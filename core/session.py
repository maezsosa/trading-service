from __future__ import annotations

from dataclasses import replace

from core.types import Bar, Order, Side, Signal
from strategy.base import Strategy
from risk.manager import RiskManager
from broker.paper_broker import PaperBroker


class TradingSession:
    """Processes one bar at a time through strategy -> risk manager -> broker.

    Shared by the historical Backtester and the live PaperTradingRunner so a
    strategy behaves identically whether it's replaying history or trading
    against a live feed — only the source of bars and the broker change.

    A signal generated from bar N's close is never filled on bar N itself —
    that would assume trading at a price the moment it prints, with zero
    latency and zero slippage. Instead it's queued and executed at bar N+1's
    open, the earliest realistic fill.
    """

    def __init__(self, strategy: Strategy, risk_manager: RiskManager, broker: PaperBroker):
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.broker = broker
        self.equity_curve: list[tuple] = []
        self._current_day = None
        self._pending_signal: Signal | None = None
        self._pending_limit_orders: list[Order] = []

    def process_bar(self, bar: Bar) -> None:
        if self._current_day is not None and bar.timestamp.date() != self._current_day:
            self.broker.account.realized_pnl_today = 0.0
        self._current_day = bar.timestamp.date()

        self._check_stop_loss(bar)
        self._check_take_profit(bar)
        self._check_pending_limit_orders(bar)
        self._execute_pending_signal(bar)

        self._pending_signal = self.strategy.on_bar(bar)

        equity = self.broker.account.equity({bar.symbol: bar.close})
        self.equity_curve.append((bar.timestamp, equity))

    def _execute_pending_signal(self, bar: Bar) -> None:
        signal = self._pending_signal
        self._pending_signal = None
        if signal is None:
            return

        # A fresh signal supersedes any stale resting limit order left over
        # from an earlier, now-outdated signal on the same symbol.
        self._pending_limit_orders = [
            order for order in self._pending_limit_orders if order.symbol != signal.symbol
        ]

        execution_price = bar.open
        self._flatten_opposing_position(signal, execution_price, bar.timestamp)
        order = self.risk_manager.validate(signal, self.broker.account, execution_price)
        if order is None:
            return

        order = replace(order, timestamp=bar.timestamp)
        if order.limit_price is not None:
            self._pending_limit_orders.append(order)
        else:
            self.broker.submit_order(order, execution_price)

    def _check_pending_limit_orders(self, bar: Bar) -> None:
        still_pending = []
        for order in self._pending_limit_orders:
            if order.symbol != bar.symbol:
                still_pending.append(order)
                continue

            triggered = (order.side == Side.BUY and bar.low <= order.limit_price) or (
                order.side == Side.SELL and bar.high >= order.limit_price
            )
            if triggered:
                self.broker.submit_order(order, order.limit_price, apply_slippage=False)
            else:
                still_pending.append(order)

        self._pending_limit_orders = still_pending

    def _flatten_opposing_position(self, signal: Signal, mark_price: float, timestamp) -> None:
        """Close any existing position that sits opposite to a new signal.

        Sized to exactly the open quantity (not the risk-based sizing
        formula) so a reversal always nets to zero instead of leaving a
        stray residual position behind. The fresh entry, if any, is then
        sized by risk_manager.validate() from a clean, flat base.
        """
        position = self.broker.account.positions.get(signal.symbol)
        if position is None or not position.is_open:
            return

        is_opposing = (position.quantity > 0 and signal.side == Side.SELL) or (
            position.quantity < 0 and signal.side == Side.BUY
        )
        if not is_opposing:
            return

        closing_side = Side.SELL if position.quantity > 0 else Side.BUY
        order = Order(
            timestamp=timestamp,
            symbol=signal.symbol,
            side=closing_side,
            quantity=abs(position.quantity),
        )
        self.broker.submit_order(order, mark_price)

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

    def _check_take_profit(self, bar: Bar) -> None:
        position = self.broker.account.positions.get(bar.symbol)
        if position is None or not position.is_open or position.take_profit_price is None:
            return

        hit = (position.quantity > 0 and bar.high >= position.take_profit_price) or (
            position.quantity < 0 and bar.low <= position.take_profit_price
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
        self.broker.submit_order(order, position.take_profit_price)
