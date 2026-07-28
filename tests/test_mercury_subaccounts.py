"""Unit tests for Mercury sub-accounts, auto-transfer rules, and IO card cashback engine."""

from __future__ import annotations

import json
import pytest
from src.bank.subaccounts import (
    MercurySubAccountManager,
    SubAccountType,
)


def test_calculate_auto_transfer_split(tmp_path):
    """Verify auto-transfer split correctly allocates 20% tax and 10% profit."""
    log_file = tmp_path / "mercury_subaccounts.jsonl"
    manager = MercurySubAccountManager(log_path=log_file)

    split = manager.calculate_auto_transfer_split(1000.0, tax_pct=20.0, profit_pct=10.0)

    assert split.total_amount_usd == 1000.0
    assert split.tax_reserve_usd == 200.0
    assert split.profit_reserve_usd == 100.0
    assert split.operating_expenses_usd == 700.0

    # Verify log output
    assert log_file.exists()
    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "AUTO_TRANSFER_SPLIT"
    assert record["data"]["tax_reserve_usd"] == 200.0


def test_calculate_auto_transfer_split_invalid_amount(tmp_path):
    """Verify non-positive amount raises ValueError."""
    manager = MercurySubAccountManager(log_path=tmp_path / "log.jsonl")
    with pytest.raises(ValueError, match="must be positive"):
        manager.calculate_auto_transfer_split(0.0)


def test_calculate_io_card_cashback(tmp_path):
    """Verify 1.5% IO card cashback calculation."""
    log_file = tmp_path / "cashback.jsonl"
    manager = MercurySubAccountManager(log_path=log_file)

    reward = manager.calculate_io_card_cashback(spend_usd=2000.0, cashback_rate_pct=1.5)

    assert reward.spend_amount_usd == 2000.0
    assert reward.cashback_rate_pct == 1.5
    assert reward.cashback_earned_usd == 30.0
    assert reward.destination_subaccount == SubAccountType.PROFIT

    # Verify log output
    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "CASHBACK_REWARD"
    assert record["data"]["cashback_earned_usd"] == 30.0
