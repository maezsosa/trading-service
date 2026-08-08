from __future__ import annotations

import logging

from core.session import TradingSession
from core.types import Bar
from data.base import MarketDataProvider
from strategy.base import Strategy
from risk.manager import RiskManager
from broker.paper_broker import PaperBroker

logger = logging.getLogger("paper_trading")


class PaperTradingRunner:
    """Runs a strategy against a live data feed with simulated execution.

    Uses the exact same Strategy, RiskManager and PaperBroker as the
    backtester — only the data source is live. Swapping PaperBroker for a
    real Broker implementation later is the only change needed to go live.
    """

    def __init__(
        self,
        strategy: Strategy,
        risk_manager: RiskManager,
        broker: PaperBroker,
        data_provider: MarketDataProvider,
    ):
        self.session = TradingSession(strategy, risk_manager, broker)
        self.data_provider = data_provider

    def run(self) -> None:
        logger.info("Starting paper trading for %s", self.session.strategy.symbol)
        try:
            for bar in self.data_provider.bars():
                was_halted = self.session.risk_manager.halted
                self.session.process_bar(bar)
                self._log_bar(bar)
                if self.session.risk_manager.halted and not was_halted:
                    logger.warning(
                        "KILL SWITCH TRIGGERED: %s -- no new positions will open "
                        "until risk_manager.reset_halt() is called",
                        self.session.risk_manager.halt_reason,
                    )
        except KeyboardInterrupt:
            logger.info("Stopped by user")
        finally:
            self._log_summary()

    def _log_bar(self, bar: Bar) -> None:
        equity = self.session.equity_curve[-1][1] if self.session.equity_curve else 0.0
        logger.info(
            "%s %s close=%.2f equity=%.2f trades=%d",
            bar.timestamp.isoformat(),
            bar.symbol,
            bar.close,
            equity,
            len(self.session.broker.fills),
        )

    def _log_summary(self) -> None:
        broker = self.session.broker
        equity_curve = self.session.equity_curve
        final_equity = equity_curve[-1][1] if equity_curve else broker.get_cash()
        logger.info(
            "Session ended. cash=%.2f equity=%.2f trades=%d halted=%s",
            broker.get_cash(),
            final_equity,
            len(broker.fills),
            self.session.risk_manager.halted,
        )
