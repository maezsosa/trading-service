from __future__ import annotations

import argparse

from data.synthetic_provider import SyntheticDataProvider
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy
from risk.manager import RiskConfig, RiskManager
from broker.paper_broker import PaperBroker
from backtest.engine import Backtester
from backtest.metrics import bars_per_year, compute_metrics, print_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Listar cada trade ejecutado")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed para la serie sintética (mismo seed = mismos datos). Ej: --seed 7",
    )
    parser.add_argument(
        "--slippage-pct",
        type=float,
        default=0.0,
        help="Slippage simulado por fill, como fracción (ej. 0.001 = 0.1%%)",
    )
    args = parser.parse_args()

    symbol = "SYNTH/USD"
    initial_cash = 10_000.0

    data_provider = SyntheticDataProvider(symbol=symbol, num_bars=500, seed=args.seed)
    strategy = MovingAverageCrossoverStrategy(symbol=symbol, fast_window=10, slow_window=30)
    risk_manager = RiskManager(RiskConfig())
    broker = PaperBroker(initial_cash=initial_cash, slippage_pct=args.slippage_pct)
    backtester = Backtester(strategy=strategy, risk_manager=risk_manager, broker=broker)

    equity_curve = backtester.run(data_provider.bars())
    final_equity = equity_curve[-1][1] if equity_curve else initial_cash

    print(f"Seed:                 {args.seed}")
    print(f"Bars procesadas:      {len(equity_curve)}")
    print(f"Equity inicial:       ${initial_cash:,.2f}")
    print(f"Equity final:         ${final_equity:,.2f}")
    metrics = compute_metrics(
        equity_curve, broker.fills, initial_cash, periods_per_year=bars_per_year("1h")
    )
    print_metrics(metrics)
    print(f"Trades ejecutados:    {len(broker.fills)}")
    print(f"Kill switch activado: {risk_manager.halted} ({risk_manager.halt_reason or '-'})")

    if args.verbose:
        print()
        print("Operaciones:")
        for fill in broker.fills:
            print(f"  {fill.timestamp}  {fill.side.value:4}  {fill.quantity:>10.4f} @ {fill.price:>10.2f}")


if __name__ == "__main__":
    main()
