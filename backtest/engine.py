from __future__ import annotations

from typing import Iterable, Sequence

from core.session import TradingSession
from core.types import Bar
from strategy.base import Strategy
from risk.manager import RiskManager
from broker.paper_broker import PaperBroker


class Backtester:
    """Replays historical bars through a TradingSession.

    Pass a single Strategy for a single-symbol backtest, or a sequence of
    Strategy instances for a multi-symbol portfolio backtest -- feed it
    bars merged chronologically across symbols (see backtest.merge.merge_bars).
    """

    def __init__(
        self,
        strategy: Strategy | Sequence[Strategy],
        risk_manager: RiskManager,
        broker: PaperBroker,
    ):
        self.risk_manager = risk_manager
        self.broker = broker
        self._session = TradingSession(strategy, risk_manager, broker)

    @property
    def equity_curve(self) -> list[tuple]:
        return self._session.equity_curve

    def run(self, bars: Iterable[Bar]) -> list[tuple]:
        for bar in bars:
            self._session.process_bar(bar)
        return self._session.equity_curve
