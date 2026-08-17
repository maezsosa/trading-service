from __future__ import annotations

import argparse

from backtest.metrics import bars_per_year, compute_metrics, print_metrics
from broker.paper_broker import PaperBroker
from core.session import TradingSession
from data.ccxt_provider import CCXTHistoricalDataProvider
from risk.manager import RiskConfig, RiskManager
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest against real historical ccxt data.")
    parser.add_argument("--exchange", default="binance", help="ccxt exchange id (default: binance)")
    parser.add_argument("--symbol", default="BTC/USDT", help="trading pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", default="1h", help="candle timeframe (default: 1h)")
    parser.add_argument("--since", default=None, help="ISO8601 start date, e.g. 2024-01-01T00:00:00Z")
    parser.add_argument("--max-bars", type=int, default=None, help="cap on number of bars fetched")
    parser.add_argument("--cash", type=float, default=10_000.0, help="starting cash")
    parser.add_argument("--fast-window", type=int, default=10)
    parser.add_argument("--slow-window", type=int, default=30)
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=RiskConfig().max_drawdown_pct,
        help=f"kill switch: halt permanente al superar este drawdown desde el pico (default: {RiskConfig().max_drawdown_pct:.0%})",
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

    data_provider = CCXTHistoricalDataProvider(
        symbol=args.symbol,
        timeframe=args.timeframe,
        since=args.since,
        max_bars=args.max_bars,
        exchange_id=args.exchange,
    )
    strategy = MovingAverageCrossoverStrategy(
        symbol=args.symbol, fast_window=args.fast_window, slow_window=args.slow_window
    )
    risk_manager = RiskManager(RiskConfig(max_drawdown_pct=args.max_drawdown_pct))
    broker = PaperBroker(initial_cash=args.cash, slippage_pct=args.slippage_pct)
    session = TradingSession(strategy, risk_manager, broker)

    halt_triggered_at: tuple[int, object] | None = None
    for bar_number, bar in enumerate(data_provider.bars(), start=1):
        was_halted = risk_manager.halted
        session.process_bar(bar)
        if risk_manager.halted and not was_halted:
            halt_triggered_at = (bar_number, bar.timestamp)

    equity_curve = session.equity_curve
    final_equity = equity_curve[-1][1] if equity_curve else args.cash

    print(f"Exchange:             {args.exchange}")
    print(f"Symbol:               {args.symbol} ({args.timeframe})")
    print(f"Bars procesadas:      {len(equity_curve)}")
    print(f"Equity inicial:       ${args.cash:,.2f}")
    print(f"Equity final:         ${final_equity:,.2f}")
    metrics = compute_metrics(
        equity_curve, broker.fills, args.cash, periods_per_year=bars_per_year(args.timeframe)
    )
    print_metrics(metrics)
    print(f"Trades ejecutados:    {len(broker.fills)}")
    print(f"Kill switch activado: {risk_manager.halted} ({risk_manager.halt_reason or '-'})")
    if halt_triggered_at:
        bar_number, timestamp = halt_triggered_at
        print(f"  -> activado en barra #{bar_number} ({timestamp}), quedaron {len(equity_curve) - bar_number} barras sin operar")

    if args.verbose:
        print()
        print("Operaciones:")
        for fill in broker.fills:
            print(f"  {fill.timestamp}  {fill.side.value:4}  {fill.quantity:>10.4f} @ {fill.price:>10.2f}")


if __name__ == "__main__":
    main()
