from datetime import datetime, timedelta

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
