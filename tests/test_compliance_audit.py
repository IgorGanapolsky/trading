"""Tests for compliance audit pattern matching precision."""

import re

from scripts.compliance_audit import DANGEROUS_CODE_PATTERNS


def _matches(text: str) -> list[str]:
    hits: list[str] = []
    for pattern, description in DANGEROUS_CODE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(description)
    return hits


def test_detects_explicit_bypass_language():
    text = """
    # bad code sample
    if should_bypass_circuit_breaker:
        execute_trade()
    """
    hits = _matches(text)
    assert "Circuit breaker bypass in code" in hits


def test_detects_manual_trade_override_language():
    text = "manual trade override requested by operator"
    hits = _matches(text)
    assert "Forced trade execution" in hits


def test_avoids_known_false_positives():
    text = """
    reinforcement learning trade model
    Force releasing trade lock for dead session cleanup
    re.finditer(pattern, content, re.IGNORECASE)
    """
    hits = _matches(text)
    assert hits == []
