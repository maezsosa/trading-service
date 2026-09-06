from datetime import datetime, timedelta

import pytest

from core.types import Bar, Side
from strategy.trailing_reentry import TrailingReentryStrategy


def make_bar(price: float, i: int) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 1) + timedelta(hours=i),
        symbol="TEST",
        open=price,
        high=price,
        low=price,
        close=price,
        volume=100.0,
    )


def test_buys_on_the_very_first_bar_like_buy_and_hold():
    strategy = TrailingReentryStrategy(symbol="TEST", trail_pct=0.15, reentry_pct=0.10)

    signal = strategy.on_bar(make_bar(100, 0))

    assert signal is not None
    assert signal.side == Side.BUY


def test_exit_and_reentry_on_traced_price_path():
    # trail_pct=15%, reentry_pct=10%. Peak tracks the running high while
    # long; a 16.67% pullback from 120 (peak) to 100 at i=3 breaches the
    # 15% trail -> SELL. Trough then tracks the running low while flat; a
    # recovery from 90 (trough) to 100 at i=5 is +11.1%, past the 10%
    # reentry threshold -> BUY.
    strategy = TrailingReentryStrategy(symbol="TEST", trail_pct=0.15, reentry_pct=0.10)

    prices = [100, 110, 120, 100, 90, 100, 115]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[0] is not None and signals[0].side == Side.BUY
    assert signals[3] is not None and signals[3].side == Side.SELL
    assert signals[5] is not None and signals[5].side == Side.BUY
    assert all(signals[i] is None for i in [1, 2, 4, 6])


def test_rejects_non_positive_thresholds():
    with pytest.raises(ValueError):
        TrailingReentryStrategy(symbol="TEST", trail_pct=0, reentry_pct=0.10)
    with pytest.raises(ValueError):
        TrailingReentryStrategy(symbol="TEST", trail_pct=0.15, reentry_pct=-0.05)
