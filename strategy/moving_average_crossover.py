from __future__ import annotations

from collections import deque

from core.types import Bar, Side, Signal
from strategy.base import Strategy


class MovingAverageCrossoverStrategy(Strategy):
    """Emits BUY when the fast SMA crosses above the slow SMA, SELL on the reverse cross.

    A cross alone is a weak signal in a ranging market: the two SMAs can
    flip back and forth on noise without any real trend behind it
    (whipsaw). min_separation_pct, if set above the default 0.0, requires
    the SMAs to actually diverge by at least that fraction after a cross
    before the signal fires -- and drops the pending signal entirely if
    price reverses back through the cross before that confirmation, since
    that reversal is exactly the noise this filter is meant to catch.
    """

    def __init__(
        self,
        symbol: str,
        fast_window: int = 10,
        slow_window: int = 30,
        stop_loss_pct: float = 0.02,
        min_separation_pct: float = 0.0,
    ):
        super().__init__(symbol)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.stop_loss_pct = stop_loss_pct
        self.min_separation_pct = min_separation_pct
        self._closes: deque[float] = deque(maxlen=slow_window)
        self._prev_fast_above_slow: bool | None = None
        self._pending_side: Side | None = None

    def on_bar(self, bar: Bar) -> Signal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow_window:
            return None

        fast_sma = sum(list(self._closes)[-self.fast_window :]) / self.fast_window
        slow_sma = sum(self._closes) / self.slow_window
        fast_above_slow = fast_sma > slow_sma
        separation_pct = abs(fast_sma - slow_sma) / slow_sma if slow_sma else 0.0

        if self._prev_fast_above_slow is not None and fast_above_slow != self._prev_fast_above_slow:
            # A fresh cross (re)arms confirmation, discarding whatever
            # pending cross came before -- it never confirmed, so it's stale.
            self._pending_side = Side.BUY if fast_above_slow else Side.SELL
        self._prev_fast_above_slow = fast_above_slow

        signal = None
        if self._pending_side is not None:
            expected_above = self._pending_side == Side.BUY
            if fast_above_slow != expected_above:
                # Reversed back through the cross before confirming --
                # noise, not a trend. Drop it; this is the filter working.
                self._pending_side = None
            elif separation_pct >= self.min_separation_pct:
                side = self._pending_side
                self._pending_side = None
                signal = Signal(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    side=side,
                    stop_loss_pct=self.stop_loss_pct,
                    reason=f"SMA{self.fast_window}/{self.slow_window} crossover (separation {separation_pct:.2%})",
                )

        return signal
