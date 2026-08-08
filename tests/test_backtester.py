from broker.paper_broker import PaperBroker
from backtest.engine import Backtester
from data.synthetic_provider import SyntheticDataProvider
from risk.manager import RiskConfig, RiskManager
from strategy.moving_average_crossover import MovingAverageCrossoverStrategy


def run_backtest(risk_config: RiskConfig, num_bars: int = 300, volatility: float = 0.01, seed: int = 1):
    symbol = "TEST/USD"
    provider = SyntheticDataProvider(symbol=symbol, num_bars=num_bars, volatility=volatility, seed=seed)
    strategy = MovingAverageCrossoverStrategy(symbol=symbol, fast_window=5, slow_window=15)
    risk_manager = RiskManager(risk_config)
    broker = PaperBroker(initial_cash=10_000.0)
    backtester = Backtester(strategy=strategy, risk_manager=risk_manager, broker=broker)

    equity_curve = backtester.run(provider.bars())
    return equity_curve, broker, risk_manager


def test_backtester_runs_end_to_end_and_tracks_equity_for_every_bar():
    equity_curve, broker, _ = run_backtest(RiskConfig(), num_bars=200)

    assert len(equity_curve) == 200
    assert all(equity > 0 for _, equity in equity_curve)


def test_backtester_stops_trading_once_kill_switch_trips():
    # Deliberately aggressive sizing + tight drawdown limit to force a halt.
    risk_config = RiskConfig(max_drawdown_pct=0.02, risk_per_trade_pct=0.5, max_position_pct=1.0)
    equity_curve, broker, risk_manager = run_backtest(risk_config, num_bars=300, volatility=0.05, seed=7)

    assert len(equity_curve) == 300
    assert risk_manager.halted
    assert risk_manager.halt_reason is not None
