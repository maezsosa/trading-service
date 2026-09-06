from __future__ import annotations

import argparse

from backtest.engine import Backtester
from backtest.metrics import bars_per_year, buy_and_hold_equity_curve, compute_metrics, print_metrics
from broker.paper_broker import PaperBroker
from data.ccxt_provider import CCXTHistoricalDataProvider
from risk.manager import RiskConfig, RiskManager
from strategy.factory import STRATEGY_NAMES, buy_and_hold_sizing_warning, create_strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest against real historical ccxt data.")
    parser.add_argument("--exchange", default="binance", help="ccxt exchange id (default: binance)")
    parser.add_argument("--symbol", default="BTC/USDT", help="trading pair (default: BTC/USDT)")
    parser.add_argument("--timeframe", default="1h", help="candle timeframe (default: 1h)")
    parser.add_argument("--since", default=None, help="ISO8601 start date, e.g. 2024-01-01T00:00:00Z")
    parser.add_argument("--max-bars", type=int, default=None, help="cap on number of bars fetched")
    parser.add_argument("--cash", type=float, default=10_000.0, help="starting cash")
    parser.add_argument(
        "--strategy",
        choices=STRATEGY_NAMES,
        default="crossover",
        help="qué estrategia correr (default: crossover)",
    )
    parser.add_argument(
        "--stop-loss-pct",
        type=float,
        default=None,
        help="override del stop-loss de la estrategia elegida (default: el propio de cada estrategia)",
    )
    parser.add_argument("--fast-window", type=int, default=10, help="[crossover]")
    parser.add_argument("--slow-window", type=int, default=30, help="[crossover]")
    parser.add_argument(
        "--min-separation-pct",
        type=float,
        default=0.0,
        help="[crossover] filtro anti-whipsaw: separación mínima entre fast/slow SMA para confirmar la señal (ej. 0.01 = 1%%)",
    )
    parser.add_argument(
        "--adx-period",
        type=int,
        default=14,
        help="[crossover] ventana del ADX (default: 14)",
    )
    parser.add_argument(
        "--adx-threshold",
        type=float,
        default=0.0,
        help="[crossover] filtro de régimen: solo opera si ADX >= este valor (0 = desactivado, ej. 25 = solo tendencias fuertes)",
    )
    parser.add_argument("--entry-window", type=int, default=20, help="[donchian] ventana de entrada")
    parser.add_argument("--exit-window", type=int, default=10, help="[donchian] ventana de salida")
    parser.add_argument("--rsi-period", type=int, default=14, help="[rsi] período del RSI")
    parser.add_argument("--oversold", type=float, default=30.0, help="[rsi] umbral de sobreventa")
    parser.add_argument("--overbought", type=float, default=70.0, help="[rsi] umbral de sobrecompra")
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=RiskConfig().max_drawdown_pct,
        help=f"kill switch: halt permanente al superar este drawdown desde el pico (default: {RiskConfig().max_drawdown_pct:.0%})",
    )
    parser.add_argument(
        "--max-position-pct",
        type=float,
        default=RiskConfig().max_position_pct,
        help=f"tope de exposición en este símbolo (default: {RiskConfig().max_position_pct:.0%})",
    )
    parser.add_argument(
        "--risk-per-trade-pct",
        type=float,
        default=RiskConfig().risk_per_trade_pct,
        help=f"fracción de equity arriesgada por trade, vía la distancia al stop (default: {RiskConfig().risk_per_trade_pct:.0%})",
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

    warning = buy_and_hold_sizing_warning(args.strategy, args.max_position_pct, args.risk_per_trade_pct, args.stop_loss_pct)
    if warning:
        print(warning)
        print()

    data_provider = CCXTHistoricalDataProvider(
        symbol=args.symbol,
        timeframe=args.timeframe,
        since=args.since,
        max_bars=args.max_bars,
        exchange_id=args.exchange,
    )
    strategy = create_strategy(
        args.strategy,
        args.symbol,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        min_separation_pct=args.min_separation_pct,
        adx_period=args.adx_period,
        adx_threshold=args.adx_threshold,
        entry_window=args.entry_window,
        exit_window=args.exit_window,
        rsi_period=args.rsi_period,
        oversold=args.oversold,
        overbought=args.overbought,
        stop_loss_pct=args.stop_loss_pct,
    )
    risk_manager = RiskManager(
        RiskConfig(
            max_drawdown_pct=args.max_drawdown_pct,
            max_position_pct=args.max_position_pct,
            max_total_exposure_pct=max(args.max_position_pct, RiskConfig().max_total_exposure_pct),
            risk_per_trade_pct=args.risk_per_trade_pct,
        )
    )
    broker = PaperBroker(initial_cash=args.cash, slippage_pct=args.slippage_pct)
    backtester = Backtester(strategy, risk_manager, broker)

    bars = list(data_provider.bars())  # materialized once so it can also feed the buy-and-hold curve
    equity_curve = backtester.run(bars)
    final_equity = equity_curve[-1][1] if equity_curve else args.cash

    print(f"Estrategia:           {args.strategy}")
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
    if backtester.halted_at:
        bar_number, timestamp = backtester.halted_at
        print(f"  -> activado en barra #{bar_number} ({timestamp}), quedaron {len(equity_curve) - bar_number} barras sin operar")

    bh_curve = buy_and_hold_equity_curve(bars, [args.symbol], args.cash)
    bh_metrics = compute_metrics(bh_curve, [], args.cash, periods_per_year=bars_per_year(args.timeframe))
    print()
    print(f"Buy-and-hold ({args.symbol}):")
    print(f"  Retorno:             {bh_metrics.total_return_pct:.2f}%")
    print(f"  Max drawdown:        {bh_metrics.max_drawdown_pct:.2f}%")
    print(f"  vs. estrategia:      {metrics.total_return_pct - bh_metrics.total_return_pct:+.2f} puntos de retorno")

    if args.verbose:
        print()
        print("Operaciones:")
        for fill in broker.fills:
            print(f"  {fill.timestamp}  {fill.side.value:4}  {fill.quantity:>10.4f} @ {fill.price:>10.2f}")


if __name__ == "__main__":
    main()
