"""Tests for the verified trade evidence boundary."""

from __future__ import annotations

from copy import deepcopy

from src.analytics.trade_evidence import build_trade_evidence


def _put_credit_row(**overrides) -> dict:
    row = {
        "id": "PCS-entry-exit",
        "status": "closed",
        "strategy": "spy_put_credit",
        "symbol": "SPY",
        "entry_time": "2026-07-01T14:30:00+00:00",
        "exit_time": "2026-07-03T15:30:00+00:00",
        "expiry": "2026-08-07",
        "realized_pnl": 75.0,
        "outcome": "win",
        "validation_phase": True,
        "profile_name": "spy-put-credit",
        "selection_method": "live_delta",
        "put_delta": 0.15,
        "quantity": 1,
        "exit_reason": "profit_target",
        "strikes": {"short_put": 700.0, "long_put": 695.0},
    }
    row.update(overrides)
    return row


def test_metrics_are_derived_from_paired_rows_not_unmatched_orders() -> None:
    payload = {
        "trades": [
            {
                "id": "ic-1",
                "status": "closed",
                "strategy": "iron_condor",
                "entry_time": "2026-06-01T14:30:00Z",
                "exit_time": "2026-06-02T14:30:00Z",
                "realized_pnl": 100,
                "outcome": "win",
            },
            {
                "id": "ic-2",
                "status": "closed",
                "strategy": "iron_condor",
                "entry_time": "2026-06-03T14:30:00Z",
                "exit_time": "2026-06-04T14:30:00Z",
                "realized_pnl": -40,
                "outcome": "loss",
            },
        ],
        "stats": {
            "closed_trades": 3,
            "total_realized_pnl": 110,
            "unpaired_order_count": 1,
            "unpaired_realized_pnl": 50,
        },
    }

    evidence = build_trade_evidence(payload)

    assert evidence.metrics.closed_trades == 2
    assert evidence.metrics.total_realized_pnl == 60
    assert evidence.metrics.expectancy_per_trade == 30
    assert evidence.metrics.profit_factor == 2.5
    assert any("mixes paired trades" in issue for issue in evidence.issues)
    assert any("mixes paired P/L" in issue for issue in evidence.issues)
    assert any("quarantined" in warning for warning in evidence.warnings)
    assert not evidence.learning_ready


def test_active_strategy_scope_excludes_killed_family() -> None:
    payload = {
        "trades": [
            _put_credit_row(),
            {
                "id": "ic-old",
                "status": "closed",
                "strategy": "iron_condor",
                "entry_time": "2026-06-01T14:30:00Z",
                "exit_time": "2026-06-02T14:30:00Z",
                "realized_pnl": -500,
                "outcome": "loss",
            },
        ],
        "stats": {"closed_trades": 2, "total_realized_pnl": -425},
    }

    evidence = build_trade_evidence(
        payload,
        strategy_family="spy_put_credit",
        require_protocol_fields=True,
    )

    assert [row["id"] for row in evidence.rows] == ["PCS-entry-exit"]
    assert evidence.metrics.total_realized_pnl == 75
    assert evidence.learning_ready


def test_live_delta_band_scan_is_verified_protocol_evidence() -> None:
    payload = {
        "trades": [_put_credit_row(selection_method="live_delta_band_scan", put_delta=0.1843)],
        "stats": {"closed_trades": 1, "total_realized_pnl": 75},
    }

    evidence = build_trade_evidence(
        payload,
        strategy_family="spy_put_credit",
        require_protocol_fields=True,
    )

    assert [row["id"] for row in evidence.rows] == ["PCS-entry-exit"]
    assert "unverified_strike_selection" not in evidence.rejected_by_reason


def test_invalid_protocol_row_is_quarantined_and_blocks_learning() -> None:
    payload = {
        "trades": [
            _put_credit_row(
                selection_method="hardcoded",
                put_delta=None,
                quantity=2,
                exit_reason=None,
            )
        ],
        "stats": {"closed_trades": 1, "total_realized_pnl": 75},
    }

    evidence = build_trade_evidence(
        payload,
        strategy_family="spy_put_credit",
        require_protocol_fields=True,
    )

    assert evidence.rows == []
    assert evidence.rejected_by_reason["unverified_strike_selection"] == 1
    assert evidence.rejected_by_reason["delta_outside_protocol"] == 1
    assert evidence.rejected_by_reason["quantity_outside_protocol"] == 1
    assert evidence.rejected_by_reason["missing_or_invalid_exit_reason"] == 1
    assert any("failed evidence validation" in issue for issue in evidence.issues)
    assert not evidence.learning_ready


def test_outcome_mismatch_and_duplicate_ids_are_rejected() -> None:
    first = _put_credit_row(outcome="loss")
    duplicate = deepcopy(first)
    duplicate["outcome"] = "win"
    payload = {
        "trades": [first, duplicate],
        "stats": {"closed_trades": 2, "total_realized_pnl": 150},
    }

    evidence = build_trade_evidence(
        payload,
        strategy_family="spy_put_credit",
        require_protocol_fields=True,
    )

    assert evidence.rows == []
    assert evidence.rejected_by_reason["outcome_pnl_mismatch"] == 1
    assert evidence.rejected_by_reason["duplicate_trade_id"] == 1
    assert not evidence.learning_ready


def test_dataset_hash_is_deterministic() -> None:
    payload = {
        "trades": [_put_credit_row()],
        "stats": {"closed_trades": 1, "total_realized_pnl": 75},
    }

    first = build_trade_evidence(payload, strategy_family="spy_put_credit")
    second = build_trade_evidence(deepcopy(payload), strategy_family="spy_put_credit")

    assert first.dataset_sha256 == second.dataset_sha256
