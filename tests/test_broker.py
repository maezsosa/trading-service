from datetime import datetime

from broker.paper_broker import PaperBroker
from core.types import Order, Side


def make_order(side: Side, quantity: float) -> Order:
    return Order(timestamp=datetime(2024, 1, 1), symbol="TEST", side=side, quantity=quantity)


def test_reversing_order_resets_avg_entry_price_to_fill_price():
    broker = PaperBroker(initial_cash=10_000.0)

    broker.submit_order(make_order(Side.BUY, 10.0), mark_price=100.0)
    broker.submit_order(make_order(Side.SELL, 15.0), mark_price=150.0)

    position = broker.account.positions["TEST"]
    assert position.quantity == -5.0
    assert position.avg_entry_price == 150.0


def test_slippage_always_works_against_the_trader():
    broker = PaperBroker(initial_cash=10_000.0, slippage_pct=0.01)

    buy_fill = broker.submit_order(make_order(Side.BUY, 1.0), mark_price=100.0)
    sell_fill = broker.submit_order(make_order(Side.SELL, 1.0), mark_price=100.0)

    # A buy fills above the quoted price, a sell fills below it -- never
    # in the trader's favor.
    assert buy_fill.price == 101.0
    assert sell_fill.price == 99.0


def test_zero_slippage_by_default_fills_at_mark_price():
    broker = PaperBroker(initial_cash=10_000.0)

    fill = broker.submit_order(make_order(Side.BUY, 1.0), mark_price=100.0)

    assert fill.price == 100.0
