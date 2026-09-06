from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path("scripts/ci/ai_pr_review.py")


def _load():
    spec = importlib.util.spec_from_file_location("ai_pr_review", MODULE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_review_event_approve_and_changes() -> None:
    mod = _load()
    assert mod.parse_review_event("Top verdict: APPROVE\n- Why: clean") == "APPROVE"
    assert mod.parse_review_event("REQUEST_CHANGES\n- P0: gateway bypass") == "REQUEST_CHANGES"
    assert mod.parse_review_event("no verdict here") == "COMMENT"
    assert mod.parse_review_event("APPROVE\nbut later REQUEST_CHANGES on a P0") == "REQUEST_CHANGES"
