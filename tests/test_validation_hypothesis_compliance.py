"""Guard: the executing profile must honor the active validation hypothesis.

The July 2026 validation cohort was invalidated because the committed
hypothesis (data/runtime/strategy_validation_hypothesis.json) rejected
10-wide wings while the spy-core profile kept trading them. This test
fails CI whenever the active profile drifts from the hypothesis
constraints, so a hypothesis change must land together with the profile
change that enforces it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.trading_profiles import get_iron_condor_profile

HYPOTHESIS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "runtime" / "strategy_validation_hypothesis.json"
)


@pytest.fixture(scope="module")
def hypothesis() -> dict:
    if not HYPOTHESIS_PATH.exists():
        pytest.skip("no validation hypothesis deployed")
    return json.loads(HYPOTHESIS_PATH.read_text())


def test_profile_honors_validation_hypothesis(hypothesis: dict) -> None:
    if not hypothesis.get("enabled"):
        pytest.skip("validation hypothesis disabled")

    profile = get_iron_condor_profile()

    # "reject 10-wide wings; the validation cohort must use narrower
    # defined-risk wings" — failed-ledger loss cluster ten_wide_wings.
    assert profile.wing_width < 10.0, (
        f"profile wing_width={profile.wing_width} repeats the 10-wide loss "
        "cluster prohibited by the active validation hypothesis"
    )

    # "one contract per structure" — loss cluster multi_contract.
    assert profile.max_contracts_per_trade == 1

    # "no more than one new structure per day".
    assert profile.max_daily_structures == 1

    # CLAUDE.md mandate: at most 2 concurrent ICs (8 legs).
    assert profile.max_concurrent_positions <= 2

    # "close by 7 DTE" — loss cluster long_hold_ge_7d.
    assert profile.exit_dte >= 7

    # "minimum 24-hour hold" — loss cluster early_exit_lt_24h.
    assert profile.min_hold_hours >= 24


def test_prohibited_loss_clusters_are_acknowledged(hypothesis: dict) -> None:
    if not hypothesis.get("enabled"):
        pytest.skip("validation hypothesis disabled")

    ack = hypothesis.get("rehabilitation_plan_ack", {})
    covered = set(ack.get("covered_loss_clusters", []))
    assert {"ten_wide_wings", "multi_contract"} <= covered


def test_hypothesis_unblocks_quarantined_entries(hypothesis: dict) -> None:
    """Mirror north_star_guard's gate: the committed hypothesis must cover the
    rehab plan's top-3 loss clusters, or every entry attempt is silently
    quarantined (Jun 18 – Jul 2 2026 outage: plan added long_hold_ge_7d,
    hypothesis never acknowledged it, zero entries for two weeks)."""
    if not hypothesis.get("enabled"):
        pytest.skip("validation hypothesis disabled")

    from src.safety.north_star_guard import _hypothesis_covers_rehabilitation_plan

    assert hypothesis.get("changed_rules"), "guard requires changed_rules"
    assert hypothesis.get("kill_criteria"), "guard requires kill_criteria"
    assert _hypothesis_covers_rehabilitation_plan(hypothesis, HYPOTHESIS_PATH), (
        "hypothesis does not cover the rehab plan's top loss clusters; "
        "north_star_guard will quarantine ALL new validation entries"
    )


def test_ic_simple_strategy_params_honor_hypothesis(hypothesis: dict) -> None:
    """scripts/ic_simple.py reads data/strategy_params.json (ML-writable), a
    second config source that bypasses trading_profiles. The 2026-07-02 dry
    run proved it can propose 10-wide entries after the profile was fixed —
    guard both sources."""
    if not hypothesis.get("enabled"):
        pytest.skip("validation hypothesis disabled")

    params_path = HYPOTHESIS_PATH.parents[1] / "strategy_params.json"
    params = json.loads(params_path.read_text())["params"]

    assert params["wing_width"] < 10, "ten_wide_wings loss cluster repeated"
    assert params["stop_loss"] == 1.0, "pinned canonical constant"
    assert params["profit_target"] == 0.50, "fixed exit plan per hypothesis"
    assert params["max_ic"] <= 2
    assert params["exit_dte"] >= 7
