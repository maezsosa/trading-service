import itertools

from data.ccxt_provider import CCXTHistoricalDataProvider, CCXTLiveDataProvider


class ScriptedHistoricalExchange:
    """Fake ccxt exchange that hands out canned OHLCV pages, no network involved."""

    def __init__(self, pages):
        self._pages = list(pages)

    def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        if not self._pages:
            return []
        return self._pages.pop(0)

    def parse8601(self, iso):
        return 0


class ScriptedLiveExchange:
    """Fake ccxt exchange that hands out canned [prev, forming] responses per poll."""

    def __init__(self, responses):
        self._responses = list(responses)

    def fetch_ohlcv(self, symbol, timeframe="1m", limit=2):
        assert self._responses, "ran out of scripted responses"
        return self._responses.pop(0)


def test_historical_provider_paginates_until_short_page():
    page_1 = [[0, 1, 2, 0.5, 1.5, 10], [3_600_000, 1.5, 2, 1, 1.8, 5]]
    page_2 = [[7_200_000, 1.8, 2, 1.5, 1.9, 3]]
    exchange = ScriptedHistoricalExchange([page_1, page_2])

    provider = CCXTHistoricalDataProvider(symbol="BTC/USDT", limit=2, exchange=exchange)
    bars = list(provider.bars())

    assert len(bars) == 3
    assert [b.close for b in bars] == [1.5, 1.8, 1.9]


def test_historical_provider_respects_max_bars():
    page_1 = [[0, 1, 2, 0.5, 1.5, 10], [3_600_000, 1.5, 2, 1, 1.8, 5]]
    exchange = ScriptedHistoricalExchange([page_1])

    provider = CCXTHistoricalDataProvider(symbol="BTC/USDT", limit=2, max_bars=1, exchange=exchange)
    bars = list(provider.bars())

    assert len(bars) == 1


def test_live_provider_only_yields_newly_closed_candles():
    responses = [
        [[1000, 1, 2, 0.5, 1.5, 10], [1060, 1.5, 2, 1, 1.8, 5]],  # closed=1000, 1060 forming
        [[1000, 1, 2, 0.5, 1.5, 10], [1060, 1.5, 2.2, 1, 2.0, 8]],  # same closed candle again
        [[1060, 1.5, 2.2, 1, 2.0, 8], [1120, 2.0, 2.1, 1.9, 2.05, 3]],  # 1060 now closed
    ]
    exchange = ScriptedLiveExchange(responses)
    provider = CCXTLiveDataProvider(symbol="BTC/USDT", exchange=exchange, sleep_fn=lambda _seconds: None)

    bars = list(itertools.islice(provider.bars(), 2))

    assert [b.close for b in bars] == [1.5, 2.0]
