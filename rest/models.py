from __future__ import annotations

from pydantic import BaseModel, Field

from risk.manager import RiskConfig


class HistoricalBacktestRequest(BaseModel):
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "1d"
    since: str | None = None
    max_bars: int | None = None
    cash: float = 10_000.0
    strategy: str = "crossover"  # "crossover" | "donchian" | "rsi" | "buy_and_hold" | "trailing_reentry"
    stop_loss_pct: float | None = None
    fast_window: int = Field(default=10, ge=1)
    slow_window: int = Field(default=30, ge=1)
    min_separation_pct: float = 0.0
    adx_period: int = Field(default=14, ge=1)
    adx_threshold: float = 0.0
    entry_window: int = Field(default=20, ge=1)
    exit_window: int = Field(default=10, ge=1)
    rsi_period: int = Field(default=14, ge=1)
    oversold: float = 30.0
    overbought: float = 70.0
    trail_pct: float = 0.15
    reentry_pct: float = 0.10
    max_position_pct: float = RiskConfig().max_position_pct
    risk_per_trade_pct: float = RiskConfig().risk_per_trade_pct
    max_drawdown_pct: float = RiskConfig().max_drawdown_pct
    slippage_pct: float = 0.0


class MetricsResponse(BaseModel):
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    num_trades: int
    win_rate_pct: float | None
    avg_win: float | None
    avg_loss: float | None
    profit_factor: float | None


class HistoricalBacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    bars: int
    strategy: MetricsResponse
    buy_and_hold: MetricsResponse
    equity_curve: list[tuple[str, float]]
    buy_and_hold_curve: list[tuple[str, float]]
