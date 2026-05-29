"""Tests for src/utils/order_intent.py.

Locks in the wire format used to back-stamp OPEN/CLOSE intent on every
Alpaca order so the paired ledger (LL-354) never has to guess intent for
SIMPLE single-leg closes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.order_intent import (  # noqa: E402
    MAX_CLIENT_ORDER_ID_LEN,
    build_client_order_id,
    parse_client_order_id,
)


def test_build_then_parse_roundtrips_for_open_leg():
    cid = build_client_order_id("OPEN", "BPS", "SP")
    parsed = parse_client_order_id(cid)
    assert parsed is not None
    assert parsed["role"] == "OPEN"
    assert parsed["intent"] == "BPS"
    assert parsed["leg_tag"] == "SP"
    assert isinstance(parsed["nanos"], int) and parsed["nanos"] > 0


def test_build_then_parse_roundtrips_for_close_leg():
    cid = build_client_order_id("CLOSE", "BCS", "SC")
    parsed = parse_client_order_id(cid)
    assert parsed == {
        "role": "CLOSE",
        "intent": "BCS",
        "leg_tag": "SC",
        "nanos": parsed["nanos"],  # value verified above
    }


def test_build_combo_parent_has_empty_leg_tag():
    cid = build_client_order_id("OPEN", "IC")
    parsed = parse_client_order_id(cid)
    assert parsed is not None
    assert parsed["role"] == "OPEN"
    assert parsed["intent"] == "IC"
    assert parsed["leg_tag"] is None


def test_build_id_under_128_chars():
    # Alpaca caps client_order_id at 128. Real format is ~30 chars.
    for role in ("OPEN", "CLOSE"):
        for intent in ("BPS", "BPL", "BCS", "BCL", "IC"):
            for tag in (None, "SP", "LP", "SC", "LC"):
                cid = build_client_order_id(role, intent, tag)
                assert len(cid) <= MAX_CLIENT_ORDER_ID_LEN
                assert cid.startswith("IC-")


def test_build_rejects_unknown_role():
    with pytest.raises(ValueError):
        build_client_order_id("REOPEN", "BPS", "SP")


def test_build_rejects_unknown_intent():
    with pytest.raises(ValueError):
        build_client_order_id("OPEN", "XYZ", "SP")


def test_build_rejects_unknown_leg_tag():
    with pytest.raises(ValueError):
        build_client_order_id("OPEN", "BPS", "ZZ")


def test_parse_returns_none_for_unknown_formats():
    # Pre-existing Alpaca order IDs / legacy rows must not raise.
    assert parse_client_order_id(None) is None
    assert parse_client_order_id("") is None
    assert parse_client_order_id("3c4b8a2e-1234-abcd") is None  # uuid-ish
    assert parse_client_order_id("IC-OPEN-BPS-SP") is None  # missing nanos
    assert parse_client_order_id("IC-WAT-BPS-SP-1") is None  # bad role
    assert parse_client_order_id("IC-OPEN-XXX-SP-1") is None  # bad intent
    assert parse_client_order_id("foo IC-OPEN-BPS-SP-1") is None  # not anchored


def test_build_is_unique_per_call():
    # time.time_ns()+counter guarantees uniqueness even in a tight loop.
    ids = {build_client_order_id("OPEN", "BPS", "SP") for _ in range(50)}
    assert len(ids) == 50
