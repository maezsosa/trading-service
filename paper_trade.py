from __future__ import annotations

import argparse
import logging

from broker.paper_broker import PaperBroker
from data.ccxt_provider import CCXTLiveDataProvider
from live.paper_runner import PaperTradingRunner
from risk.manager import RiskConfig, RiskManager
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paper trading against a live ccxt feed.")
    parser.add_argument("--exchange", default="binance", help="ccxt exchange id (default: binance)")
    parser.add_argument("--symbol", default="BTC/USDT", help="trading pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", default="1m", help="candle timeframe (default: 1m)")
    parser.add_argument(
        "--poll-interval", type=float, default=30.0, help="seconds between exchange polls"
    )
    parser.add_argument("--cash", type=float, default=10_000.0, help="starting paper cash")
    parser.add_argument("--fast-window", type=int, default=10)
    parser.add_argument("--slow-window", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    data_provider = CCXTLiveDataProvider(
        symbol=args.symbol,
        timeframe=args.timeframe,
        poll_interval_seconds=args.poll_interval,
        exchange_id=args.exchange,
    )
    strategy = MovingAverageCrossoverStrategy(
        symbol=args.symbol, fast_window=args.fast_window, slow_window=args.slow_window
    )
    risk_manager = RiskManager(RiskConfig())
    broker = PaperBroker(initial_cash=args.cash)

    runner = PaperTradingRunner(strategy, risk_manager, broker, data_provider)
    runner.run()


if __name__ == "__main__":
    main()
