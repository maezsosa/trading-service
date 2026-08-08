from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import sleep as time_sleep
from typing import Any, Callable, Iterator, Optional

from core.types import Bar
from data.base import MarketDataProvider

logger = logging.getLogger("data.ccxt_provider")


def _build_exchange(exchange_id: str) -> Any:
    import ccxt  # imported lazily so ccxt is only required when actually used

    exchange_class = getattr(ccxt, exchange_id)
    return exchange_class({"enableRateLimit": True})


def _candle_to_bar(candle: list, symbol: str) -> Bar:
    timestamp_ms, open_, high, low, close, volume = candle
    return Bar(
        timestamp=datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc),
        symbol=symbol,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


class CCXTHistoricalDataProvider(MarketDataProvider):
    """Historical OHLCV bars from a real exchange via ccxt (paginated).

    Uses only public market-data endpoints — no API keys required.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[str] = None,
        limit: int = 500,
        max_bars: Optional[int] = None,
        exchange_id: str = "binance",
        exchange: Any = None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.limit = limit
        self.max_bars = max_bars
        self.exchange = exchange or _build_exchange(exchange_id)
        self._since_ms = self.exchange.parse8601(since) if since else None

    def bars(self) -> Iterator[Bar]:
        since_ms = self._since_ms
        yielded = 0
        while True:
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, timeframe=self.timeframe, since=since_ms, limit=self.limit
            )
            if not ohlcv:
                return

            for candle in ohlcv:
                yield _candle_to_bar(candle, self.symbol)
                yielded += 1
                if self.max_bars and yielded >= self.max_bars:
                    return

            if len(ohlcv) < self.limit:
                return
            since_ms = ohlcv[-1][0] + 1


class CCXTLiveDataProvider(MarketDataProvider):
    """Polls a real exchange via ccxt and yields a Bar each time a candle closes.

    Only yields the last *closed* candle (never the one still forming), so
    strategies see the same kind of data live as they saw in backtests.
    Public market data only — no API keys required for paper trading.
    """

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1m",
        poll_interval_seconds: float = 30.0,
        exchange_id: str = "binance",
        exchange: Any = None,
        sleep_fn: Callable[[float], None] = time_sleep,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.poll_interval_seconds = poll_interval_seconds
        self.exchange = exchange or _build_exchange(exchange_id)
        self._sleep = sleep_fn

    def bars(self) -> Iterator[Bar]:
        last_timestamp_ms: Optional[int] = None
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=2)
            except Exception as exc:
                # Transient network/exchange hiccups shouldn't kill a live session --
                # log and retry on the next poll instead of propagating.
                logger.warning("fetch_ohlcv failed for %s, will retry: %s", self.symbol, exc)
                self._sleep(self.poll_interval_seconds)
                continue

            if len(ohlcv) >= 2:
                closed_candle = ohlcv[-2]
                if closed_candle[0] != last_timestamp_ms:
                    last_timestamp_ms = closed_candle[0]
                    yield _candle_to_bar(closed_candle, self.symbol)
            self._sleep(self.poll_interval_seconds)
