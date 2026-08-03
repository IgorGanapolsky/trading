"""Tests for LLM/RAG production control plane and fail-closed gates."""

from __future__ import annotations

from src.observability.llm_production_control_plane import (
    evaluate_llm_production_control_plane,
    _grade,
)
from src.rag.document_acl import assert_indexable, detect_secrets, scrub_secrets
from src.rag.rag_pipeline import GateDecision, LessonResult, gate_decision
from src.validators.pre_tool_validator import PreToolValidator


def test_grade_thresholds():
    assert _grade(9.6) == "A+"
    assert _grade(9.0) == "A"
    assert _grade(7.0) == "B"


def test_llm_plane_reports_six_dimensions():
    report = evaluate_llm_production_control_plane()
    names = {d.name for d in report.dimensions}
    assert names == {
        "latency_cost_control",
        "observability",
        "failure_modes",
        "structured_outputs",
        "multi_tenancy_acl",
        "framework_discipline",
    }
    assert report.overall_score_0_10 >= 9.5
    assert report.a_plus_ready is True
    assert all(d.score_0_10 >= 9.5 for d in report.dimensions)
    assert "EDGE_CANDIDATE" in report.cash_engine_note or "n≥30" in report.cash_engine_note
    # Framework discipline must stay high (no LangChain in pyproject)
    fw = next(d for d in report.dimensions if d.name == "framework_discipline")
    assert fw.score_0_10 >= 9.95


def test_empty_index_fail_closed_safety_and_strict():
    d = gate_decision([], mode="safety", index_size=0)
    assert d.approved is False
    assert d.severity == "BLOCK"
    assert d.empty_index is True

    d2 = gate_decision([], mode="strict", index_size=0)
    assert d2.approved is False

    # advisory allows degraded continue (soft path)
    d3 = gate_decision([], mode="advisory", index_size=0)
    assert d3.approved is True
    assert d3.severity == "DEGRADED"


def test_retrieval_miss_modes():
    # index healthy, no hits
    d = gate_decision([], mode="advisory", index_size=10)
    assert d.approved is True
    assert d.severity == "APPROVED"

    d2 = gate_decision([], mode="safety", index_size=10)
    assert d2.approved is True
    assert d2.severity == "DEGRADED"

    d3 = gate_decision([], mode="strict", index_size=10)
    assert d3.approved is False
    assert d3.severity == "BLOCK"


def test_critical_lesson_still_blocks():
    lesson = LessonResult(
        id="LL-TEST",
        title="Never do X",
        severity="CRITICAL",
        snippet="critical failure",
        prevention="do not X",
        file="LL-TEST.md",
        score=0.9,
    )
    d = gate_decision([(lesson, 0.9)], mode="safety", index_size=50)
    assert d.approved is False
    assert d.severity == "BLOCK"


def test_document_acl_scrubs_secrets():
    text = "key is sk-abcdefghijklmnopqrstuvwxyz012345 and more text here for length"
    assert detect_secrets(text)
    scrubbed = scrub_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_assert_indexable_rejects_secrets():
    try:
        assert_indexable("password=supersecretvalue1234567890")
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def test_pre_tool_fail_closed_money_tools():
    # Registered tool with missing fields → invalid
    r = PreToolValidator.validate_tool_call("place_order", {"symbol": "SPY"})
    assert r.is_valid is False

    # Unregistered money tool → FAIL_CLOSED
    r2 = PreToolValidator.validate_tool_call("submit_order_raw", {"symbol": "SPY"})
    assert r2.is_valid is False
    assert any("FAIL_CLOSED" in e for e in r2.errors)

    # Unregistered advisory tool → still allowed
    r3 = PreToolValidator.validate_tool_call("summarize_news", {"text": "hi"})
    assert r3.is_valid is True


def test_gate_decision_dataclass_has_mode():
    d = gate_decision([], mode="advisory", index_size=1)
    assert isinstance(d, GateDecision)
    assert d.mode == "advisory"
