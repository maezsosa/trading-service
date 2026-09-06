from __future__ import annotations

from core.types import Bar, Side, Signal
from strategy.base import Strategy


class TrailingReentryStrategy(Strategy):
    """Buy-and-hold with a trailing exit and re-entry on recovery.

    Starts long on the first bar, like buy-and-hold. Sells when price
    pulls back trail_pct from its running peak while in the position
    (the peak keeps rising as price makes new highs, so this is a
    trailing stop, not a fixed one). While out of the market, tracks
    the running trough since the exit and buys back once price recovers
    reentry_pct from it.

    The bet: capture most of an uptrend like buy-and-hold does, but
    sidestep the largest drawdowns instead of riding them out --
    trading the risk of missing a V-shaped recovery (getting stopped
    out, then having price snap back before the reentry threshold is
    reached) for smaller max drawdown.
    """

    def __init__(
        self,
        symbol: str,
        trail_pct: float = 0.15,
        reentry_pct: float = 0.10,
        stop_loss_pct: float = 0.90,
    ):
        if trail_pct <= 0 or reentry_pct <= 0:
            raise ValueError(f"trail_pct and reentry_pct must be > 0, got {trail_pct}/{reentry_pct}")
        super().__init__(symbol)
        self.trail_pct = trail_pct
        self.reentry_pct = reentry_pct
        self.stop_loss_pct = stop_loss_pct
        self._in_position = False
        self._peak: float | None = None
        self._trough: float | None = None

    def on_bar(self, bar: Bar) -> Signal | None:
        if self._peak is None:
            # First bar ever: start long, same as buy-and-hold's entry point.
            self._in_position = True
            self._peak = bar.close
            return self._signal(bar, Side.BUY)

        if self._in_position:
            self._peak = max(self._peak, bar.close)
            if bar.close <= self._peak * (1 - self.trail_pct):
                self._in_position = False
                self._trough = bar.close
                return self._signal(bar, Side.SELL)
            return None

        self._trough = min(self._trough, bar.close)
        if bar.close >= self._trough * (1 + self.reentry_pct):
            self._in_position = True
            self._peak = bar.close
            return self._signal(bar, Side.BUY)
        return None

    def _signal(self, bar: Bar, side: Side) -> Signal:
        return Signal(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            side=side,
            stop_loss_pct=self.stop_loss_pct,
            reason=f"trailing {'exit' if side == Side.SELL else 'reentry'} ({self.trail_pct:.0%}/{self.reentry_pct:.0%})",
        )
