"""Tests for scripts.collect_agent_handoff_ab_metrics."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.collect_agent_handoff_ab_metrics import collect_ab_metrics, summarize_records


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_ab_metrics_computes_expected_fields(tmp_path: Path) -> None:
    gate_report = {
        "passed": False,
        "changed_paths": [
            "rag_knowledge/lessons_learned/ll_001.md",
            "src/core/trading_constants.py",
            "rag_knowledge/lessons_learned/ll_001.md",  # duplicate path shouldn't double count
        ],
        "steps": [
            {"name": "trading policy drift", "passed": False, "duration_seconds": 0.2},
            {"name": "lint", "passed": True, "duration_seconds": 1.0},
            {"name": "format", "passed": True, "duration_seconds": 0.4},
            {"name": "tests", "passed": False, "duration_seconds": 2.4},
        ],
    }
    policy_report = {"checks_failed": 2, "drift_items": ["a", "b"]}

    gate_path = tmp_path / "gate.json"
    policy_path = tmp_path / "policy.json"
    incident_root = tmp_path / "rag_knowledge" / "lessons_learned"
    incident_root.mkdir(parents=True)
    (incident_root / "ll_001.md").write_text("x", encoding="utf-8")
    (incident_root / "ll_002.md").write_text("x", encoding="utf-8")
    (incident_root / "notes.txt").write_text("x", encoding="utf-8")

    _write_json(gate_path, gate_report)
    _write_json(policy_path, policy_report)

    metrics = collect_ab_metrics(
        variant="B",
        gate_report_path=gate_path,
        policy_report_path=policy_path,
        ci_conclusion="failure",
        incident_root=incident_root,
    )

    assert metrics["variant"] == "B"
    assert metrics["gate_passed"] is False
    assert metrics["gate_latency_seconds"] == 4.0
    assert metrics["policy_violations"] == 2
    assert metrics["ci_pass"] is False
    assert metrics["lint_passed"] is True
    assert metrics["tests_passed"] is False
    assert metrics["policy_passed"] is False
    assert metrics["incident_count_total"] == 2
    assert metrics["incident_count_changed"] == 1


def test_summarize_records_filters_by_lookback_and_groups_variants() -> None:
    now = datetime.now(timezone.utc)
    recent_a = {
        "captured_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "variant": "A",
        "gate_passed": True,
        "ci_pass": True,
        "gate_latency_seconds": 1.0,
        "policy_violations": 0,
        "incident_count_total": 2,
        "incident_count_changed": 0,
    }
    recent_b = {
        "captured_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "variant": "B",
        "gate_passed": False,
        "ci_pass": False,
        "gate_latency_seconds": 3.0,
        "policy_violations": 2,
        "incident_count_total": 4,
        "incident_count_changed": 2,
    }
    stale = {
        "captured_at_utc": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "variant": "A",
        "gate_passed": False,
        "ci_pass": False,
        "gate_latency_seconds": 10.0,
        "policy_violations": 9,
        "incident_count_total": 9,
        "incident_count_changed": 9,
    }

    summary = summarize_records([recent_a, recent_b, stale], days=7)

    assert summary["samples"] == 2
    assert summary["variants"]["A"]["samples"] == 1
    assert summary["variants"]["A"]["gate_pass_rate"] == 1.0
    assert summary["variants"]["A"]["avg_gate_latency_seconds"] == 1.0

    assert summary["variants"]["B"]["samples"] == 1
    assert summary["variants"]["B"]["gate_pass_rate"] == 0.0
    assert summary["variants"]["B"]["avg_policy_violations"] == 2.0
