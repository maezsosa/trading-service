from __future__ import annotations

from core.types import AccountState, Fill, Order, Position, Side
from broker.base import Broker


class PaperBroker(Broker):
    """Simulated broker: fills every order immediately at the given mark price.

    Owns the AccountState (cash, positions, realized PnL) so the backtester
    and the risk manager always see a consistent view of the account.
    """

    def __init__(self, initial_cash: float, fee_pct: float = 0.0):
        self.account = AccountState(cash=initial_cash)
        self.fee_pct = fee_pct
        self.fills: list[Fill] = []

    def submit_order(self, order: Order, mark_price: float) -> Fill:
        fee = mark_price * order.quantity * self.fee_pct
        position = self.account.positions.setdefault(order.symbol, Position(symbol=order.symbol))
        signed_qty = order.quantity if order.side == Side.BUY else -order.quantity

        same_direction = position.quantity == 0 or (position.quantity > 0) == (signed_qty > 0)
        if same_direction:
            total_cost = position.avg_entry_price * position.quantity + mark_price * signed_qty
            position.quantity += signed_qty
            position.avg_entry_price = (
                total_cost / position.quantity if position.quantity != 0 else 0.0
            )
            position.stop_loss_price = order.stop_loss_price
            self.account.cash -= signed_qty * mark_price + fee
        else:
            closing_qty = min(abs(signed_qty), abs(position.quantity))
            direction = 1 if position.quantity > 0 else -1
            realized = closing_qty * (mark_price - position.avg_entry_price) * direction
            self.account.realized_pnl_today += realized
            self.account.cash += closing_qty * mark_price * direction - fee
            position.quantity += signed_qty
            if position.quantity == 0:
                position.avg_entry_price = 0.0
                position.stop_loss_price = None
            else:
                # Order size exceeded the open position: the remainder opens
                # a new position in the opposite direction at the fill price.
                position.avg_entry_price = mark_price
                position.stop_loss_price = order.stop_loss_price

        fill = Fill(
            timestamp=order.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=mark_price,
        )
        self.fills.append(fill)
        return fill

    def get_cash(self) -> float:
        return self.account.cash
