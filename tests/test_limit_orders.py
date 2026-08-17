from datetime import datetime, timedelta

from broker.paper_broker import PaperBroker
from core.session import TradingSession
from core.types import Bar, Side, Signal
from risk.manager import RiskConfig, RiskManager
from strategy.base import Strategy


class ScriptedStrategy(Strategy):
    """Emits a fixed Signal on chosen bar indices, None otherwise."""

    def __init__(self, symbol: str, signals_by_index: dict[int, Signal]):
        super().__init__(symbol)
        self._signals_by_index = signals_by_index
        self._index = -1

    def on_bar(self, bar: Bar) -> Signal | None:
        self._index += 1
        return self._signals_by_index.get(self._index)


def make_bar(symbol: str, timestamp: datetime, open_: float, high: float, low: float, close: float) -> Bar:
    return Bar(
        timestamp=timestamp,
        symbol=symbol,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
    )


def test_limit_order_rests_until_touched_then_fills_at_exact_limit_price():
    symbol = "TEST"
    t0 = datetime(2024, 1, 1)
    buy_signal = Signal(timestamp=t0, symbol=symbol, side=Side.BUY, limit_price=95.0)
    strategy = ScriptedStrategy(symbol, {0: buy_signal})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    # High slippage on purpose: a limit fill must ignore it entirely.
    broker = PaperBroker(initial_cash=10_000.0, slippage_pct=0.05)
    session = TradingSession(strategy, risk_manager, broker)

    bar0 = make_bar(symbol, t0, 100, 100, 100, 100)
    bar1 = make_bar(symbol, t0 + timedelta(hours=1), 100, 100, 100, 100)
    bar2 = make_bar(symbol, t0 + timedelta(hours=2), 98, 98, 90, 96)  # low touches the 95 limit

    session.process_bar(bar0)
    assert broker.fills == []

    session.process_bar(bar1)
    assert broker.fills == []
    assert len(session._pending_limit_orders) == 1

    session.process_bar(bar2)
    assert len(broker.fills) == 1
    fill = broker.fills[0]
    assert fill.side == Side.BUY
    assert fill.price == 95.0
    assert session._pending_limit_orders == []


def test_limit_order_stays_pending_while_price_never_touches_it():
    symbol = "TEST"
    t0 = datetime(2024, 1, 1)
    buy_signal = Signal(timestamp=t0, symbol=symbol, side=Side.BUY, limit_price=50.0)
    strategy = ScriptedStrategy(symbol, {0: buy_signal})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession(strategy, risk_manager, broker)

    bars = [
        make_bar(symbol, t0, 100, 100, 100, 100),
        make_bar(symbol, t0 + timedelta(hours=1), 100, 105, 95, 100),
        make_bar(symbol, t0 + timedelta(hours=2), 100, 105, 95, 100),
    ]
    for bar in bars:
        session.process_bar(bar)

    assert broker.fills == []
    assert len(session._pending_limit_orders) == 1


def test_new_signal_cancels_stale_pending_limit_order():
    symbol = "TEST"
    t0 = datetime(2024, 1, 1)
    stale_signal = Signal(timestamp=t0, symbol=symbol, side=Side.BUY, limit_price=50.0)
    fresh_signal = Signal(timestamp=t0, symbol=symbol, side=Side.SELL, stop_loss_pct=0.5)
    strategy = ScriptedStrategy(symbol, {0: stale_signal, 1: fresh_signal})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession(strategy, risk_manager, broker)

    bars = [
        make_bar(symbol, t0, 100, 100, 100, 100),
        make_bar(symbol, t0 + timedelta(hours=1), 100, 100, 100, 100),
        make_bar(symbol, t0 + timedelta(hours=2), 100, 100, 100, 100),
    ]
    session.process_bar(bars[0])  # queues stale_signal
    session.process_bar(bars[1])  # executes stale_signal -> resting limit order; queues fresh_signal
    assert len(session._pending_limit_orders) == 1

    session.process_bar(bars[2])  # executes fresh_signal -> must drop the stale resting order
    assert session._pending_limit_orders == []
