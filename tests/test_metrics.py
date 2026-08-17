from datetime import datetime

import pytest

from backtest.metrics import bars_per_year, compute_metrics
from core.types import Fill, Side


def make_fill(realized_pnl: float | None) -> Fill:
    return Fill(
        timestamp=datetime(2024, 1, 1),
        symbol="TEST",
        side=Side.SELL,
        quantity=1.0,
        price=100.0,
        realized_pnl=realized_pnl,
    )


def test_bars_per_year_for_common_timeframes():
    assert bars_per_year("1d") == 365
    assert bars_per_year("1h") == 365 * 24
    assert bars_per_year("4h") == 365 * 6


def test_return_and_drawdown_from_equity_curve():
    equity_curve = [
        (datetime(2024, 1, 1), 10_000.0),
        (datetime(2024, 1, 2), 12_000.0),
        (datetime(2024, 1, 3), 9_000.0),  # 25% drawdown from the 12k peak
        (datetime(2024, 1, 4), 11_000.0),
    ]
    metrics = compute_metrics(equity_curve, fills=[], initial_cash=10_000.0)

    assert metrics.total_return_pct == pytest.approx(10.0)
    assert metrics.max_drawdown_pct == pytest.approx(25.0)


def test_trade_stats_from_fills_with_realized_pnl():
    fills = [
        make_fill(realized_pnl=None),  # opening fill, ignored
        make_fill(realized_pnl=100.0),
        make_fill(realized_pnl=-50.0),
        make_fill(realized_pnl=200.0),
        make_fill(realized_pnl=None),  # another opening fill
    ]
    metrics = compute_metrics([], fills, initial_cash=10_000.0)

    assert metrics.num_trades == 3
    assert metrics.win_rate_pct == pytest.approx(2 / 3 * 100)
    assert metrics.avg_win == 150.0
    assert metrics.avg_loss == -50.0
    assert metrics.profit_factor == pytest.approx(300.0 / 50.0)


def test_no_trades_leaves_trade_stats_as_none():
    metrics = compute_metrics([], fills=[], initial_cash=10_000.0)

    assert metrics.num_trades == 0
    assert metrics.win_rate_pct is None
    assert metrics.avg_win is None
    assert metrics.avg_loss is None
    assert metrics.profit_factor is None


def test_all_wins_gives_infinite_profit_factor():
    fills = [make_fill(realized_pnl=100.0), make_fill(realized_pnl=50.0)]
    metrics = compute_metrics([], fills, initial_cash=10_000.0)

    assert metrics.profit_factor == float("inf")


def test_sharpe_and_sortino_none_with_fewer_than_two_bars():
    metrics = compute_metrics([(datetime(2024, 1, 1), 10_000.0)], fills=[], initial_cash=10_000.0)

    assert metrics.sharpe_ratio is None
    assert metrics.sortino_ratio is None
