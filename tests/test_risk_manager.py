from datetime import datetime

from core.types import AccountState, Side, Signal
from risk.manager import RiskConfig, RiskManager


def make_signal(side: Side = Side.BUY, stop_loss_pct: float = 0.02) -> Signal:
    return Signal(timestamp=datetime(2024, 1, 1), symbol="TEST", side=side, stop_loss_pct=stop_loss_pct)


def test_position_sizing_respects_risk_per_trade():
    config = RiskConfig(risk_per_trade_pct=0.01, max_position_pct=1.0, max_total_exposure_pct=1.0)
    manager = RiskManager(config)
    account = AccountState(cash=10_000.0)

    order = manager.validate(make_signal(stop_loss_pct=0.02), account, mark_price=100.0)

    # risk_amount = 10000 * 0.01 = 100; stop_distance = 100 * 0.02 = 2 -> qty = 50
    assert order is not None
    assert order.quantity == 50.0


def test_max_position_pct_caps_order_size():
    config = RiskConfig(risk_per_trade_pct=0.5, max_position_pct=0.1, max_total_exposure_pct=1.0)
    manager = RiskManager(config)
    account = AccountState(cash=10_000.0)

    order = manager.validate(make_signal(stop_loss_pct=0.01), account, mark_price=100.0)

    # max position value = 10000 * 0.1 = 1000 -> qty capped at 10
    assert order is not None
    assert order.quantity == 10.0


def test_kill_switch_halts_after_max_drawdown():
    config = RiskConfig(max_drawdown_pct=0.1)
    manager = RiskManager(config)
    account = AccountState(cash=10_000.0, equity_peak=10_000.0)

    order = manager.validate(make_signal(), account, mark_price=100.0)
    assert order is not None
    assert not manager.halted

    account.cash = 8_500.0  # simulate a loss: drawdown from peak is now 15%
    order = manager.validate(make_signal(), account, mark_price=100.0)

    assert manager.halted
    assert order is None


def test_daily_loss_limit_blocks_new_trades_without_permanent_halt():
    config = RiskConfig(max_daily_loss_pct=0.02)
    manager = RiskManager(config)
    account = AccountState(cash=10_000.0, equity_peak=10_000.0, realized_pnl_today=-300.0)

    order = manager.validate(make_signal(), account, mark_price=100.0)

    assert order is None
    assert not manager.halted


def test_max_total_exposure_blocks_when_already_fully_deployed():
    from core.types import Position

    config = RiskConfig(max_total_exposure_pct=0.5)
    manager = RiskManager(config)
    account = AccountState(cash=5_000.0, equity_peak=10_000.0)
    account.positions["OTHER"] = Position(symbol="OTHER", quantity=50.0, avg_entry_price=100.0)

    order = manager.validate(make_signal(), account, mark_price=100.0)

    assert order is None


def test_exposure_uses_each_position_own_price_not_the_new_signals_price():
    from core.types import Position

    # OTHER is priced at 1000/unit (real notional 50_000), far above the
    # incoming signal's mark_price for TEST. Exposure must be computed off
    # OTHER's own price, not TEST's mark_price, or it's wildly understated.
    config = RiskConfig(max_total_exposure_pct=0.5)
    manager = RiskManager(config)
    account = AccountState(cash=5_000.0, equity_peak=10_000.0)
    account.positions["OTHER"] = Position(symbol="OTHER", quantity=50.0, avg_entry_price=1000.0)

    order = manager.validate(make_signal(), account, mark_price=100.0)

    assert order is None


def test_group_exposure_caps_correlated_symbols_combined():
    from core.types import Position

    config = RiskConfig(
        max_total_exposure_pct=1.0,  # total cap wide open on purpose
        correlated_groups={"BTC": "crypto", "ETH": "crypto"},
        max_group_exposure_pct=0.5,
    )
    manager = RiskManager(config)
    # cash reduced by the BTC notional already spent, so equity works out to
    # exactly 10,000 (5,000 cash + 5,000 BTC position), matching the pattern
    # used in the exposure tests above.
    account = AccountState(cash=5_000.0, equity_peak=10_000.0)
    # BTC already has $5,000 notional -- exactly the group's 50% budget.
    account.positions["BTC"] = Position(symbol="BTC", quantity=50.0, avg_entry_price=100.0)

    signal = Signal(timestamp=datetime(2024, 1, 1), symbol="ETH", side=Side.BUY, stop_loss_pct=0.02)
    order = manager.validate(signal, account, mark_price=100.0)

    assert order is None  # group budget already fully used by BTC, despite total cap being wide open


def test_group_exposure_does_not_constrain_symbols_outside_the_group():
    from core.types import Position

    config = RiskConfig(
        max_total_exposure_pct=1.0,
        correlated_groups={"BTC": "crypto", "ETH": "crypto"},
        max_group_exposure_pct=0.5,
    )
    manager = RiskManager(config)
    account = AccountState(cash=5_000.0, equity_peak=10_000.0)
    account.positions["BTC"] = Position(symbol="BTC", quantity=50.0, avg_entry_price=100.0)

    signal = Signal(timestamp=datetime(2024, 1, 1), symbol="SOL", side=Side.BUY, stop_loss_pct=0.02)
    order = manager.validate(signal, account, mark_price=100.0)

    assert order is not None  # SOL isn't in the "crypto" group, unaffected by BTC's group usage


def test_group_exposure_disabled_by_default():
    from core.types import Position

    config = RiskConfig(
        max_total_exposure_pct=1.0,
        correlated_groups={"BTC": "crypto", "ETH": "crypto"},
        # max_group_exposure_pct left at its default: None
    )
    manager = RiskManager(config)
    account = AccountState(cash=10_000.0, equity_peak=10_000.0)
    account.positions["BTC"] = Position(symbol="BTC", quantity=50.0, avg_entry_price=100.0)

    signal = Signal(timestamp=datetime(2024, 1, 1), symbol="ETH", side=Side.BUY, stop_loss_pct=0.02)
    order = manager.validate(signal, account, mark_price=100.0)

    assert order is not None  # the group check is opt-in
