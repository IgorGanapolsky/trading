"""Tests for deterministic context gisting."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from src.ops.context_gist import estimate_tokens, gist_context


def test_gist_requires_two_acs_and_scopes():
    bad = gist_context(
        goal="x",
        in_scope="",
        out_scope="no webinar",
        acceptance_criteria=["only one"],
    )
    assert bad.ok is False
    assert "missing_in_scope" in bad.failing
    assert "need_at_least_two_acceptance_criteria" in bad.failing


def test_gist_ok_within_budget():
    g = gist_context(
        goal="put credit dry-run",
        in_scope="paper plan only",
        out_scope="live submit",
        acceptance_criteria=["tests pass", "CLI exit 0"],
        constraints=["paper_only"],
        token_budget=800,
    )
    assert g.ok is True
    assert g.estimated_tokens <= g.token_budget
    assert len(g.content_hash) == 16
    assert "paper_only" in g.constraints


def test_newsletter_noise_dropped():
    g = gist_context(
        goal="session",
        in_scope="trading ops",
        out_scope="Harness webinar",
        acceptance_criteria=["a", "b"],
        extras=["Sponsored by Harness Save your Seat", "useful constraint note"],
    )
    assert any(d.startswith("noise:") for d in g.dropped_sections)
    assert any("useful constraint" in c for c in g.constraints)


def test_estimate_tokens_positive():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 8) == 2


def test_many_dropped_extras_stay_within_budget():
    extras = [f"Sponsored by Harness Save your Seat noise {i}" for i in range(200)]
    g = gist_context(
        goal="session",
        in_scope="trading ops",
        out_scope="webinar spend",
        acceptance_criteria=["a", "b"],
        extras=extras,
        token_budget=400,
    )
    assert g.estimated_tokens <= g.token_budget
    compact = g.compact()
    assert estimate_tokens(compact) <= g.token_budget + 40  # metadata lines
    assert any(
        d.startswith("dropped_overflow:") or d.startswith("noise:") for d in g.dropped_sections
    )
    assert len(g.dropped_sections) < 50


def test_cli_script_loads():
    path = Path(__file__).resolve().parents[1] / "scripts" / "context_gist.py"
    spec = importlib.util.spec_from_file_location("context_gist_cli", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main(
        [
            "--goal",
            "g",
            "--in-scope",
            "in",
            "--out-scope",
            "out",
            "--ac",
            "one",
            "--ac",
            "two",
        ]
    )
    assert rc == 0
