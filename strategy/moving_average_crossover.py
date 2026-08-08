from __future__ import annotations

from collections import deque

from core.types import Bar, Side, Signal
from strategy.base import Strategy


class MovingAverageCrossoverStrategy(Strategy):
    """Emits BUY when the fast SMA crosses above the slow SMA, SELL on the reverse cross."""

    def __init__(
        self,
        symbol: str,
        fast_window: int = 10,
        slow_window: int = 30,
        stop_loss_pct: float = 0.02,
    ):
        super().__init__(symbol)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.stop_loss_pct = stop_loss_pct
        self._closes: deque[float] = deque(maxlen=slow_window)
        self._prev_fast_above_slow: bool | None = None

    def on_bar(self, bar: Bar) -> Signal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow_window:
            return None

        fast_sma = sum(list(self._closes)[-self.fast_window :]) / self.fast_window
        slow_sma = sum(self._closes) / self.slow_window
        fast_above_slow = fast_sma > slow_sma

        signal = None
        if self._prev_fast_above_slow is not None and fast_above_slow != self._prev_fast_above_slow:
            side = Side.BUY if fast_above_slow else Side.SELL
            signal = Signal(
                timestamp=bar.timestamp,
                symbol=bar.symbol,
                side=side,
                stop_loss_pct=self.stop_loss_pct,
                reason=f"SMA{self.fast_window}/{self.slow_window} crossover",
            )

        self._prev_fast_above_slow = fast_above_slow
        return signal
