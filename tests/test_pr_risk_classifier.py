"""Tests for PR risk classifier (AI vs human review)."""

from __future__ import annotations

from src.ops.pr_risk_classifier import classify_pr_paths, mentions_billed_review


def test_docs_and_ops_allow_ai_approve():
    d = classify_pr_paths(
        [
            "docs/INFOQ_CONTROL_PLANE.md",
            "src/ops/context_gist.py",
            "tests/test_context_gist.py",
        ]
    )
    assert d.allow_ai_approve is True
    assert d.require_human is False
    assert d.risk == "low"
    assert d.ok is True


def test_risk_paths_require_human():
    d = classify_pr_paths(["src/risk/trade_gateway.py", "docs/README.md"])
    assert d.require_human is True
    assert d.allow_ai_approve is False
    assert d.risk == "high"
    assert "src/risk/trade_gateway.py" in d.matched_human_paths


def test_billed_copilot_forbidden():
    d = classify_pr_paths(
        ["docs/x.md"],
        propose_billed_copilot=True,
    )
    assert d.ok is False
    assert "billed_copilot_review_forbidden" in d.failing
    assert d.forbid_billed_copilot_review is True


def test_unknown_path_fail_closed():
    d = classify_pr_paths(["mystery/engine.rs"])
    assert d.ok is False
    assert d.require_human is True
    assert "mystery/engine.rs" in d.unknown_paths


def test_mentions_billed_review():
    assert mentions_billed_review("enable Copilot Code Review billed per review")
    assert not mentions_billed_review("use existing CI AI review")


def test_unrecognized_script_requires_human():
    d = classify_pr_paths(["scripts/submit_order.py"])
    assert d.allow_ai_approve is False
    assert d.require_human is True
    assert "scripts/submit_order.py" in d.unknown_paths


def test_allowlisted_infoq_script_ai_ok():
    d = classify_pr_paths(["scripts/infoq_agent_control_plane.py", "docs/INFOQ_CONTROL_PLANE.md"])
    assert d.allow_ai_approve is True
    assert d.ok is True


def test_path_traversal_resolves_to_human_policy():
    d = classify_pr_paths(["src/ops/../risk/trade_gateway.py"])
    assert d.require_human is True
    assert d.allow_ai_approve is False
    assert "src/risk/trade_gateway.py" in d.matched_human_paths


def test_absolute_and_escaping_paths_fail_closed():
    d = classify_pr_paths(["/etc/passwd", "../secrets.env"])
    assert d.ok is False
    assert d.require_human is True
    assert len(d.unknown_paths) == 2
