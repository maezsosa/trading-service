from __future__ import annotations

import csv
from datetime import datetime
from typing import Iterator

from core.types import Bar
from data.base import MarketDataProvider


class CSVDataProvider(MarketDataProvider):
    """Reads historical OHLCV bars from a CSV file.

    Expected columns: timestamp,open,high,low,close,volume
    """

    def __init__(self, path: str, symbol: str, timestamp_format: str = "%Y-%m-%d %H:%M:%S"):
        self.path = path
        self.symbol = symbol
        self.timestamp_format = timestamp_format

    def bars(self) -> Iterator[Bar]:
        with open(self.path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield Bar(
                    timestamp=datetime.strptime(row["timestamp"], self.timestamp_format),
                    symbol=self.symbol,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
