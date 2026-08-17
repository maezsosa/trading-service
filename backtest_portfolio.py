from __future__ import annotations

import argparse

from backtest.engine import Backtester
from backtest.merge import merge_bars
from backtest.metrics import bars_per_year, compute_metrics, print_metrics
from broker.paper_broker import PaperBroker
from data.ccxt_provider import CCXTHistoricalDataProvider
from risk.manager import RiskConfig, RiskManager
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-symbol portfolio backtest against real historical ccxt data.")
    parser.add_argument("--exchange", default="binance", help="ccxt exchange id (default: binance)")
    parser.add_argument(
        "--symbols",
        default="BTC/USDT,ETH/USDT",
        help="comma-separated trading pairs (default: BTC/USDT,ETH/USDT)",
    )
    parser.add_argument("--timeframe", default="1d", help="candle timeframe (default: 1d)")
    parser.add_argument("--since", default=None, help="ISO8601 start date, e.g. 2024-01-01T00:00:00Z")
    parser.add_argument("--max-bars", type=int, default=None, help="cap on bars fetched, per symbol")
    parser.add_argument("--cash", type=float, default=10_000.0, help="starting cash, shared across the portfolio")
    parser.add_argument("--fast-window", type=int, default=10)
    parser.add_argument("--slow-window", type=int, default=30)
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=RiskConfig().max_drawdown_pct,
        help=f"kill switch: halt permanente al superar este drawdown desde el pico (default: {RiskConfig().max_drawdown_pct:.0%})",
    )
    parser.add_argument(
        "--max-total-exposure-pct",
        type=float,
        default=RiskConfig().max_total_exposure_pct,
        help=f"tope de exposición combinada del portfolio (default: {RiskConfig().max_total_exposure_pct:.0%})",
    )
    parser.add_argument(
        "--slippage-pct",
        type=float,
        default=0.0,
        help="slippage simulado por fill, como fracción (ej. 0.001 = 0.1%%)",
    )
    parser.add_argument("--verbose", action="store_true", help="listar cada trade ejecutado")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    data_providers = [
        CCXTHistoricalDataProvider(
            symbol=symbol,
            timeframe=args.timeframe,
            since=args.since,
            max_bars=args.max_bars,
            exchange_id=args.exchange,
        )
        for symbol in symbols
    ]
    strategies = [
        MovingAverageCrossoverStrategy(symbol=symbol, fast_window=args.fast_window, slow_window=args.slow_window)
        for symbol in symbols
    ]
    risk_manager = RiskManager(
        RiskConfig(max_drawdown_pct=args.max_drawdown_pct, max_total_exposure_pct=args.max_total_exposure_pct)
    )
    broker = PaperBroker(initial_cash=args.cash, slippage_pct=args.slippage_pct)
    backtester = Backtester(strategy=strategies, risk_manager=risk_manager, broker=broker)

    bars = merge_bars(provider.bars() for provider in data_providers)
    equity_curve = backtester.run(bars)

    final_equity = equity_curve[-1][1] if equity_curve else args.cash

    print(f"Exchange:             {args.exchange}")
    print(f"Symbols:              {', '.join(symbols)} ({args.timeframe})")
    print(f"Bars procesadas:      {len(equity_curve)}")
    print(f"Equity inicial:       ${args.cash:,.2f}")
    print(f"Equity final:         ${final_equity:,.2f}")
    metrics = compute_metrics(
        equity_curve, broker.fills, args.cash, periods_per_year=bars_per_year(args.timeframe)
    )
    print_metrics(metrics)
    print(f"Trades ejecutados:    {len(broker.fills)}")
    print(f"Kill switch activado: {risk_manager.halted} ({risk_manager.halt_reason or '-'})")

    print()
    print("Trades por símbolo:")
    for symbol in symbols:
        count = sum(1 for fill in broker.fills if fill.symbol == symbol)
        position = broker.account.positions.get(symbol)
        open_qty = position.quantity if position else 0.0
        print(f"  {symbol:12} trades={count:<4} posición abierta={open_qty:.6f}")

    if args.verbose:
        print()
        print("Operaciones:")
        for fill in broker.fills:
            print(f"  {fill.timestamp}  {fill.symbol:10}  {fill.side.value:4}  {fill.quantity:>10.4f} @ {fill.price:>10.2f}")


if __name__ == "__main__":
    main()
