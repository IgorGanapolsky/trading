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


def test_path_validation_and_traversal_prevention(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    evaluator = SpecConformanceEvaluator(specs_dir=tmp_path / "specs")

    valid_spec = tmp_path / "spec.json"
    valid_spec.write_text("{}", encoding="utf-8")
    assert evaluator.validate_spec_path(valid_spec) == valid_spec.resolve()

    # Non-existent file
    import pytest

    with pytest.raises(FileNotFoundError):
        evaluator.validate_spec_path(tmp_path / "missing.json")

    # Non-json file
    bad_ext = tmp_path / "bad.txt"
    bad_ext.write_text("bad", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        evaluator.validate_spec_path(bad_ext)

    # Path traversal attempt outside root
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Access denied"):
        evaluator.validate_spec_path(outside)


def test_load_spec(tmp_path: Path, monkeypatch):
    import json

    monkeypatch.chdir(tmp_path)
    evaluator = SpecConformanceEvaluator()
    spec_path = tmp_path / "test.json"
    spec_path.write_text(json.dumps({"spec_id": "LOAD-01"}), encoding="utf-8")

    data = evaluator.load_spec(spec_path)
    assert data["spec_id"] == "LOAD-01"


def test_verify_receipt_hmac(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(audit_dir=tmp_path)
    mock_spec = {"spec_id": "TEST-HMAC", "version": "1.0.0", "invariants": []}
    receipt = evaluator.evaluate_trading_spec(mock_spec)

    assert SpecConformanceEvaluator.verify_receipt(receipt) is True

    # Tampered receipt
    import dataclasses

    tampered = dataclasses.replace(receipt, conformance_status="TAMPERED")
    assert SpecConformanceEvaluator.verify_receipt(tampered) is False

    # Empty fingerprint
    empty_fp = dataclasses.replace(receipt, sha256_fingerprint="")
    assert SpecConformanceEvaluator.verify_receipt(empty_fp) is False


def test_invariant_eval_failures(tmp_path: Path):
    evaluator = SpecConformanceEvaluator(audit_dir=tmp_path)
    spec = {
        "spec_id": "TEST-FAIL",
        "invariants": [
            {"id": "INV-003", "parameters": {"min_iv_rank": 40.0, "max_short_delta": 0.10}},
            {"id": "INV-004", "parameters": {"profit_target_pct": 50.0}},
            {"id": "INV-005", "parameters": {}},
            {"id": "INV-999", "name": "Custom"},
        ],
    }
    # State with low IV rank and delta too high and no idempotency
    state = {
        "iv_rank": 20.0,
        "short_delta": 0.25,
        "has_order_idempotency": False,
    }
    receipt = evaluator.evaluate_trading_spec(spec, system_state=state)
    assert receipt.conformance_status == "FAIL"
    assert receipt.failed_invariants == 2  # INV-003 and INV-005 fail


def test_main_cli(tmp_path: Path, monkeypatch, capsys):
    from scripts.spec_conformance_evaluator import main

    monkeypatch.chdir(tmp_path)

    # Doctor flag
    monkeypatch.setattr("sys.argv", ["evaluator", "--doctor"])
    assert main() == 0
    captured = capsys.readouterr()
    assert "ONLINE" in captured.out

    # Missing spec
    monkeypatch.setattr("sys.argv", ["evaluator", "--spec", "nonexistent.json"])
    assert main() == 1

    # Valid passing spec
    import json

    valid_spec = tmp_path / "valid.spec.json"
    valid_spec.write_text(
        json.dumps({"spec_id": "CLI-TEST", "version": "1.0", "invariants": []}), encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["evaluator", "--spec", str(valid_spec)])
    assert main() == 0
    captured = capsys.readouterr()
    assert "Status: PASS" in captured.out
