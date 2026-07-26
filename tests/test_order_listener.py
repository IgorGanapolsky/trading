from src.execution.order_listener import OrderEvent, OrderFillHandler


def test_order_fill_handler_buy(tmp_path):
    state_file = tmp_path / "state.json"
    handler = OrderFillHandler(state_path=state_file)

    event = OrderEvent(
        event_type="fill",
        order_id="ord-101",
        symbol="SCHD",
        qty=10.0,
        filled_qty=10.0,
        filled_price=80.0,
        side="buy",
        timestamp="2026-07-26T12:00:00Z",
    )

    state = handler.process_event(event)
    assert state["positions"]["SCHD"] == 800.0
    assert len(state["events"]) == 1
    assert state["events"][0]["order_id"] == "ord-101"


def test_order_fill_handler_sell(tmp_path):
    state_file = tmp_path / "state.json"
    handler = OrderFillHandler(state_path=state_file)
    initial_state = {"positions": {"SCHD": 1000.0}, "events": []}

    event = OrderEvent(
        event_type="fill",
        order_id="ord-102",
        symbol="SCHD",
        qty=5.0,
        filled_qty=5.0,
        filled_price=80.0,
        side="sell",
        timestamp="2026-07-26T12:05:00Z",
    )

    state = handler.process_event(event, state=initial_state)
    assert state["positions"]["SCHD"] == 600.0
