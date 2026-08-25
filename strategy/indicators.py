from __future__ import annotations

from core.types import Bar


class ADXCalculator:
    """Wilder's Average Directional Index, computed incrementally bar by bar.

    Measures trend STRENGTH (0-100), not direction: high ADX means the
    market is trending strongly (either way), low ADX means it's ranging or
    choppy. Feed it bars in order via update(); returns None until enough
    bars have arrived to warm up (roughly 2 * period bars).
    """

    def __init__(self, period: int = 14):
        self.period = period
        self._prev_bar: Bar | None = None
        self._tr_values: list[float] = []
        self._plus_dm_values: list[float] = []
        self._minus_dm_values: list[float] = []
        self._dx_values: list[float] = []
        self._smoothed_tr: float | None = None
        self._smoothed_plus_dm: float | None = None
        self._smoothed_minus_dm: float | None = None
        self._adx: float | None = None

    def update(self, bar: Bar) -> float | None:
        prev = self._prev_bar
        self._prev_bar = bar
        if prev is None:
            return None

        true_range = max(
            bar.high - bar.low,
            abs(bar.high - prev.close),
            abs(bar.low - prev.close),
        )
        up_move = bar.high - prev.high
        down_move = prev.low - bar.low
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        if self._smoothed_tr is None:
            self._tr_values.append(true_range)
            self._plus_dm_values.append(plus_dm)
            self._minus_dm_values.append(minus_dm)
            if len(self._tr_values) < self.period:
                return None
            self._smoothed_tr = sum(self._tr_values)
            self._smoothed_plus_dm = sum(self._plus_dm_values)
            self._smoothed_minus_dm = sum(self._minus_dm_values)
        else:
            # Wilder's smoothing: each new value replaces 1/period of the running total.
            self._smoothed_tr += true_range - self._smoothed_tr / self.period
            self._smoothed_plus_dm += plus_dm - self._smoothed_plus_dm / self.period
            self._smoothed_minus_dm += minus_dm - self._smoothed_minus_dm / self.period

        if self._smoothed_tr == 0:
            dx = 0.0
        else:
            plus_di = 100 * self._smoothed_plus_dm / self._smoothed_tr
            minus_di = 100 * self._smoothed_minus_dm / self._smoothed_tr
            di_sum = plus_di + minus_di
            dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0

        if self._adx is None:
            self._dx_values.append(dx)
            if len(self._dx_values) < self.period:
                return None
            self._adx = sum(self._dx_values) / self.period
        else:
            self._adx = (self._adx * (self.period - 1) + dx) / self.period

        return self._adx
