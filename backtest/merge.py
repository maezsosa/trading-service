from __future__ import annotations

import heapq
from typing import Iterable, Iterator

from core.types import Bar


def merge_bars(streams: Iterable[Iterable[Bar]]) -> Iterator[Bar]:
    """Merge multiple per-symbol Bar streams into one, sorted by timestamp.

    Each stream should already be chronologically sorted on its own (true
    of every MarketDataProvider here). Ties break by input order, so which
    symbol's bar comes first at an identical timestamp is deterministic but
    otherwise arbitrary.
    """
    heap: list[tuple] = []
    iterators = [iter(stream) for stream in streams]
    for index, it in enumerate(iterators):
        bar = next(it, None)
        if bar is not None:
            heapq.heappush(heap, (bar.timestamp, index, bar, it))

    while heap:
        _, index, bar, it = heapq.heappop(heap)
        yield bar
        next_bar = next(it, None)
        if next_bar is not None:
            heapq.heappush(heap, (next_bar.timestamp, index, next_bar, it))
