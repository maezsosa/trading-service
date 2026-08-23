from __future__ import annotations

from core.types import AccountState, Fill, Order, Position, Side
from broker.base import Broker


class PaperBroker(Broker):
    """Simulated broker: fills every order immediately, at the given mark
    price adjusted for simulated slippage.

    Owns the AccountState (cash, positions, realized PnL) so the backtester
    and the risk manager always see a consistent view of the account.
    """

    def __init__(self, initial_cash: float, fee_pct: float = 0.0, slippage_pct: float = 0.0):
        self.account = AccountState(cash=initial_cash)
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.fills: list[Fill] = []

    def submit_order(self, order: Order, mark_price: float, apply_slippage: bool = True) -> Fill:
        # Slippage always works against the trader: a buy fills higher than
        # the quoted price, a sell fills lower -- never in your favor. Not
        # applied to a limit-order fill: that price is a guarantee, never
        # worse than what was specified.
        if apply_slippage:
            slippage_multiplier = 1 + self.slippage_pct if order.side == Side.BUY else 1 - self.slippage_pct
        else:
            slippage_multiplier = 1.0
        execution_price = mark_price * slippage_multiplier

        fee = execution_price * order.quantity * self.fee_pct
        position = self.account.positions.setdefault(order.symbol, Position(symbol=order.symbol))
        signed_qty = order.quantity if order.side == Side.BUY else -order.quantity

        realized: float | None = None
        same_direction = position.quantity == 0 or (position.quantity > 0) == (signed_qty > 0)
        if same_direction:
            # Abrir o sumar a favor de la posición: el avg_entry_price nuevo
            # es un promedio ponderado entre lo que ya había y lo que se
            # suma ahora -- no hay PnL realizado, todavía no se cerró nada.
            total_cost = position.avg_entry_price * position.quantity + execution_price * signed_qty
            position.quantity += signed_qty
            position.avg_entry_price = (
                total_cost / position.quantity if position.quantity != 0 else 0.0
            )
            position.stop_loss_price = order.stop_loss_price
            position.take_profit_price = order.take_profit_price
            self.account.cash -= signed_qty * execution_price + fee
        else:
            # Orden en contra de la posición existente: cierra (total o
            # parcialmente) contra avg_entry_price, ahí sí hay PnL realizado.
            closing_qty = min(abs(signed_qty), abs(position.quantity))
            direction = 1 if position.quantity > 0 else -1
            realized = closing_qty * (execution_price - position.avg_entry_price) * direction
            self.account.realized_pnl_today += realized
            self.account.cash += closing_qty * execution_price * direction - fee
            position.quantity += signed_qty
            if position.quantity == 0:
                position.avg_entry_price = 0.0
                position.stop_loss_price = None
                position.take_profit_price = None
            else:
                # Order size exceeded the open position: the remainder opens
                # a new position in the opposite direction at the fill price.
                position.avg_entry_price = execution_price
                position.stop_loss_price = order.stop_loss_price
                position.take_profit_price = order.take_profit_price

        fill = Fill(
            timestamp=order.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
            realized_pnl=realized,
        )
        self.fills.append(fill)
        return fill

    def get_cash(self) -> float:
        return self.account.cash
