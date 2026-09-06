from __future__ import annotations

from strategy.base import Strategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy
from strategy.rsi_mean_reversion import RSIMeanReversionStrategy

STRATEGY_NAMES = ("crossover", "donchian", "rsi")


def create_strategy(
    name: str,
    symbol: str,
    *,
    fast_window: int = 10,
    slow_window: int = 30,
    min_separation_pct: float = 0.0,
    adx_period: int = 14,
    adx_threshold: float = 0.0,
    entry_window: int = 20,
    exit_window: int = 10,
    rsi_period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    stop_loss_pct: float | None = None,
) -> Strategy:
    """Build a Strategy by name from one flat parameter set.

    Callers (CLI, API) can pass every parameter unconditionally -- each
    branch below only reads the ones its own strategy takes, so the
    others are silently ignored rather than needing per-strategy call
    sites. stop_loss_pct is left as each strategy's own class default
    unless explicitly given, since a sensible default differs a lot
    between a tight mean-reversion stop and a wide breakout one.
    """
    if name == "crossover":
        kwargs: dict = dict(
            fast_window=fast_window,
            slow_window=slow_window,
            min_separation_pct=min_separation_pct,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
        )
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return MovingAverageCrossoverStrategy(symbol=symbol, **kwargs)

    if name == "donchian":
        kwargs = dict(entry_window=entry_window, exit_window=exit_window)
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return DonchianBreakoutStrategy(symbol=symbol, **kwargs)

    if name == "rsi":
        kwargs = dict(rsi_period=rsi_period, oversold=oversold, overbought=overbought)
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return RSIMeanReversionStrategy(symbol=symbol, **kwargs)

    raise ValueError(f"unknown strategy '{name}', expected one of {STRATEGY_NAMES}")
