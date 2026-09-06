from __future__ import annotations

from strategy.base import Strategy
from strategy.buy_and_hold import BuyAndHoldStrategy
from strategy.donchian_breakout import DonchianBreakoutStrategy
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy
from strategy.rsi_mean_reversion import RSIMeanReversionStrategy

STRATEGY_NAMES = ("crossover", "donchian", "rsi", "buy_and_hold")


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

    if name == "buy_and_hold":
        kwargs = {}
        if stop_loss_pct is not None:
            kwargs["stop_loss_pct"] = stop_loss_pct
        return BuyAndHoldStrategy(symbol=symbol, **kwargs)

    raise ValueError(f"unknown strategy '{name}', expected one of {STRATEGY_NAMES}")


def buy_and_hold_sizing_warning(
    strategy_name: str,
    max_position_pct: float,
    risk_per_trade_pct: float,
    stop_loss_pct: float | None = None,
) -> str | None:
    """Flag the classic trap: BuyAndHoldStrategy's stop is deliberately wide
    (so it approximates never selling), but RiskManager sizes off risk /
    stop_distance -- a wide stop with the usual small risk_per_trade_pct
    and max_position_pct defaults ends up barely invested at all, not
    holding the full position the strategy name implies.
    """
    if strategy_name != "buy_and_hold":
        return None

    effective_stop = stop_loss_pct if stop_loss_pct is not None else BuyAndHoldStrategy(symbol="_").stop_loss_pct
    required_risk_per_trade_pct = max_position_pct * effective_stop
    if risk_per_trade_pct >= required_risk_per_trade_pct * 0.99:
        return None

    return (
        f"aviso: con --max-position-pct {max_position_pct:.0%} y --risk-per-trade-pct {risk_per_trade_pct:.0%}, "
        f"buy_and_hold va a quedar sub-invertido -- su stop ancho ({effective_stop:.0%}) necesita "
        f"risk_per_trade_pct >= max_position_pct * stop_loss_pct (~{required_risk_per_trade_pct:.0%}) "
        "para usar todo el capital permitido. Subí ambos flags para aproximar un buy-and-hold real."
    )
