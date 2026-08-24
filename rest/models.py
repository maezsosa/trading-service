from __future__ import annotations

from pydantic import BaseModel

from risk.manager import RiskConfig


class HistoricalBacktestRequest(BaseModel):
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "1d"
    since: str | None = None
    max_bars: int | None = None
    cash: float = 10_000.0
    fast_window: int = 10
    slow_window: int = 30
    min_separation_pct: float = 0.0
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
