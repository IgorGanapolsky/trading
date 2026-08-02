"""Antithesis-Inspired Deterministic Chaos & Fault Injection Simulator.

Steals core principles from Antithesis (Deterministic Simulation Testing, State-Space Exploration,
Property Invariants, and Time-Travel Bug Minimization) tailored specifically for options trading
and agentic execution safety.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CHAOS_AUDIT_LOG = ROOT / "data" / "audit" / "chaos_simulation_runs.json"


class FaultType(StrEnum):
    BROKER_API_TIMEOUT = "BROKER_API_TIMEOUT"
    PARTIAL_FILL_DESYNC = "PARTIAL_FILL_DESYNC"
    CIRCUIT_BREAKER_STORM = "CIRCUIT_BREAKER_STORM"
    STALE_GREEKS_DATA = "STALE_GREEKS_DATA"
    MERCURY_REMITTANCE_DELAY = "MERCURY_REMITTANCE_DELAY"


@dataclass(frozen=True)
class InvariantViolation:
    invariant_name: str
    description: str
    step_index: int
    seed: int
    fault_type: FaultType | None


@dataclass
class SimulationState:
    step_index: int
    cash_balance: float
    account_drawdown_pct: float
    open_leg_count: int
    rl_quarantined: bool
    delta: float


class SystemInvariantChecker:
    """Checks hard system safety rules across every tick state."""

    def check_invariants(
        self, state: SimulationState, seed: int, fault: FaultType | None
    ) -> list[InvariantViolation]:
        violations: list[InvariantViolation] = []

        # Invariant 1: Drawdown never exceeds 5.0%
        if state.account_drawdown_pct > 0.05:
            violations.append(
                InvariantViolation(
                    invariant_name="DRAWDOWN_LIMIT_5_PCT",
                    description=f"Account drawdown {state.account_drawdown_pct * 100:.2f}% exceeded 5.0% safety limit",
                    step_index=state.step_index,
                    seed=seed,
                    fault_type=fault,
                )
            )

        # Invariant 2: Defined-risk Iron Condor legs must be balanced (0 or 4)
        if state.open_leg_count not in (0, 4):
            violations.append(
                InvariantViolation(
                    invariant_name="IRON_CONDOR_4_LEG_HEDGE",
                    description=f"Unhedged options position found with {state.open_leg_count} legs open",
                    step_index=state.step_index,
                    seed=seed,
                    fault_type=fault,
                )
            )

        # Invariant 3: Maximum 0.15 Delta limit for SPY/XSP credit spreads
        if state.delta > 0.15:
            violations.append(
                InvariantViolation(
                    invariant_name="DELTA_LIMIT_15",
                    description=f"Position delta {state.delta:.3f} exceeded max 0.15 threshold",
                    step_index=state.step_index,
                    seed=seed,
                    fault_type=fault,
                )
            )

        return violations


class DeterministicChaosSimulator:
    """Deterministic Simulation Testing (DST) engine with fault injection."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.invariant_checker = SystemInvariantChecker()

    def run_simulation(
        self,
        steps: int = 100,
        fault_rate: float = 0.10,
    ) -> dict[str, Any]:
        self.rng.seed(self.seed)

        state = SimulationState(
            step_index=0,
            cash_balance=10000.0,
            account_drawdown_pct=0.0,
            open_leg_count=4,
            rl_quarantined=True,
            delta=0.15,
        )

        violations: list[InvariantViolation] = []
        faults_injected: list[dict[str, Any]] = []

        for i in range(1, steps + 1):
            state.step_index = i

            # Decide whether to inject a fault this step
            injected_fault: FaultType | None = None
            if self.rng.random() < fault_rate:
                injected_fault = self.rng.choice(list(FaultType))
                faults_injected.append({"step": i, "fault": injected_fault.value})

            # Apply simulation dynamics & fault perturbations
            if injected_fault == FaultType.CIRCUIT_BREAKER_STORM:
                state.account_drawdown_pct = 0.06  # Triggers drawdown violation
            elif injected_fault == FaultType.PARTIAL_FILL_DESYNC:
                state.open_leg_count = 2  # Triggers leg hedge violation
            elif injected_fault == FaultType.STALE_GREEKS_DATA:
                state.delta = 0.22  # Triggers delta violation
            else:
                # Normal state progression
                state.account_drawdown_pct = max(0.0, state.account_drawdown_pct - 0.001)
                state.open_leg_count = 4 if state.open_leg_count > 0 else 0
                state.delta = 0.15

            # Assert invariants
            step_violations = self.invariant_checker.check_invariants(
                state, self.seed, injected_fault
            )
            violations.extend(step_violations)

        report = {
            "seed": self.seed,
            "total_steps": steps,
            "faults_injected_count": len(faults_injected),
            "invariant_violations_count": len(violations),
            "faults_injected": faults_injected,
            "violations": [asdict(v) for v in violations],
            "passed": len(violations) == 0,
        }

        self._save_audit_report(report)
        return report

    def _save_audit_report(self, report: dict[str, Any]) -> None:
        CHAOS_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        try:
            runs = []
            if CHAOS_AUDIT_LOG.exists():
                with CHAOS_AUDIT_LOG.open("r", encoding="utf-8") as h:
                    runs = json.load(h)
            runs.append(report)
            with CHAOS_AUDIT_LOG.open("w", encoding="utf-8") as h:
                json.dump(runs[-20:], h, indent=2)
        except Exception as e:
            logger.warning("Failed to save chaos simulation report: %s", e)
