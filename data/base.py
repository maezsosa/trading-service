from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from core.types import Bar


class MarketDataProvider(ABC):
    """Abstract source of bars (historical or live) for a single symbol.

    Concrete implementations can wrap a CSV file, a synthetic generator,
    or a real exchange/broker feed (e.g. via ccxt) without the rest of
    the system needing to change.
    """

    @abstractmethod
    def bars(self) -> Iterator[Bar]:
        ...
