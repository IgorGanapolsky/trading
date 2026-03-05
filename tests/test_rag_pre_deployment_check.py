"""Tests for scripts/rag_pre_deployment_check.py."""

from __future__ import annotations

from scripts.rag_pre_deployment_check import infer_severity


def test_infer_severity_detects_critical_over_high() -> None:
    content = """
    # Lesson
    **Severity**: HIGH
    **Severity**: CRITICAL
    """
    assert infer_severity(content) == "critical"


def test_infer_severity_detects_high() -> None:
    assert infer_severity("severity: high") == "high"


def test_infer_severity_unknown_when_missing() -> None:
    assert infer_severity("no severity field here") == "unknown"
