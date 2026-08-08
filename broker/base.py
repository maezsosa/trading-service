from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import Fill, Order


class Broker(ABC):
    """Abstract execution venue.

    A live implementation would call a real exchange/broker API here
    (e.g. via ccxt or a broker SDK) with the same interface used by
    PaperBroker, so strategies and risk rules don't change when going live.
    """

    @abstractmethod
    def submit_order(self, order: Order, mark_price: float) -> Fill:
        ...

    @abstractmethod
    def get_cash(self) -> float:
        ...
