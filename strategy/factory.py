from __future__ import annotations

from strategy.base import Strategy
from strategy.buy_and_hold import BuyAndHoldStrategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy
from strategy.rsi_mean_reversion import RSIMeanReversionStrategy
from strategy.trailing_reentry import TrailingReentryStrategy

STRATEGY_NAMES = ("crossover", "donchian", "rsi", "buy_and_hold", "trailing_reentry")

# Strategies whose stop_loss_pct is deliberately very wide (an
# approximation of "never sell" for a mostly-long strategy), which
# interacts badly with RiskManager's risk/stop_distance sizing formula
# unless risk_per_trade_pct is raised to compensate -- see
# wide_stop_sizing_warning().
_WIDE_STOP_DEFAULTS = {
    "buy_and_hold": BuyAndHoldStrategy(symbol="_").stop_loss_pct,
    "trailing_reentry": TrailingReentryStrategy(symbol="_").stop_loss_pct,
}


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
    trail_pct: float = 0.15,
    reentry_pct: float = 0.10,
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

    if name == "buy_and_hold":
        kwargs = {}
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return BuyAndHoldStrategy(symbol=symbol, **kwargs)

    if name == "trailing_reentry":
        kwargs = dict(trail_pct=trail_pct, reentry_pct=reentry_pct)
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return TrailingReentryStrategy(symbol=symbol, **kwargs)

    raise ValueError(f"unknown strategy '{name}', expected one of {STRATEGY_NAMES}")


def buy_and_hold_sizing_warning(
    strategy_name: str,
    max_position_pct: float,
    risk_per_trade_pct: float,
    stop_loss_pct: float | None = None,
) -> str | None:
    """Flag the classic trap: some mostly-long strategies (buy_and_hold,
    trailing_reentry) default to a deliberately wide stop_loss_pct as an
    approximation of "never sell on a stop" -- but RiskManager sizes off
    risk / stop_distance, so that wide stop with the usual small
    risk_per_trade_pct and max_position_pct defaults ends up barely
    invested at all, not holding the position the strategy implies.
    """
    if strategy_name not in _WIDE_STOP_DEFAULTS:
        return None

    effective_stop = stop_loss_pct if stop_loss_pct is not None else _WIDE_STOP_DEFAULTS[strategy_name]
    required_risk_per_trade_pct = max_position_pct * effective_stop
    if risk_per_trade_pct >= required_risk_per_trade_pct * 0.99:
        return None

    return (
        f"aviso: con --max-position-pct {max_position_pct:.0%} y --risk-per-trade-pct {risk_per_trade_pct:.0%}, "
        f"{strategy_name} va a quedar sub-invertida -- su stop ancho ({effective_stop:.0%}) necesita "
        f"risk_per_trade_pct >= max_position_pct * stop_loss_pct (~{required_risk_per_trade_pct:.0%}) "
        "para usar todo el capital permitido. Subí ambos flags."
    )
