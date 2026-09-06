from datetime import datetime, timedelta

import pytest

from core.types import Bar
from strategy.indicators import ADXCalculator, RSICalculator


def make_bar(index: int, close: float, rng: float = 1.0) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 1) + timedelta(hours=index),
        symbol="TEST",
        open=close,
        high=close + rng,
        low=close - rng,
        close=close,
        volume=1.0,
    )


def test_adx_is_none_before_warmup():
    calc = ADXCalculator(period=14)

    adx = None
    for i in range(10):
        adx = calc.update(make_bar(i, 100 + i))

    assert adx is None


def test_adx_is_high_for_a_steadily_trending_series():
    calc = ADXCalculator(period=14)

    adx = None
    for i in range(60):
        adx = calc.update(make_bar(i, 100 + i * 2))

    assert adx is not None
    assert adx > 25  # conventional "strong trend" threshold


def test_adx_is_low_for_a_choppy_sideways_series():
    calc = ADXCalculator(period=14)

    adx = None
    for i in range(60):
        close = 100 + (3 if i % 2 == 0 else -3)
        adx = calc.update(make_bar(i, close))

    assert adx is not None
    assert adx < 20


def test_adx_calculator_rejects_period_below_one():
    with pytest.raises(ValueError):
        ADXCalculator(period=0)


def test_rsi_is_none_before_warmup():
    calc = RSICalculator(period=14)

    rsi = None
    for i in range(10):
        rsi = calc.update(100 + i)

    assert rsi is None


def test_rsi_is_high_for_a_steadily_rising_series():
    calc = RSICalculator(period=14)

    rsi = None
    for i in range(30):
        rsi = calc.update(100 + i)

    assert rsi is not None
    assert rsi > 90  # all gains, no losses -- close to the 100 ceiling


def test_rsi_is_low_for_a_steadily_falling_series():
    calc = RSICalculator(period=14)

    rsi = None
    for i in range(30):
        rsi = calc.update(100 - i)

    assert rsi is not None
    assert rsi < 10  # all losses, no gains -- close to the 0 floor


def test_rsi_calculator_rejects_period_below_one():
    with pytest.raises(ValueError):
        RSICalculator(period=0)
