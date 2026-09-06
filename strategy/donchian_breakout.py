from __future__ import annotations

from collections import deque

from core.types import Bar, Side, Signal
from strategy.base import Strategy


class DonchianBreakoutStrategy(Strategy):
    """Trend-following breakout, in the spirit of the Turtle Trading system.

    Enters BUY on a new entry_window-bar high, SELL on a new
    entry_window-bar low. While in a position, exits (which reverses,
    same as MovingAverageCrossoverStrategy's signals do) on a break of the
    shorter exit_window channel in the opposite direction -- exiting on a
    tighter channel than the one used to enter locks in gains faster than
    waiting for an equally extreme move the other way.

    This is the complementary case to the crossover strategy: it's built
    to stay in a trade through a sustained trend instead of trading in
    and out of it, at the cost of giving back more on a sharp reversal
    (stop_loss_pct defaults wider than the crossover's, on purpose --
    breakout systems need room to breathe, not a tight leash).
    """

    def __init__(
        self,
        symbol: str,
        entry_window: int = 20,
        exit_window: int = 10,
        stop_loss_pct: float = 0.10,
    ):
        if entry_window < 1 or exit_window < 1:
            raise ValueError(f"entry_window and exit_window must be >= 1, got {entry_window}/{exit_window}")
        super().__init__(symbol)
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.stop_loss_pct = stop_loss_pct
        self._highs: deque[float] = deque(maxlen=entry_window)
        self._lows: deque[float] = deque(maxlen=entry_window)
        self._exit_highs: deque[float] = deque(maxlen=exit_window)
        self._exit_lows: deque[float] = deque(maxlen=exit_window)
        self._position_side: Side | None = None

    def on_bar(self, bar: Bar) -> Signal | None:
        signal = None
        if len(self._highs) >= self.entry_window and len(self._exit_highs) >= self.exit_window:
            if self._position_side != Side.BUY and bar.close > max(self._highs):
                signal = self._signal(bar, Side.BUY, f"donchian {self.entry_window}-bar high breakout")
                self._position_side = Side.BUY
            elif self._position_side != Side.SELL and bar.close < min(self._lows):
                signal = self._signal(bar, Side.SELL, f"donchian {self.entry_window}-bar low breakout")
                self._position_side = Side.SELL
            elif self._position_side == Side.BUY and bar.close < min(self._exit_lows):
                signal = self._signal(bar, Side.SELL, f"donchian {self.exit_window}-bar exit")
                self._position_side = Side.SELL
            elif self._position_side == Side.SELL and bar.close > max(self._exit_highs):
                signal = self._signal(bar, Side.BUY, f"donchian {self.exit_window}-bar exit")
                self._position_side = Side.BUY

        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._exit_highs.append(bar.high)
        self._exit_lows.append(bar.low)
        return signal

    def _signal(self, bar: Bar, side: Side, reason: str) -> Signal:
        return Signal(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            side=side,
            stop_loss_pct=self.stop_loss_pct,
            reason=reason,
        )
