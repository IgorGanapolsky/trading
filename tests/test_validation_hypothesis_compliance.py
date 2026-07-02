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
