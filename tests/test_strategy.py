from datetime import datetime, timedelta

import pytest

from core.types import Bar, Side
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy


def make_bar(close: float, i: int) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 1) + timedelta(hours=i),
        symbol="TEST",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100.0,
    )


def test_no_signal_before_enough_data():
    strategy = MovingAverageCrossoverStrategy(symbol="TEST", fast_window=2, slow_window=4)

    signal = strategy.on_bar(make_bar(100, 0))

    assert signal is None


def test_emits_buy_signal_on_upward_crossover():
    strategy = MovingAverageCrossoverStrategy(symbol="TEST", fast_window=2, slow_window=4)

    prices = [100, 100, 100, 100, 105, 110]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    buy_signals = [s for s in signals if s is not None and s.side == Side.BUY]
    assert len(buy_signals) == 1


def test_emits_sell_signal_on_downward_crossover():
    strategy = MovingAverageCrossoverStrategy(symbol="TEST", fast_window=2, slow_window=4)

    prices = [100, 100, 100, 100, 105, 110, 90, 80]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    sell_signals = [s for s in signals if s is not None and s.side == Side.SELL]
    assert len(sell_signals) == 1


def test_min_separation_pct_delays_confirmation_until_gap_widens():
    strategy = MovingAverageCrossoverStrategy(
        symbol="TEST", fast_window=2, slow_window=4, min_separation_pct=0.03
    )
    # Same series as test_emits_buy_signal_on_upward_crossover, where the
    # cross confirms immediately (bar 4) with no separation filter -- here
    # the ~1.2% gap right at the cross isn't enough, so confirmation waits
    # one more bar until the gap widens past 3%.
    prices = [100, 100, 100, 100, 105, 110]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    buy_signals = [i for i, s in enumerate(signals) if s is not None and s.side == Side.BUY]
    assert buy_signals == [5]


def test_min_separation_pct_drops_signal_on_whipsaw_before_confirming():
    strategy = MovingAverageCrossoverStrategy(
        symbol="TEST", fast_window=2, slow_window=4, min_separation_pct=0.10
    )
    # Crosses up briefly, then reverses down -- the gap never reaches the
    # 10% threshold in either direction, so no signal should ever fire.
    prices = [100, 100, 100, 100, 105, 100, 95, 90]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert all(signal is None for signal in signals)


def test_rejects_zero_or_negative_windows():
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(symbol="TEST", fast_window=0, slow_window=30)
    with pytest.raises(ValueError):
        MovingAverageCrossoverStrategy(symbol="TEST", fast_window=10, slow_window=0)
