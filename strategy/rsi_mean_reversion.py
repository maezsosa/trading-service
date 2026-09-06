from __future__ import annotations

from core.types import Bar, Side, Signal
from strategy.base import Strategy
from strategy.indicators import RSICalculator


class RSIMeanReversionStrategy(Strategy):
    """Bets that an extreme move reverts, rather than continues -- the
    opposite thesis from MovingAverageCrossoverStrategy and
    DonchianBreakoutStrategy (both trend-following).

    BUY when RSI crosses back up through oversold (recovery confirmed,
    not the instant it dips below -- buying the exact bottom of a falling
    knife is the classic mean-reversion mistake). SELL when RSI crosses
    back down through overbought, same idea in reverse.

    Expected to do well in ranging/choppy markets where price oscillates
    without commitment (exactly where the trend-following strategies
    whipsaw) and poorly in a sustained trend (fighting it the whole way,
    e.g. repeatedly "selling overbought" through a real bull run).
    """

    def __init__(
        self,
        symbol: str,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        stop_loss_pct: float = 0.03,
    ):
        if not 0 < oversold < overbought < 100:
            raise ValueError(f"require 0 < oversold < overbought < 100, got {oversold}/{overbought}")
        super().__init__(symbol)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_loss_pct = stop_loss_pct
        self._rsi_calc = RSICalculator(period=rsi_period)
        self._prev_rsi: float | None = None

    def on_bar(self, bar: Bar) -> Signal | None:
        rsi = self._rsi_calc.update(bar.close)
        prev_rsi = self._prev_rsi
        self._prev_rsi = rsi

        signal = None
        if rsi is not None and prev_rsi is not None:
            if prev_rsi <= self.oversold < rsi:
                signal = self._signal(bar, Side.BUY, f"RSI recovered above {self.oversold:.0f}")
            elif prev_rsi >= self.overbought > rsi:
                signal = self._signal(bar, Side.SELL, f"RSI fell below {self.overbought:.0f}")

        return signal

    def _signal(self, bar: Bar, side: Side, reason: str) -> Signal:
        return Signal(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            side=side,
            stop_loss_pct=self.stop_loss_pct,
            reason=reason,
        )
