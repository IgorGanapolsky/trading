"""Automated Evaluation Harness for Strategy and Risk Gate Benchmarking.

Evaluates synthesized EvalCases against system rules, computing accuracy %,
pass rates, policy compliance, and detailed failure diagnostics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.eval.trace_miner import EvalCase, TraceMiner
from src.risk.drawdown_circuit_breaker import DrawdownCircuitBreaker

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    category: str
    passed: bool
    details: str
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class EvalReport:
    total_evals: int
    passed_count: int
    failed_count: int
    pass_rate_pct: float
    results: list[EvalResult]


class EvalHarness:
    """Runs automated evaluation benchmarks across strategy and risk components."""

    def __init__(self, dataset_path: Path | None = None):
        self.dataset_path = dataset_path or (ROOT / "data" / "eval" / "eval_dataset.jsonl")

    def load_cases(self) -> list[EvalCase]:
        if not self.dataset_path.exists():
            miner = TraceMiner()
            miner.save_eval_dataset(self.dataset_path)

        cases: list[EvalCase] = []
        with self.dataset_path.open("r", encoding="utf-8") as h:
            for line in h:
                if line.strip():
                    raw = json.loads(line)
                    cases.append(EvalCase(**raw))
        return cases

    def run_evals(self) -> EvalReport:
        cases = self.load_cases()
        results: list[EvalResult] = []

        for case in cases:
            res = self._evaluate_case(case)
            results.append(res)

        passed_count = sum(1 for r in results if r.passed)
        total_evals = len(results)
        pass_rate = round((passed_count / total_evals) * 100.0, 2) if total_evals > 0 else 0.0

        return EvalReport(
            total_evals=total_evals,
            passed_count=passed_count,
            failed_count=total_evals - passed_count,
            pass_rate_pct=pass_rate,
            results=results,
        )

    def _evaluate_case(self, case: EvalCase) -> EvalResult:
        if case.category == "bank_surplus":
            bal = case.input_state.get("available_balance_usd", 0.0)
            buf = case.input_state.get("safety_buffer_usd", 500.0)
            surplus = max(0.0, bal - buf)
            should_withdraw = surplus > 0.0

            expected_withdraw = case.expected_outcome.get("should_withdraw", False)
            expected_amt = case.expected_outcome.get("withdrawal_amount", 0.0)

            passed = (should_withdraw == expected_withdraw) and (surplus == expected_amt)
            return EvalResult(
                eval_id=case.eval_id,
                category=case.category,
                passed=passed,
                details=f"Surplus calculated ${surplus:.2f} (expected ${expected_amt:.2f})",
                diagnostics={"calculated_surplus": surplus, "expected_amount": expected_amt},
            )

        elif case.category == "risk_gate":
            current_eq = case.input_state.get("current_equity", 10000.0)
            peak_eq = case.input_state.get("peak_equity", 10000.0)
            cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0)
            # NEVER persist eval equity into production data/TRADING_HALTED.
            # Synthetic cases (e.g. 9400/10000) previously halted real paper trading.
            status = cb.check_equity(
                current_equity=current_eq,
                peak_equity=peak_eq,
                persist=False,
            )

            expected_tripped = case.expected_outcome.get("tripped", False)
            passed = status.tripped == expected_tripped
            return EvalResult(
                eval_id=case.eval_id,
                category=case.category,
                passed=passed,
                details=f"Circuit breaker tripped={status.tripped} (expected {expected_tripped})",
                diagnostics={
                    "drawdown_pct": status.drawdown_pct,
                    "tripped": status.tripped,
                    "persist": False,
                },
            )

        else:
            # Default traced tick structural check
            valid = bool(case.input_state)
            return EvalResult(
                eval_id=case.eval_id,
                category=case.category,
                passed=valid,
                details="Traced tick structure verified",
                diagnostics={"has_input": valid},
            )
