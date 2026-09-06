from __future__ import annotations

import argparse

from backtest.engine import Backtester
from backtest.merge import merge_bars
from backtest.metrics import bars_per_year, buy_and_hold_equity_curve, compute_metrics, print_metrics
from broker.paper_broker import PaperBroker
from data.ccxt_provider import CCXTHistoricalDataProvider
from risk.manager import RiskConfig, RiskManager
from strategy.factory import STRATEGY_NAMES, buy_and_hold_sizing_warning, create_strategy


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
    parser.add_argument(
        "--strategy",
        choices=STRATEGY_NAMES,
        default="crossover",
        help="qué estrategia correr en cada símbolo (default: crossover)",
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
        "--max-total-exposure-pct",
        type=float,
        default=RiskConfig().max_total_exposure_pct,
        help=f"tope de exposición combinada del portfolio (default: {RiskConfig().max_total_exposure_pct:.0%})",
    )
    parser.add_argument(
        "--max-position-pct",
        type=float,
        default=RiskConfig().max_position_pct,
        help=f"tope de exposición por símbolo individual (default: {RiskConfig().max_position_pct:.0%})",
    )
    parser.add_argument(
        "--risk-per-trade-pct",
        type=float,
        default=RiskConfig().risk_per_trade_pct,
        help=f"fracción de equity arriesgada por trade, vía la distancia al stop (default: {RiskConfig().risk_per_trade_pct:.0%})",
    )
    parser.add_argument(
        "--correlated-groups",
        default=None,
        help='símbolos que se mueven juntos, ej. "BTC/USDT:crypto,ETH/USDT:crypto"',
    )
    parser.add_argument(
        "--max-group-exposure-pct",
        type=float,
        default=None,
        help="tope de exposición combinada dentro de un mismo grupo correlacionado (requiere --correlated-groups)",
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

    warning = buy_and_hold_sizing_warning(args.strategy, args.max_position_pct, args.risk_per_trade_pct, args.stop_loss_pct)
    if warning:
        print(warning)
        print()

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
        create_strategy(
            args.strategy,
            symbol,
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
        for symbol in symbols
    ]
    correlated_groups = {}
    if args.correlated_groups:
        for pair in args.correlated_groups.split(","):
            symbol, _, group = pair.strip().partition(":")
            correlated_groups[symbol] = group

    risk_manager = RiskManager(
        RiskConfig(
            max_drawdown_pct=args.max_drawdown_pct,
            max_total_exposure_pct=args.max_total_exposure_pct,
            max_position_pct=args.max_position_pct,
            risk_per_trade_pct=args.risk_per_trade_pct,
            correlated_groups=correlated_groups,
            max_group_exposure_pct=args.max_group_exposure_pct,
        )
    )
    broker = PaperBroker(initial_cash=args.cash, slippage_pct=args.slippage_pct)
    backtester = Backtester(strategy=strategies, risk_manager=risk_manager, broker=broker)

    bars = list(merge_bars(provider.bars() for provider in data_providers))
    equity_curve = backtester.run(bars)

    final_equity = equity_curve[-1][1] if equity_curve else args.cash

    print(f"Estrategia:           {args.strategy}")
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

    bh_curve = buy_and_hold_equity_curve(bars, symbols, args.cash)
    bh_metrics = compute_metrics(bh_curve, [], args.cash, periods_per_year=bars_per_year(args.timeframe))
    print()
    print(f"Buy-and-hold (cash repartido parejo entre {', '.join(symbols)}):")
    print(f"  Retorno:             {bh_metrics.total_return_pct:.2f}%")
    print(f"  Max drawdown:        {bh_metrics.max_drawdown_pct:.2f}%")
    print(f"  vs. estrategia:      {metrics.total_return_pct - bh_metrics.total_return_pct:+.2f} puntos de retorno")

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
