from datetime import datetime, timedelta

import pytest

from core.types import Bar, Side
from strategy.rsi_mean_reversion import RSIMeanReversionStrategy


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


def test_no_signal_before_rsi_warms_up():
    strategy = RSIMeanReversionStrategy(symbol="TEST", rsi_period=3)

    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate([100, 102, 101, 103])]

    # RSI itself becomes available at index 3, but a signal needs a *prior*
    # RSI to detect a cross, so nothing can fire yet even once warmed up.
    assert all(signal is None for signal in signals)


def test_sell_and_buy_signals_on_verified_rsi_crosses():
    # RSI(period=3) for this exact series, hand-verified against
    # RSICalculator directly: [_, _, _, 80.0, 36.36, 25.81, 55.12, 77.42]
    # (index 0-2: not yet available). Crosses: 80.0 -> 36.36 crosses down
    # through overbought(70) at index 4; 25.81 -> 55.12 crosses up through
    # oversold(30) at index 6.
    strategy = RSIMeanReversionStrategy(symbol="TEST", rsi_period=3, oversold=30, overbought=70)

    prices = [100, 102, 101, 103, 99, 97, 100, 105]
    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate(prices)]

    assert signals[4] is not None and signals[4].side == Side.SELL
    assert signals[6] is not None and signals[6].side == Side.BUY
    assert all(signals[i] is None for i in [0, 1, 2, 3, 5, 7])


def test_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        RSIMeanReversionStrategy(symbol="TEST", oversold=70, overbought=30)
    with pytest.raises(ValueError):
        RSIMeanReversionStrategy(symbol="TEST", oversold=0, overbought=70)
