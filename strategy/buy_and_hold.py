from __future__ import annotations

from core.types import Bar, Side, Signal
from strategy.base import Strategy


class BuyAndHoldStrategy(Strategy):
    """Buys once on the first bar it sees and never signals again.

    The engine's RiskManager currently requires every order to carry a
    stop-loss (there's no "no stop" path yet -- see the backlog item for
    real support). stop_loss_pct defaults very wide (90%) as an
    approximation: in practice it's never touched by anything short of a
    near-total collapse, but it's not a literal "never sell" guarantee
    the way real buy-and-hold is. Runs through the same PaperBroker as
    every other strategy, so fees/slippage apply here too -- unlike
    backtest.metrics.buy_and_hold_equity_curve(), which is a pure
    zero-cost benchmark computed outside the engine.
    """

    def __init__(self, symbol: str, stop_loss_pct: float = 0.90):
        super().__init__(symbol)
        self.stop_loss_pct = stop_loss_pct
        self._bought = False

    def on_bar(self, bar: Bar) -> Signal | None:
        if self._bought:
            return None
        self._bought = True
        return Signal(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            side=Side.BUY,
            stop_loss_pct=self.stop_loss_pct,
            reason="buy and hold",
        )
