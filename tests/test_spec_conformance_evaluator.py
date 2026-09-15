#!/usr/bin/env python3
"""
Unit tests for Spec-Driven Development (SDD) Conformance Evaluator.
"""

from pathlib import Path
from scripts.spec_conformance_evaluator import SpecConformanceEvaluator


def test_spec_conformance_evaluator_initialization(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(specs_dir=tmp_path / "specs", audit_dir=tmp_path / "audit")
    assert evaluator.specs_dir == tmp_path / "specs"
    assert evaluator.audit_dir.exists()


def test_evaluate_trading_spec_success(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(audit_dir=tmp_path)
    mock_spec = {
        "spec_id": "TEST-SPEC-01",
        "version": "1.0.0",
        "invariants": [
            {
                "id": "INV-001",
                "name": "Buffett Rule #1",
                "parameters": {"max_risk_pct_nav": 1.0},
            },
            {
                "id": "INV-002",
                "name": "Defined Risk",
                "parameters": {"requires_protective_wing": True},
            },
            {
                "id": "INV-003",
                "name": "Selective Regime",
                "parameters": {"min_iv_rank": 30.0, "max_short_delta": 0.15},
            },
            {
                "id": "INV-004",
                "name": "50% Profit Harvesting",
                "parameters": {"profit_target_pct": 50.0},
            },
            {
                "id": "INV-005",
                "name": "Order Identity",
                "parameters": {"idempotency_token_required": True},
            },
        ],
    }
    valid_state = {
        "portfolio_nav": 100000.0,
        "max_risk_pct": 0.8,
        "iv_rank": 40.0,
        "short_delta": 0.12,
        "has_protective_wing": True,
        "has_order_idempotency": True,
    }

    receipt = evaluator.evaluate_trading_spec(mock_spec, system_state=valid_state)
    assert receipt.conformance_status == "PASS"
    assert receipt.total_invariants == 5
    assert receipt.passed_invariants == 5
    assert receipt.failed_invariants == 0
    assert receipt.conformance_pct == 100.0
    assert len(receipt.sha256_fingerprint) == 64


def test_evaluate_trading_spec_failure_detection(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(audit_dir=tmp_path)
    mock_spec = {
        "spec_id": "TEST-SPEC-02",
        "version": "1.0.0",
        "invariants": [
            {
                "id": "INV-001",
                "name": "Buffett Rule #1",
                "parameters": {"max_risk_pct_nav": 1.0},
            },
            {
                "id": "INV-002",
                "name": "Defined Risk",
                "parameters": {"requires_protective_wing": True},
            },
        ],
    }
    invalid_state = {
        "max_risk_pct": 3.5,  # Exceeds 1.0% cap
        "has_protective_wing": False,  # Naked options
    }

    receipt = evaluator.evaluate_trading_spec(mock_spec, system_state=invalid_state)
    assert receipt.conformance_status == "FAIL"
    assert receipt.passed_invariants == 0
    assert receipt.failed_invariants == 2
    assert receipt.conformance_pct == 0.0


def test_save_receipt_creates_valid_json(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(audit_dir=tmp_path)
    mock_spec = {"spec_id": "TEST-SAVE", "version": "1.0.0", "invariants": []}
    receipt = evaluator.evaluate_trading_spec(mock_spec)

    receipt_path = evaluator.save_receipt(receipt, filename="test_receipt.json")
    assert receipt_path.exists()

    content = receipt_path.read_text(encoding="utf-8")
    assert "TEST-SAVE" in content
    assert "sha256_fingerprint" in content
