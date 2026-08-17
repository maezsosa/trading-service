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
