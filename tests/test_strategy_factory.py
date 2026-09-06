import pytest

from strategy.buy_and_hold import BuyAndHoldStrategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.factory import create_strategy
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy
from strategy.rsi_mean_reversion import RSIMeanReversionStrategy


def test_creates_crossover_strategy():
    strategy = create_strategy("crossover", "TEST", fast_window=5, slow_window=15)

    assert isinstance(strategy, MovingAverageCrossoverStrategy)
    assert strategy.fast_window == 5
    assert strategy.slow_window == 15


def test_creates_donchian_strategy():
    strategy = create_strategy("donchian", "TEST", entry_window=55, exit_window=20)

    assert isinstance(strategy, DonchianBreakoutStrategy)
    assert strategy.entry_window == 55
    assert strategy.exit_window == 20


def test_creates_rsi_strategy():
    strategy = create_strategy("rsi", "TEST", rsi_period=21, oversold=25, overbought=75)

    assert isinstance(strategy, RSIMeanReversionStrategy)
    assert strategy.rsi_period == 21
    assert strategy.oversold == 25
    assert strategy.overbought == 75


def test_stop_loss_pct_override_applies_per_strategy():
    strategy = create_strategy("donchian", "TEST", stop_loss_pct=0.2)

    assert strategy.stop_loss_pct == 0.2


def test_stop_loss_pct_defaults_to_each_strategys_own_class_default_when_omitted():
    strategy = create_strategy("rsi", "TEST")

    assert strategy.stop_loss_pct == RSIMeanReversionStrategy(symbol="TEST").stop_loss_pct


def test_creates_buy_and_hold_strategy():
    strategy = create_strategy("buy_and_hold", "TEST", stop_loss_pct=0.5)

    assert isinstance(strategy, BuyAndHoldStrategy)
    assert strategy.stop_loss_pct == 0.5


def test_unknown_strategy_name_raises():
    with pytest.raises(ValueError):
        create_strategy("not-a-real-strategy", "TEST")
