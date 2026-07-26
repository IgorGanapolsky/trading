"""Hard-gate for live trading and real Mercury bank transfers.

Fail closed when kill switch blocks live or put-credit edge sample is insufficient.
Dry-run / paper planning is not blocked by this module.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.core.active_strategy import load_kill_state

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COHORT = REPO_ROOT / "data" / "audit" / "put_credit_cohort_latest.json"
DEFAULT_KILL = REPO_ROOT / "data" / "runtime" / "strategy_kill_switch.json"

EDGE_N_MIN = 30
EDGE_MIN_EXPECTANCY = 0.0
EDGE_MIN_PF = 1.0


@dataclass(frozen=True)
class LiveBankGateDecision:
    allowed: bool
    live_trading_allowed: bool
    bank_transfer_allowed: bool
    blockers: tuple[str, ...]
    paper_only: bool
    live_blocked: bool
    sample_closed_n: int | None
    expectancy: float | None
    profit_factor: float | None
    strategy_mode: str
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["blockers"] = list(self.blockers)
        return d


def _load_cohort_metrics(cohort_path: Path) -> dict[str, Any]:
    if not cohort_path.is_file():
        return {}
    try:
        raw = json.loads(cohort_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    closed = raw.get("closed") if isinstance(raw.get("closed"), dict) else {}
    kill = closed.get("kill_criteria") if isinstance(closed.get("kill_criteria"), dict) else {}
    honesty = raw.get("honesty") if isinstance(raw.get("honesty"), dict) else {}
    return {
        "closed_n": closed.get("closed_n"),
        "expectancy": closed.get("expectancy"),
        "profit_factor": closed.get("profit_factor"),
        "verdict": kill.get("verdict"),
        "live_deposit_ready": honesty.get("live_deposit_ready"),
        "claim_profitable": honesty.get("claim_profitable"),
    }


def evaluate_live_bank_gate(
    *,
    cohort_path: Path | None = None,
    require_edge_sample: bool = True,
) -> LiveBankGateDecision:
    """Return whether live trading and real bank transfers may proceed.

    Strategy mode is always multi-day / non-PDT default (put-credit holds or
    buy-and-hold), never same-day churn as the primary path.
    """
    state = load_kill_state()
    metrics = _load_cohort_metrics(cohort_path or DEFAULT_COHORT)
    blockers: list[str] = []

    if state.live_blocked:
        blockers.append(f"kill_switch.live_blocked: {state.reason[:200]}")
    if state.paper_only:
        blockers.append("kill_switch.paper_only=true")

    closed_n = metrics.get("closed_n")
    exp = metrics.get("expectancy")
    pf = metrics.get("profit_factor")
    try:
        # Missing cohort → treat as 0 closed (fail closed for live), not None
        closed_n_i = int(closed_n) if closed_n is not None else 0
    except (TypeError, ValueError):
        closed_n_i = 0
    try:
        exp_f = float(exp) if exp is not None else None
    except (TypeError, ValueError):
        exp_f = None
    try:
        pf_f = float(pf) if pf is not None else None
    except (TypeError, ValueError):
        pf_f = None

    if require_edge_sample:
        if closed_n_i is None or closed_n_i < EDGE_N_MIN:
            blockers.append(
                f"insufficient_edge_sample: closed_n={closed_n_i} need>={EDGE_N_MIN}"
            )
        else:
            if exp_f is None or exp_f <= EDGE_MIN_EXPECTANCY:
                blockers.append(f"expectancy_not_positive: {exp_f}")
            if pf_f is None or pf_f <= EDGE_MIN_PF:
                blockers.append(f"profit_factor_not_gt_1: {pf_f}")
        if metrics.get("live_deposit_ready") is False:
            blockers.append("cohort.live_deposit_ready=false")
        if metrics.get("verdict") and str(metrics.get("verdict")) != "EDGE_CANDIDATE":
            blockers.append(f"kill_verdict={metrics.get('verdict')} (need EDGE_CANDIDATE)")

    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for b in blockers:
        if b not in seen:
            seen.add(b)
            uniq.append(b)

    allowed = len(uniq) == 0
    return LiveBankGateDecision(
        allowed=allowed,
        live_trading_allowed=allowed,
        bank_transfer_allowed=allowed,
        blockers=tuple(uniq),
        paper_only=bool(state.paper_only),
        live_blocked=bool(state.live_blocked),
        sample_closed_n=closed_n_i,
        expectancy=exp_f,
        profit_factor=pf_f,
        strategy_mode="multi_day_hold_or_buy_hold_non_pdt",
        detail={
            "active_family": state.active_family,
            "cohort_verdict": metrics.get("verdict"),
            "claim_profitable": metrics.get("claim_profitable"),
        },
    )


def assert_live_bank_allowed(*, action: str = "live_or_bank") -> LiveBankGateDecision:
    """Raise RuntimeError with block reasons if live/bank not allowed."""
    decision = evaluate_live_bank_gate()
    if not decision.allowed:
        raise RuntimeError(
            f"{action} REFUSED (fail closed): " + "; ".join(decision.blockers)
        )
    return decision
