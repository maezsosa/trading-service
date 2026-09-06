from datetime import datetime, timedelta

import pytest

from core.types import Bar, Side
from strategy.donchian_breakout import DonchianBreakoutStrategy


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


def test_no_signal_before_entry_window_warms_up():
    strategy = DonchianBreakoutStrategy(symbol="TEST", entry_window=3, exit_window=2)

    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate([100, 100, 100])]

    assert all(signal is None for signal in signals)


def test_new_high_breakout_emits_buy():
    strategy = DonchianBreakoutStrategy(symbol="TEST", entry_window=3, exit_window=2)

    prices = [100, 100, 100, 105]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[:3] == [None, None, None]
    assert signals[3] is not None
    assert signals[3].side == Side.BUY


def test_new_low_breakout_emits_sell():
    strategy = DonchianBreakoutStrategy(symbol="TEST", entry_window=3, exit_window=2)

    prices = [100, 100, 100, 95]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[3] is not None
    assert signals[3].side == Side.SELL


def test_exits_on_shorter_channel_before_entry_channel_would_reverse():
    # entry_window=3, exit_window=2: after entering long at bar 3 (close=105),
    # bar 5 (close=101) breaks the 2-bar exit low (103) well before it would
    # break the 3-bar entry low (100) -- the shorter channel should fire first.
    strategy = DonchianBreakoutStrategy(symbol="TEST", entry_window=3, exit_window=2)

    prices = [100, 100, 100, 105, 103, 101]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[3] is not None and signals[3].side == Side.BUY
    assert signals[4] is None
    assert signals[5] is not None and signals[5].side == Side.SELL


def test_does_not_re_signal_on_further_new_highs_while_already_long():
    strategy = DonchianBreakoutStrategy(symbol="TEST", entry_window=3, exit_window=2)

    prices = [100, 100, 100, 105, 110]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[3] is not None and signals[3].side == Side.BUY
    assert signals[4] is None  # a further new high while already long is not a fresh signal


def test_rejects_zero_or_negative_windows():
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(symbol="TEST", entry_window=0, exit_window=10)
    with pytest.raises(ValueError):
        DonchianBreakoutStrategy(symbol="TEST", entry_window=20, exit_window=0)
