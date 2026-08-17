from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Bar:
    """A single OHLCV candle for a symbol."""

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    """A strategy's opinion that a trade should happen. Not yet sized or risk-checked."""

    timestamp: datetime
    symbol: str
    side: Side
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    limit_price: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class Order:
    """A sized, risk-approved instruction ready to send to a broker.

    limit_price=None is a market order (fills immediately at whatever price
    it's submitted with). If set, the order rests unfilled until a bar's
    range touches limit_price, then fills at exactly that price.
    """

    timestamp: datetime
    symbol: str
    side: Side
    quantity: float
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    limit_price: float | None = None


@dataclass
class Fill:
    """Confirmation that an order was executed.

    realized_pnl is set only when this fill closed (all or part of) an
    existing position -- None for a fill that opened or added to one.
    """

    timestamp: datetime
    symbol: str
    side: Side
    quantity: float
    price: float
    realized_pnl: float | None = None


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    stop_loss_price: float | None = None
    take_profit_price: float | None = None

    @property
    def is_open(self) -> bool:
        return self.quantity != 0.0


@dataclass
class AccountState:
    """Mutable snapshot of cash, open positions, and risk bookkeeping."""

    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    equity_peak: float = 0.0
    realized_pnl_today: float = 0.0

    def equity(self, mark_prices: dict[str, float]) -> float:
        total = self.cash
        for symbol, position in self.positions.items():
            if position.is_open:
                price = mark_prices.get(symbol, position.avg_entry_price)
                total += position.quantity * price
        return total
