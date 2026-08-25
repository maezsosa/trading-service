from __future__ import annotations

from collections import deque

from core.types import Bar, Side, Signal
from strategy.base import Strategy
from strategy.indicators import ADXCalculator


class MovingAverageCrossoverStrategy(Strategy):
    """Emits BUY when the fast SMA crosses above the slow SMA, SELL on the reverse cross.

    A cross alone is a weak signal in a ranging market: the two SMAs can
    flip back and forth on noise without any real trend behind it
    (whipsaw). min_separation_pct, if set above the default 0.0, requires
    the SMAs to actually diverge by at least that fraction after a cross
    before the signal fires -- and drops the pending signal entirely if
    price reverses back through the cross before that confirmation, since
    that reversal is exactly the noise this filter is meant to catch.

    min_separation_pct still tunes the SAME crossover, though -- it can't
    fix the fact that one fast/slow window pair has to work in both
    trending and ranging markets. adx_threshold, if set above the default
    0.0, adds an independent regime gate: a confirmed cross only fires if
    ADX (trend strength, not direction) is at or above the threshold,
    regardless of how wide the SMA separation is. Below it, the market is
    judged too choppy to trade at all.
    """

    def __init__(
        self,
        symbol: str,
        fast_window: int = 10,
        slow_window: int = 30,
        stop_loss_pct: float = 0.02,
        min_separation_pct: float = 0.0,
        adx_period: int = 14,
        adx_threshold: float = 0.0,
    ):
        if fast_window < 1 or slow_window < 1:
            raise ValueError(f"fast_window and slow_window must be >= 1, got {fast_window}/{slow_window}")
        super().__init__(symbol)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.stop_loss_pct = stop_loss_pct
        self.min_separation_pct = min_separation_pct
        self.adx_threshold = adx_threshold
        self._closes: deque[float] = deque(maxlen=slow_window)
        self._prev_fast_above_slow: bool | None = None
        self._pending_side: Side | None = None
        self._adx_calc = ADXCalculator(period=adx_period)

    def on_bar(self, bar: Bar) -> Signal | None:
        adx = self._adx_calc.update(bar)

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
                # A confirmed cross still doesn't fire if the market isn't
                # trending strongly enough (ADX below threshold) -- dropped
                # here rather than re-armed, same as a reversal-before-
                # confirmation: this regime was judged too choppy to trade.
                if self.adx_threshold <= 0 or (adx is not None and adx >= self.adx_threshold):
                    signal = Signal(
                        timestamp=bar.timestamp,
                        symbol=bar.symbol,
                        side=side,
                        stop_loss_pct=self.stop_loss_pct,
                        reason=f"SMA{self.fast_window}/{self.slow_window} crossover (separation {separation_pct:.2%})",
                    )

        return signal
