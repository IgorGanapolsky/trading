"""Tests for open option inventory hygiene audit."""

from __future__ import annotations

import json
from pathlib import Path

from src.risk.open_inventory_audit import (
    audit_from_files,
    audit_open_inventory,
    parse_option_leg,
)


def test_parse_option_leg():
    leg = parse_option_leg("SPY260821C00776000", -2)
    assert leg is not None
    assert leg.expiry_ymd == "260821"
    assert leg.right == "C"
    assert leg.strike == 776.0
    assert leg.qty == -2.0


def test_clean_one_lot_ic():
    positions = [
        {"symbol": "SPY260821C00776000", "qty": -1},
        {"symbol": "SPY260821C00781000", "qty": 1},
        {"symbol": "SPY260821P00703000", "qty": 1},
        {"symbol": "SPY260821P00708000", "qty": -1},
    ]
    entries = {
        "IC_260821": {
            "quantity": 1,
            "strikes": {
                "short_put": 708.0,
                "long_put": 703.0,
                "short_call": 776.0,
                "long_call": 781.0,
            },
        }
    }
    result = audit_open_inventory(positions, entries)
    assert result.clean is True
    assert result.option_leg_count == 4
    assert result.block_reasons() == []


def test_detects_two_lot_call_and_extra_put_vertical():
    """Reproduce SPY 2026-08-21 dirty book from live ledger."""
    positions = [
        {"symbol": "SPY260821C00776000", "qty": -2},
        {"symbol": "SPY260821C00781000", "qty": 2},
        {"symbol": "SPY260821P00695000", "qty": 1},
        {"symbol": "SPY260821P00700000", "qty": -1},
        {"symbol": "SPY260821P00703000", "qty": 1},
        {"symbol": "SPY260821P00708000", "qty": -1},
    ]
    entries = {
        "IC_260821": {
            "quantity": 1,
            "signature": "SPY_2026-08-21_P703-708_C776-781",
            "strikes": {
                "short_put": 708.0,
                "long_put": 703.0,
                "short_call": 776.0,
                "long_call": 781.0,
            },
        }
    }
    result = audit_open_inventory(positions, entries)
    assert result.clean is False
    codes = {f.code for f in result.findings}
    assert "LOT_SIZE_EXCEEDED" in codes
    assert "EXTRA_LEGS" in codes or "QTY_MISMATCH" in codes
    assert "SAME_EXPIRY_OVERSTACK" in codes
    assert any("776" in r or "lot" in r.lower() or "extra" in r.lower() for r in result.block_reasons())


def test_unjournaled_expiry_blocks():
    positions = [{"symbol": "SPY260821P00708000", "qty": -1}]
    result = audit_open_inventory(positions, {})
    assert result.clean is False
    assert any(f.code == "UNJOURNALED_EXPIRY" for f in result.findings)


def test_audit_from_files_on_repo_fixture(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "system_state.json").write_text(
        json.dumps(
            {
                "positions": [
                    {"symbol": "SPY260821C00776000", "qty": -1},
                    {"symbol": "SPY260821C00781000", "qty": 1},
                    {"symbol": "SPY260821P00703000", "qty": 1},
                    {"symbol": "SPY260821P00708000", "qty": -1},
                ]
            }
        ),
        encoding="utf-8",
    )
    (data / "ic_entries.json").write_text(
        json.dumps(
            {
                "IC_260821": {
                    "quantity": 1,
                    "strikes": {
                        "short_put": 708.0,
                        "long_put": 703.0,
                        "short_call": 776.0,
                        "long_call": 781.0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    result = audit_from_files(tmp_path)
    assert result.clean is True
