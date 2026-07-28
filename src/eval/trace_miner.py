"""Trace Miner for Automated Eval Engineering.

Mines execution traces from runtime logs, tick audits, and system state histories
to automatically synthesize reproducible EvalCases for agent and strategy testing.
Inspired by LangChain's Eval Engineering Skill architecture.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvalCase:
    eval_id: str
    category: str  # e.g. "risk_gate", "bank_surplus", "rth_schedule", "order_idempotency"
    description: str
    input_state: dict[str, Any]
    expected_outcome: dict[str, Any]


class TraceMiner:
    """Mines execution logs to generate structured evaluation datasets."""

    def __init__(self, trace_dir: Path | None = None):
        self.trace_dir = trace_dir or (ROOT / "data" / "audit" / "ralph_ticks")

    def mine_eval_cases(self) -> list[EvalCase]:
        cases: list[EvalCase] = []

        # 1. Synthesize Default Risk Gate Eval Cases
        cases.append(
            EvalCase(
                eval_id="eval_risk_buffer_insufficient",
                category="bank_surplus",
                description="Verify bank adapter refuses withdrawal when balance <= $500 safety buffer",
                input_state={"available_balance_usd": 400.0, "safety_buffer_usd": 500.0},
                expected_outcome={"should_withdraw": False, "withdrawal_amount": 0.0},
            )
        )

        cases.append(
            EvalCase(
                eval_id="eval_risk_buffer_surplus",
                category="bank_surplus",
                description="Verify bank adapter withdraws exact surplus when balance > $500 safety buffer",
                input_state={"available_balance_usd": 1500.0, "safety_buffer_usd": 500.0},
                expected_outcome={"should_withdraw": True, "withdrawal_amount": 1000.0},
            )
        )

        cases.append(
            EvalCase(
                eval_id="eval_drawdown_circuit_breaker_trigger",
                category="risk_gate",
                description="Verify circuit breaker trips when intraday drawdown >= 5.0%",
                input_state={"current_equity": 9400.0, "peak_equity": 10000.0},
                expected_outcome={"tripped": True, "halt_file_written": True},
            )
        )

        # 2. Mine Historical Tick Files if present
        if self.trace_dir.exists():
            for tick_file in self.trace_dir.glob("tick_*.json"):
                try:
                    with tick_file.open("r", encoding="utf-8") as h:
                        data = json.load(h)
                    eval_id = f"eval_tick_{tick_file.stem}"
                    cases.append(
                        EvalCase(
                            eval_id=eval_id,
                            category="traced_tick",
                            description=f"Automated mined trace from {tick_file.name}",
                            input_state=data,
                            expected_outcome={"valid_structure": True},
                        )
                    )
                except Exception as exc:
                    logger.debug("Failed to parse tick file %s: %s", tick_file, exc)

        return cases

    def save_eval_dataset(self, output_path: Path | None = None) -> Path:
        output_path = output_path or (ROOT / "data" / "eval" / "eval_dataset.jsonl")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cases = self.mine_eval_cases()

        with output_path.open("w", encoding="utf-8") as h:
            for c in cases:
                h.write(json.dumps(asdict(c)) + "\n")

        logger.info("Saved %d eval cases to %s", len(cases), output_path)
        return output_path
