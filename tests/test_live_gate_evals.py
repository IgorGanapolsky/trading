"""Fail-closed evals for the live-money gate (src/bank/live_gate.py).

This gate is the single decision point between paper validation and real
Mercury/broker money movement. These evals pin:
- the policy thresholds (n>=30, expectancy>0, PF>1) to kill-criteria.md
- fail-closed behavior on missing/corrupt cohort data and on a missing
  human sign-off bit (honesty.live_deposit_ready must be explicitly true)
- each blocker triggering independently
- that the gate CAN open when every criterion is genuinely met, so the
  unlock path provably exists (a gate that can never open hides risk in
  whatever workaround eventually replaces it)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.bank.live_gate as live_gate
import src.core.active_strategy as active_strategy
from src.bank.live_gate import evaluate_live_bank_gate


@pytest.fixture
def kill_cleared(tmp_path, monkeypatch):
    """Kill switch with live explicitly unblocked (the post-validation state)."""
    _write_kill(tmp_path, monkeypatch, paper_only=False, live_blocked=False)
    return tmp_path


@pytest.fixture
def kill_blocking(tmp_path, monkeypatch):
    """Kill switch in today's real state: paper only, live blocked."""
    _write_kill(tmp_path, monkeypatch, paper_only=True, live_blocked=True)
    return tmp_path


def _write_kill(tmp_path, monkeypatch, *, paper_only: bool, live_blocked: bool) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    kill_file = runtime / "strategy_kill_switch.json"
    kill_file.write_text(
        json.dumps(
            {
                "active_family": "spy_put_credit",
                "successor_family": "spy_put_credit",
                "killed_families": ["ic_simple", "iron_condor"],
                "paper_only": paper_only,
                "live_blocked": live_blocked,
                "reason": "eval fixture",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(active_strategy, "KILL_FILE", kill_file)
    monkeypatch.setattr(active_strategy, "HYPOTHESIS_FILE", runtime / "no_hypothesis.json")
    monkeypatch.delenv("ACTIVE_STRATEGY_FAMILY", raising=False)


def _cohort(
    tmp_path,
    *,
    closed_n: int = 100,
    expectancy: float = 12.5,
    expectancy_lower_95: float = 5.0,
    profit_factor: float = 1.8,
    verdict: str = "EDGE_CANDIDATE",
    live_deposit_ready: bool | None = True,
    omit_honesty: bool = False,
) -> Path:
    payload: dict = {
        "closed": {
            "closed_n": closed_n,
            "expectancy": expectancy,
            "expectancy_lower_95": expectancy_lower_95,
            "profit_factor": profit_factor,
            "kill_criteria": {"verdict": verdict},
            "desk_grade": {"verdict": "DESK_GRADE_CANDIDATE"},
        }
    }
    if not omit_honesty:
        payload["honesty"] = {"live_deposit_ready": live_deposit_ready}
    path = tmp_path / "cohort.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _blocker_matching(decision, needle: str) -> bool:
    return any(needle in blocker for blocker in decision.blockers)


class TestPolicyConstants:
    def test_thresholds_match_kill_criteria_policy(self):
        assert live_gate.EDGE_N_MIN == 100
        assert live_gate.EDGE_MIN_EXPECTANCY == 0.0
        assert live_gate.EDGE_MIN_PF == 1.2


class TestGateCanOpen:
    def test_all_criteria_met_allows_live(self, kill_cleared):
        cohort = _cohort(kill_cleared)
        decision = evaluate_live_bank_gate(cohort_path=cohort)
        assert decision.blockers == ()
        assert decision.allowed is True
        assert decision.live_trading_allowed is True
        assert decision.bank_transfer_allowed is True


class TestFailClosed:
    def test_missing_cohort_file_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(cohort_path=kill_cleared / "does_not_exist.json")
        assert decision.allowed is False
        assert _blocker_matching(decision, "insufficient_edge_sample")

    def test_corrupt_cohort_json_blocks(self, kill_cleared):
        corrupt = kill_cleared / "cohort.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        decision = evaluate_live_bank_gate(cohort_path=corrupt)
        assert decision.allowed is False

    def test_missing_honesty_signoff_blocks(self, kill_cleared):
        cohort = _cohort(kill_cleared, omit_honesty=True)
        decision = evaluate_live_bank_gate(cohort_path=cohort)
        assert decision.allowed is False
        assert _blocker_matching(decision, "live_deposit_ready")

    def test_signoff_false_blocks(self, kill_cleared):
        cohort = _cohort(kill_cleared, live_deposit_ready=False)
        decision = evaluate_live_bank_gate(cohort_path=cohort)
        assert decision.allowed is False
        assert _blocker_matching(decision, "live_deposit_ready")


class TestEachCriterionBlocksIndependently:
    def test_insufficient_sample_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(cohort_path=_cohort(kill_cleared, closed_n=99))
        assert decision.allowed is False
        assert _blocker_matching(decision, "insufficient_edge_sample")

    def test_nonpositive_expectancy_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(cohort_path=_cohort(kill_cleared, expectancy=0.0))
        assert decision.allowed is False
        assert _blocker_matching(decision, "expectancy_not_positive")

    def test_profit_factor_at_one_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(cohort_path=_cohort(kill_cleared, profit_factor=1.0))
        assert decision.allowed is False
        assert _blocker_matching(decision, "profit_factor_not_gte_1.2")

    def test_nonpositive_expectancy_confidence_bound_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(
            cohort_path=_cohort(kill_cleared, expectancy=10.0, expectancy_lower_95=-1.0)
        )
        assert decision.allowed is False
        assert _blocker_matching(decision, "expectancy_lower_95_not_positive")

    def test_non_candidate_verdict_blocks(self, kill_cleared):
        decision = evaluate_live_bank_gate(
            cohort_path=_cohort(kill_cleared, verdict="INSUFFICIENT_SAMPLE")
        )
        assert decision.allowed is False
        assert _blocker_matching(decision, "kill_verdict")

    def test_kill_switch_flags_block_even_with_perfect_cohort(self, kill_blocking):
        decision = evaluate_live_bank_gate(cohort_path=_cohort(kill_blocking))
        assert decision.allowed is False
        assert _blocker_matching(decision, "live_blocked")
        assert _blocker_matching(decision, "paper_only")
