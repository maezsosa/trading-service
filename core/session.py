from __future__ import annotations

from core.types import Bar, Order, Side
from strategy.base import Strategy
from risk.manager import RiskManager
from broker.paper_broker import PaperBroker


class TradingSession:
    """Processes one bar at a time through strategy -> risk manager -> broker.

    Shared by the historical Backtester and the live PaperTradingRunner so a
    strategy behaves identically whether it's replaying history or trading
    against a live feed — only the source of bars and the broker change.
    """

    def __init__(self, strategy: Strategy, risk_manager: RiskManager, broker: PaperBroker):
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.broker = broker
        self.equity_curve: list[tuple] = []
        self._current_day = None

    def process_bar(self, bar: Bar) -> None:
        if self._current_day is not None and bar.timestamp.date() != self._current_day:
            self.broker.account.realized_pnl_today = 0.0
        self._current_day = bar.timestamp.date()

        self._check_stop_loss(bar)

        signal = self.strategy.on_bar(bar)
        if signal is not None:
            order = self.risk_manager.validate(signal, self.broker.account, bar.close)
            if order is not None:
                self.broker.submit_order(order, bar.close)

        equity = self.broker.account.equity({bar.symbol: bar.close})
        self.equity_curve.append((bar.timestamp, equity))

    def _check_stop_loss(self, bar: Bar) -> None:
        position = self.broker.account.positions.get(bar.symbol)
        if position is None or not position.is_open or position.stop_loss_price is None:
            return

        hit = (position.quantity > 0 and bar.low <= position.stop_loss_price) or (
            position.quantity < 0 and bar.high >= position.stop_loss_price
        )
        if not hit:
            return

        closing_side = Side.SELL if position.quantity > 0 else Side.BUY
        order = Order(
            timestamp=bar.timestamp,
            symbol=bar.symbol,
            side=closing_side,
            quantity=abs(position.quantity),
        )
        self.broker.submit_order(order, position.stop_loss_price)
