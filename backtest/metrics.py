from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable, Sequence

from core.types import Bar, Fill

_SECONDS_PER_UNIT = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
_SECONDS_PER_YEAR = 365 * 86400  # crypto markets trade 24/7, unlike max_bars-style equities conventions


def bars_per_year(timeframe: str) -> float:
    """Bars per year implied by a ccxt-style timeframe string (e.g. "1h", "4h", "1d")."""
    value = int(timeframe[:-1])
    unit = timeframe[-1]
    seconds_per_bar = value * _SECONDS_PER_UNIT[unit]
    return _SECONDS_PER_YEAR / seconds_per_bar


@dataclass
class PerformanceMetrics:
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    num_trades: int
    win_rate_pct: float | None
    avg_win: float | None
    avg_loss: float | None
    profit_factor: float | None


def compute_metrics(
    equity_curve: list[tuple],
    fills: list[Fill],
    initial_cash: float,
    periods_per_year: float = 252,
) -> PerformanceMetrics:
    """Summarize a backtest run from its equity curve and fills.

    periods_per_year annualizes Sharpe/Sortino and should match the bar
    frequency of equity_curve (see bars_per_year() for ccxt timeframes).
    """
    equities = [equity for _, equity in equity_curve]
    final_equity = equities[-1] if equities else initial_cash
    total_return_pct = (final_equity / initial_cash - 1) * 100 if initial_cash else 0.0

    peak = 0.0
    max_drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)

    sharpe_ratio = None
    sortino_ratio = None
    if len(equities) >= 2:
        returns = [
            equities[i] / equities[i - 1] - 1
            for i in range(1, len(equities))
            if equities[i - 1] > 0
        ]
        if len(returns) >= 2:
            mean_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            if std_return > 0:
                sharpe_ratio = mean_return / std_return * (periods_per_year**0.5)

            downside_deviation = (sum(min(r, 0.0) ** 2 for r in returns) / len(returns)) ** 0.5
            if downside_deviation > 0:
                sortino_ratio = mean_return / downside_deviation * (periods_per_year**0.5)

    realized = [fill.realized_pnl for fill in fills if fill.realized_pnl is not None]
    wins = [pnl for pnl in realized if pnl > 0]
    losses = [pnl for pnl in realized if pnl < 0]
    num_trades = len(realized)

    win_rate_pct = (len(wins) / num_trades * 100) if num_trades else None
    avg_win = statistics.mean(wins) if wins else None
    avg_loss = statistics.mean(losses) if losses else None
    gross_loss = abs(sum(losses))
    if losses and gross_loss > 0:
        profit_factor = sum(wins) / gross_loss
    elif wins:
        profit_factor = float("inf")
    else:
        profit_factor = None

    return PerformanceMetrics(
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown * 100,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        num_trades=num_trades,
        win_rate_pct=win_rate_pct,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
    )


def buy_and_hold_equity_curve(
    bars: Iterable[Bar], symbols: Sequence[str], initial_cash: float
) -> list[tuple]:
    """What initial_cash would be worth just buying and holding, for comparison.

    Splits initial_cash equally across symbols, "buying" each the moment its
    first bar appears (at that bar's open) and marking to the last known
    close from then on -- same last-known-price approach TradingSession uses
    for its own equity curve, so the two are computed consistently.
    """
    cash_per_symbol = initial_cash / len(symbols) if symbols else 0.0
    quantities: dict[str, float] = {}
    last_price: dict[str, float] = {}
    curve: list[tuple] = []

    for bar in bars:
        if bar.symbol not in quantities and bar.symbol in symbols:
            quantities[bar.symbol] = cash_per_symbol / bar.open if bar.open > 0 else 0.0
        if bar.symbol in quantities:
            last_price[bar.symbol] = bar.close
        equity = sum(quantities[symbol] * last_price[symbol] for symbol in quantities)
        curve.append((bar.timestamp, equity))

    return curve


def _fmt(value: float | None, suffix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "N/A (sin trades cerrados)"
    return f"{value:.{decimals}f}{suffix}"


def print_metrics(metrics: PerformanceMetrics) -> None:
    print(f"Retorno:              {metrics.total_return_pct:.2f}%")
    print(f"Max drawdown:         {metrics.max_drawdown_pct:.2f}%")
    print(f"Sharpe ratio:         {_fmt(metrics.sharpe_ratio)}")
    print(f"Sortino ratio:        {_fmt(metrics.sortino_ratio)}")
    print(f"Trades cerrados:      {metrics.num_trades}")
    print(f"Win rate:             {_fmt(metrics.win_rate_pct, '%')}")
    print(f"Avg win / avg loss:   {_fmt(metrics.avg_win)} / {_fmt(metrics.avg_loss)}")
    print(f"Profit factor:        {_fmt(metrics.profit_factor)}")
