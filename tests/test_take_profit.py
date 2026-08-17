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


def test_take_profit_closes_position_at_exact_target_price():
    symbol = "TEST"
    t0 = datetime(2024, 1, 1)
    buy_signal = Signal(
        timestamp=t0, symbol=symbol, side=Side.BUY, stop_loss_pct=0.5, take_profit_pct=0.05
    )
    strategy = ScriptedStrategy(symbol, {0: buy_signal})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession(strategy, risk_manager, broker)

    bar0 = make_bar(symbol, t0, 100, 100, 100, 100)
    bar1 = make_bar(symbol, t0 + timedelta(hours=1), 100, 100, 100, 100)  # entry fills at 100
    bar2 = make_bar(symbol, t0 + timedelta(hours=2), 100, 110, 100, 108)  # high touches 105 target

    session.process_bar(bar0)
    session.process_bar(bar1)
    entry_fill = broker.fills[0]
    assert entry_fill.price == 100.0

    position = broker.account.positions[symbol]
    assert position.take_profit_price == 105.0

    session.process_bar(bar2)
    assert len(broker.fills) == 2
    exit_fill = broker.fills[1]
    assert exit_fill.side == Side.SELL
    assert exit_fill.price == 105.0
    assert broker.account.positions[symbol].quantity == 0.0
    assert broker.account.positions[symbol].take_profit_price is None


def test_stop_loss_takes_priority_over_take_profit_in_same_bar():
    symbol = "TEST"
    t0 = datetime(2024, 1, 1)
    buy_signal = Signal(
        timestamp=t0, symbol=symbol, side=Side.BUY, stop_loss_pct=0.02, take_profit_pct=0.05
    )
    strategy = ScriptedStrategy(symbol, {0: buy_signal})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession(strategy, risk_manager, broker)

    bar0 = make_bar(symbol, t0, 100, 100, 100, 100)
    bar1 = make_bar(symbol, t0 + timedelta(hours=1), 100, 100, 100, 100)  # entry at 100, stop=98, target=105
    # A single wide bar that touches both the stop (98) and the target (105).
    bar2 = make_bar(symbol, t0 + timedelta(hours=2), 100, 110, 90, 100)

    session.process_bar(bar0)
    session.process_bar(bar1)
    session.process_bar(bar2)

    assert len(broker.fills) == 2
    exit_fill = broker.fills[1]
    assert exit_fill.price == 98.0  # stop-loss price, not the take-profit price
    assert broker.account.positions[symbol].quantity == 0.0
