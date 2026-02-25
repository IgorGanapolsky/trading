"""Tests for src.safety.handoff_governance."""

from __future__ import annotations

import json
from pathlib import Path

from src.safety.handoff_governance import (
    append_handoff_audit_record,
    build_delegation_contract,
    infer_risk_tier,
    validate_delegation_contract,
)


def test_infer_risk_tier_from_changed_paths() -> None:
    assert infer_risk_tier(["README.md"]) == "low"
    assert infer_risk_tier(["scripts/reporting.py"]) == "medium"
    assert infer_risk_tier(["src/orchestrator/main.py"]) == "high"


def test_build_delegation_contract_auto_uses_inferred_risk_tier() -> None:
    contract = build_delegation_contract(
        changed_paths=["src/orchestrator/main.py"],
        mode="quick",
        assignee="codex",
        fallback_assignee="guardian",
        risk_tier="auto",
    )
    assert contract["risk_tier"] == "high"
    assert "workflow-contracts" in contract["acceptance_tests"]


def test_validate_delegation_contract_rejects_understated_risk_tier() -> None:
    contract = build_delegation_contract(
        changed_paths=["src/orchestrator/main.py"],
        mode="quick",
        assignee="codex",
        fallback_assignee="guardian",
        risk_tier="low",
    )
    issues = validate_delegation_contract(contract, changed_paths=["src/orchestrator/main.py"])
    assert any("lower than inferred tier" in issue for issue in issues)


def test_validate_delegation_contract_rejects_assignee_capability_overreach() -> None:
    contract = build_delegation_contract(
        changed_paths=["src/orchestrator/main.py"],
        mode="quick",
        assignee="autopilot",
        fallback_assignee="guardian",
        risk_tier="high",
    )
    issues = validate_delegation_contract(contract, changed_paths=["src/orchestrator/main.py"])
    assert any("cannot run risk tier" in issue for issue in issues)


def test_append_handoff_audit_record_builds_hash_chain(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    first = append_handoff_audit_record(log_path, {"run": 1, "status": "pass"})
    second = append_handoff_audit_record(log_path, {"run": 2, "status": "fail"})

    assert first["previous_hash"] == "GENESIS"
    assert second["previous_hash"] == first["hash"]
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[1]["hash"] == second["hash"]
