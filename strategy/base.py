from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import Bar, Signal


class Strategy(ABC):
    """Base class for pluggable strategies.

    A strategy only decides *whether* it wants to trade. It never sizes
    orders or touches the account directly — that's the RiskManager's job.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal | None:
        """Called once per new bar. Return a Signal to act, or None to hold."""
