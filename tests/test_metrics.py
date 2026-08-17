from datetime import datetime, timedelta

import pytest

from backtest.metrics import bars_per_year, buy_and_hold_equity_curve, compute_metrics
from core.types import Bar, Fill, Side


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


def make_bar(symbol: str, timestamp: datetime, open_: float, close: float) -> Bar:
    return Bar(
        timestamp=timestamp, symbol=symbol, open=open_, high=close, low=open_, close=close, volume=1.0
    )


def test_buy_and_hold_tracks_a_single_symbols_price():
    t0 = datetime(2024, 1, 1)
    bars = [
        make_bar("TEST", t0, open_=100.0, close=100.0),
        make_bar("TEST", t0 + timedelta(hours=1), open_=100.0, close=110.0),
        make_bar("TEST", t0 + timedelta(hours=2), open_=110.0, close=120.0),
    ]

    curve = buy_and_hold_equity_curve(bars, symbols=["TEST"], initial_cash=10_000.0)

    assert [equity for _, equity in curve] == pytest.approx([10_000.0, 11_000.0, 12_000.0])


def test_buy_and_hold_splits_cash_evenly_across_symbols():
    t0 = datetime(2024, 1, 1)
    bars = [
        make_bar("AAA", t0, open_=100.0, close=100.0),
        make_bar("BBB", t0 + timedelta(hours=1), open_=200.0, close=200.0),
        make_bar("AAA", t0 + timedelta(hours=2), open_=100.0, close=150.0),  # AAA +50%
        make_bar("BBB", t0 + timedelta(hours=3), open_=200.0, close=100.0),  # BBB -50%
    ]

    curve = buy_and_hold_equity_curve(bars, symbols=["AAA", "BBB"], initial_cash=10_000.0)

    # $5k in each symbol; a +50% and a -50% leg cancel out back to $10k.
    assert curve[-1][1] == pytest.approx(10_000.0)
