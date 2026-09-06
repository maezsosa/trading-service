from datetime import datetime, timedelta

from core.types import Bar, Side
from strategy.buy_and_hold import BuyAndHoldStrategy


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


def test_buys_on_the_first_bar():
    strategy = BuyAndHoldStrategy(symbol="TEST")

    signal = strategy.on_bar(make_bar(100, 0))

    assert signal is not None
    assert signal.side == Side.BUY


def test_never_signals_again_after_the_first_buy():
    strategy = BuyAndHoldStrategy(symbol="TEST")

    signals = [strategy.on_bar(make_bar(p, i)) for i, p in enumerate([100, 105, 90, 120, 50])]

    assert signals[0] is not None
    assert all(signal is None for signal in signals[1:])


def test_stop_loss_pct_defaults_wide():
    strategy = BuyAndHoldStrategy(symbol="TEST")

    assert strategy.stop_loss_pct == 0.90
