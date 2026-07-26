from src.adapters.mercury_reconciler import ACHDepositNotification, MercuryACHReconciler


def test_reconcile_deposit(tmp_path):
    state_file = tmp_path / "state.json"
    reconciler = MercuryACHReconciler(state_path=state_file)

    notification = ACHDepositNotification(
        transaction_id="tx-999",
        account_id="acct-7725",
        amount_usd=1000.0,
        sender_name="Alpaca Brokerage",
        posted_at="2026-07-26T14:00:00Z",
    )

    state = reconciler.reconcile_deposit(notification)
    assert state["total_deposited_to_bank_usd"] == 1000.0
    assert len(state["events"]) == 1
    assert state["events"][0]["transaction_id"] == "tx-999"


def test_reconcile_deposit_idempotency(tmp_path):
    state_file = tmp_path / "state.json"
    reconciler = MercuryACHReconciler(state_path=state_file)

    notification = ACHDepositNotification(
        transaction_id="tx-999",
        account_id="acct-7725",
        amount_usd=1000.0,
        sender_name="Alpaca Brokerage",
        posted_at="2026-07-26T14:00:00Z",
    )

    state1 = reconciler.reconcile_deposit(notification)
    state2 = reconciler.reconcile_deposit(notification, state=state1)

    assert state2["total_deposited_to_bank_usd"] == 1000.0
    assert len(state2["events"]) == 1
