from __future__ import annotations

from fastapi import APIRouter

from backtest.engine import Backtester
from backtest.metrics import bars_per_year, buy_and_hold_equity_curve, compute_metrics
from broker.paper_broker import PaperBroker
from data.ccxt_provider import CCXTHistoricalDataProvider
from rest.models import HistoricalBacktestRequest, HistoricalBacktestResponse, MetricsResponse
from risk.manager import RiskConfig, RiskManager
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy

router = APIRouter()


@router.post("/historical", response_model=HistoricalBacktestResponse)
def run_historical_backtest(request: HistoricalBacktestRequest) -> HistoricalBacktestResponse:
    """Run a single-symbol backtest against real historical ccxt data."""
    data_provider = CCXTHistoricalDataProvider(
        symbol=request.symbol,
        timeframe=request.timeframe,
        since=request.since,
        max_bars=request.max_bars,
        exchange_id=request.exchange,
    )
    strategy = MovingAverageCrossoverStrategy(
        symbol=request.symbol,
        fast_window=request.fast_window,
        slow_window=request.slow_window,
        min_separation_pct=request.min_separation_pct,
        adx_period=request.adx_period,
        adx_threshold=request.adx_threshold,
    )
    risk_manager = RiskManager(
        RiskConfig(
            max_drawdown_pct=request.max_drawdown_pct,
            max_position_pct=request.max_position_pct,
            max_total_exposure_pct=max(request.max_position_pct, RiskConfig().max_total_exposure_pct),
            risk_per_trade_pct=request.risk_per_trade_pct,
        )
    )
    broker = PaperBroker(initial_cash=request.cash, slippage_pct=request.slippage_pct)
    backtester = Backtester(strategy, risk_manager, broker)

    bars = list(data_provider.bars())
    equity_curve = backtester.run(bars)
    ppy = bars_per_year(request.timeframe)
    metrics = compute_metrics(equity_curve, broker.fills, request.cash, periods_per_year=ppy)

    bh_curve = buy_and_hold_equity_curve(bars, [request.symbol], request.cash)
    bh_metrics = compute_metrics(bh_curve, [], request.cash, periods_per_year=ppy)

    return HistoricalBacktestResponse(
        symbol=request.symbol,
        timeframe=request.timeframe,
        bars=len(equity_curve),
        strategy=MetricsResponse(**vars(metrics)),
        buy_and_hold=MetricsResponse(**vars(bh_metrics)),
        equity_curve=[(t.isoformat(), e) for t, e in equity_curve],
        buy_and_hold_curve=[(t.isoformat(), e) for t, e in bh_curve],
    )
