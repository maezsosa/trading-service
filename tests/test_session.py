from datetime import datetime, timedelta

import pytest

from broker.paper_broker import PaperBroker
from core.session import TradingSession
from core.types import Bar, Side, Signal
from risk.manager import RiskConfig, RiskManager
from strategy.base import Strategy


class ScriptedStrategy(Strategy):
    """Emits a fixed Signal on chosen bar indices, None otherwise."""

    def __init__(self, symbol: str, signals_by_index: dict[int, Side]):
        super().__init__(symbol)
        self._signals_by_index = signals_by_index
        self._index = -1

    def on_bar(self, bar: Bar) -> Signal | None:
        self._index += 1
        side = self._signals_by_index.get(self._index)
        if side is None:
            return None
        return Signal(timestamp=bar.timestamp, symbol=bar.symbol, side=side, stop_loss_pct=0.5)


def make_bars(symbol: str, closes: list[float]) -> list[Bar]:
    timestamp = datetime(2024, 1, 1)
    bars = []
    for close in closes:
        bars.append(
            Bar(
                timestamp=timestamp,
                symbol=symbol,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000.0,
            )
        )
        timestamp += timedelta(hours=1)
    return bars


def test_reversal_signal_flattens_exactly_before_reentering():
    symbol = "TEST"
    # BUY signal queued on bar 0's close fills on bar 1's open; SELL signal
    # queued on bar 1's close fills on bar 2's open, and must close the long
    # to exactly zero (not a mismatched partial/over-sized flip) before any
    # new entry.
    strategy = ScriptedStrategy(symbol, {0: Side.BUY, 1: Side.SELL})
    risk_manager = RiskManager(RiskConfig(max_position_pct=1.0, max_total_exposure_pct=1.0))
    broker = PaperBroker(initial_cash=10_000.0)
    session = TradingSession(strategy, risk_manager, broker)

    bars = make_bars(symbol, [100.0, 110.0, 120.0])
    for bar in bars:
        session.process_bar(bar)

    fills = broker.fills
    # opening BUY, exact-flatten SELL, then a fresh SELL entry sized from a
    # clean (flat) base -- three fills, not a single mismatched flip.
    assert len(fills) == 3

    opening_fill, flatten_fill, reentry_fill = fills
    assert opening_fill.side == Side.BUY
    assert flatten_fill.side == Side.SELL
    assert reentry_fill.side == Side.SELL
    # No residual: the flatten fill exactly matches the opened quantity.
    assert flatten_fill.quantity == opening_fill.quantity

    position = broker.account.positions[symbol]
    # Position lands exactly on the fresh entry's size -- not some
    # mismatched leftover from combining close+reopen into one fill.
    assert position.quantity == -reentry_fill.quantity
    assert position.avg_entry_price == pytest.approx(reentry_fill.price)
