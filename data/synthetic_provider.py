from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Iterator

from core.types import Bar
from data.base import MarketDataProvider


class SyntheticDataProvider(MarketDataProvider):
    """Generates a random-walk OHLCV series.

    Useful for smoke-testing the pipeline end-to-end without needing
    real historical data or network access.
    """

    def __init__(
        self,
        symbol: str,
        num_bars: int = 500,
        start_price: float = 100.0,
        volatility: float = 0.01,
        seed: int | None = 42,
    ):
        self.symbol = symbol
        self.num_bars = num_bars
        self.start_price = start_price
        self.volatility = volatility
        self._rng = random.Random(seed)

    def bars(self) -> Iterator[Bar]:
        price = self.start_price
        timestamp = datetime(2024, 1, 1)
        for _ in range(self.num_bars):
            change = self._rng.gauss(0, self.volatility)
            open_price = price
            close_price = max(0.01, open_price * (1 + change))
            wick = abs(self._rng.gauss(0, self.volatility / 2))
            high = max(open_price, close_price) * (1 + wick)
            low = min(open_price, close_price) * (1 - wick)
            volume = abs(self._rng.gauss(1000, 200))

            yield Bar(
                timestamp=timestamp,
                symbol=self.symbol,
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume,
            )

            price = close_price
            timestamp += timedelta(hours=1)
