from datetime import datetime, timedelta

from broker.paper_broker import PaperBroker
from core.session import TradingSession
from core.types import Bar, Side, Signal
from backtest.merge import merge_bars
from risk.manager import RiskConfig, RiskManager
from strategy.base import Strategy


class ScriptedStrategy(Strategy):
    """Emits a fixed Signal on chosen bar indices (counted per-symbol), None otherwise."""

    def __init__(self, symbol: str, signals_by_index: dict[int, Signal]):
        super().__init__(symbol)
        self._signals_by_index = signals_by_index
        self._index = -1

    def on_bar(self, bar: Bar) -> Signal | None:
        self._index += 1
        return self._signals_by_index.get(self._index)


def make_bar(symbol: str, timestamp: datetime, price: float = 100.0) -> Bar:
    return Bar(
        timestamp=timestamp,
        symbol=symbol,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1000.0,
    )


def test_merge_bars_interleaves_multiple_streams_by_timestamp():
    t0 = datetime(2024, 1, 1)
    stream_a = [make_bar("AAA", t0), make_bar("AAA", t0 + timedelta(hours=2))]
    stream_b = [make_bar("BBB", t0 + timedelta(hours=1)), make_bar("BBB", t0 + timedelta(hours=3))]

    merged = list(merge_bars([stream_a, stream_b]))

    assert [(bar.symbol, bar.timestamp) for bar in merged] == [
        ("AAA", t0),
        ("BBB", t0 + timedelta(hours=1)),
        ("AAA", t0 + timedelta(hours=2)),
        ("BBB", t0 + timedelta(hours=3)),
    ]


def test_bar_only_drives_its_own_symbols_strategy():
    symbol_a, symbol_b = "AAA", "BBB"
    t0 = datetime(2024, 1, 1)
    strategy_a = ScriptedStrategy(symbol_a, {})
    strategy_b = ScriptedStrategy(symbol_b, {})
    risk_manager = RiskManager(RiskConfig())
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession([strategy_a, strategy_b], risk_manager, broker)

    session.process_bar(make_bar(symbol_a, t0))

    assert strategy_a._index == 0
    assert strategy_b._index == -1  # never called: this bar wasn't its symbol


def test_portfolio_session_shares_exposure_limit_across_symbols():
    symbol_a, symbol_b = "AAA", "BBB"
    t0 = datetime(2024, 1, 1)

    signal_a = Signal(timestamp=t0, symbol=symbol_a, side=Side.BUY, stop_loss_pct=0.5)
    signal_b = Signal(timestamp=t0, symbol=symbol_b, side=Side.BUY, stop_loss_pct=0.5)
    strategy_a = ScriptedStrategy(symbol_a, {0: signal_a})
    strategy_b = ScriptedStrategy(symbol_b, {1: signal_b})

    risk_manager = RiskManager(
        RiskConfig(risk_per_trade_pct=1.0, max_position_pct=1.0, max_total_exposure_pct=0.5)
    )
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession([strategy_a, strategy_b], risk_manager, broker)

    # A's signal (bar index 0) fills on the next A bar, consuming the whole
    # portfolio exposure budget (50% of $10k equity) by itself.
    session.process_bar(make_bar(symbol_a, t0))
    session.process_bar(make_bar(symbol_a, t0 + timedelta(hours=1)))
    assert len(broker.fills) == 1
    assert broker.account.positions[symbol_a].quantity == 50.0  # $5,000 notional @ 100

    # B's signal (its bar index 1) is validated only after A already used
    # up the entire max_total_exposure_pct budget, so B gets nothing.
    session.process_bar(make_bar(symbol_b, t0 + timedelta(hours=2)))
    session.process_bar(make_bar(symbol_b, t0 + timedelta(hours=3)))
    session.process_bar(make_bar(symbol_b, t0 + timedelta(hours=4)))

    assert len(broker.fills) == 1  # still just A's fill
    position_b = broker.account.positions.get(symbol_b)
    assert position_b is None or not position_b.is_open
