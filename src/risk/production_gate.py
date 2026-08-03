"""Production gate — hard preconditions for new trading risk.

World-class ops: every new-risk attempt passes a deterministic checklist.
This does NOT invent edge. Edge is separate (cohort EDGE_CANDIDATE).

Use before put-credit entries and any gateway new-risk path that opts in.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_STATE = ROOT / "data" / "system_state.json"
KILL_SWITCH = ROOT / "data" / "runtime" / "strategy_kill_switch.json"
INVENTORY = ROOT / "data" / "audit" / "open_inventory_latest.json"
HALT = ROOT / "data" / "TRADING_HALTED"
COHORT = ROOT / "data" / "audit" / "put_credit_cohort_latest.json"

# Ops SLA: broker snapshot older than this fails the production gate for NEW risk.
MAX_STATE_AGE_HOURS = float(os.environ.get("PRODUCTION_GATE_MAX_STATE_AGE_HOURS", "24"))
MAX_INVENTORY_AGE_HOURS = float(os.environ.get("PRODUCTION_GATE_MAX_INVENTORY_AGE_HOURS", "24"))


@dataclass
class GateCheck:
    id: str
    ok: bool
    severity: str  # critical | high | info
    detail: str


@dataclass
class ProductionGateResult:
    ok: bool
    score_0_10: float
    grade: str
    checks: list[GateCheck] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    allow_new_risk: bool = False
    allow_live_capital: bool = False
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score_0_10": self.score_0_10,
            "grade": self.grade,
            "checks": [asdict(c) for c in self.checks],
            "blockers": self.blockers,
            "allow_new_risk": self.allow_new_risk,
            "allow_live_capital": self.allow_live_capital,
            "generated_at": self.generated_at,
        }


def _grade(score: float) -> str:
    if score >= 9.5:
        return "A+"
    if score >= 9.0:
        return "A"
    if score >= 8.5:
        return "A-"
    if score >= 8.0:
        return "B+"
    if score >= 7.0:
        return "B"
    if score >= 6.0:
        return "B-"
    if score >= 5.0:
        return "C"
    if score >= 4.0:
        return "C-"
    if score >= 3.0:
        return "D"
    return "F"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    return max(0.0, (datetime.now(UTC).timestamp() - path.stat().st_mtime) / 3600.0)


def evaluate_production_gate(
    *,
    require_fresh_state: bool = True,
    require_clean_inventory: bool = True,
    require_put_credit_active: bool = True,
    for_live: bool = False,
) -> ProductionGateResult:
    """Evaluate ops production gate.

    allow_new_risk: paper new entries when ops checks pass (edge sample may still be thin).
    allow_live_capital: only EDGE_CANDIDATE + live not blocked incorrectly.
    """
    checks: list[GateCheck] = []
    blockers: list[str] = []

    # 1) Halt file
    halted = HALT.is_file()
    checks.append(
        GateCheck(
            "trading_halt",
            not halted,
            "critical",
            "TRADING_HALTED absent" if not halted else f"{HALT} present",
        )
    )
    if halted:
        blockers.append("TRADING_HALTED")

    # 2) Kill switch / active family
    kill = _load_json(KILL_SWITCH) or {}
    active = kill.get("active_family")
    paper_only = bool(kill.get("paper_only", True))
    live_blocked = bool(kill.get("live_blocked", True))
    killed = set(kill.get("killed_families") or [])
    family_ok = (not require_put_credit_active) or active == "spy_put_credit"
    checks.append(
        GateCheck(
            "active_family",
            family_ok,
            "critical",
            f"active_family={active} paper_only={paper_only} live_blocked={live_blocked}",
        )
    )
    if not family_ok:
        blockers.append(f"active_family={active}")
    ic_killed = "ic_simple" in killed or "iron_condor" in killed
    checks.append(
        GateCheck(
            "ic_killed",
            ic_killed,
            "high",
            f"killed_families={sorted(killed)}",
        )
    )
    if not ic_killed:
        blockers.append("IC families not marked killed")

    # 3) System state freshness
    age = _file_age_hours(SYSTEM_STATE)
    state = _load_json(SYSTEM_STATE) or {}
    state_ok = (
        age is not None and age <= MAX_STATE_AGE_HOURS if require_fresh_state else age is not None
    )
    checks.append(
        GateCheck(
            "broker_state_fresh",
            bool(state_ok),
            "critical" if require_fresh_state else "high",
            f"system_state age_h={round(age, 2) if age is not None else None} "
            f"max={MAX_STATE_AGE_HOURS} equity={(state.get('paper_account') or {}).get('equity')}",
        )
    )
    if require_fresh_state and not state_ok:
        blockers.append("stale_or_missing_system_state")

    # 4) Inventory
    inv = _load_json(INVENTORY)
    inv_age = _file_age_hours(INVENTORY)
    if inv is None:
        inv_ok = not require_clean_inventory
        inv_detail = "inventory audit missing"
        if require_clean_inventory:
            blockers.append("missing_inventory_audit")
    else:
        clean = bool(inv.get("clean", False))
        inv_fresh = inv_age is not None and inv_age <= MAX_INVENTORY_AGE_HOURS
        inv_ok = clean and (inv_fresh or not require_clean_inventory)
        inv_detail = (
            f"clean={clean} findings={len(inv.get('findings') or [])} "
            f"age_h={round(inv_age, 2) if inv_age is not None else None}"
        )
        if require_clean_inventory and not clean:
            blockers.append("unclean_inventory")
        if require_clean_inventory and not inv_fresh:
            blockers.append("stale_inventory_audit")
            inv_ok = False
    checks.append(
        GateCheck(
            "open_inventory",
            inv_ok,
            "critical" if require_clean_inventory else "high",
            inv_detail,
        )
    )

    # 5) Cohort / live capital policy
    cohort = _load_json(COHORT) or {}
    # Prefer embedded kill criteria; else rebuild lightly
    closed = (cohort.get("closed") or {}) if isinstance(cohort, dict) else {}
    kill_crit = closed.get("kill_criteria") or {}
    verdict = str(kill_crit.get("verdict") or "UNKNOWN")
    if verdict == "UNKNOWN":
        try:
            from scripts.put_credit_cohort_scorecard import build_scorecard

            card = build_scorecard()
            kill_crit = (card.get("closed") or {}).get("kill_criteria") or {}
            verdict = str(kill_crit.get("verdict") or "UNKNOWN")
            closed = card.get("closed") or closed
        except Exception as exc:  # noqa: BLE001
            checks.append(
                GateCheck("cohort_scorecard", False, "high", f"cohort rebuild failed: {exc}")
            )
    edge = verdict == "EDGE_CANDIDATE" and kill_crit.get("pass_all") is True
    checks.append(
        GateCheck(
            "edge_cohort",
            True,  # does not block paper new risk
            "info",
            f"verdict={verdict} closed_n={closed.get('closed_n')} live_deposit_ready={edge}",
        )
    )
    # World-class: live_blocked stays true until human flips AFTER EDGE_CANDIDATE.
    allow_live_capital = bool(edge and live_blocked is False)
    if for_live and not allow_live_capital:
        blockers.append("live_not_authorized")
        checks.append(
            GateCheck(
                "live_authorization",
                False,
                "critical",
                f"for_live requires EDGE_CANDIDATE and live_blocked=false; "
                f"verdict={verdict} live_blocked={live_blocked}",
            )
        )
    else:
        checks.append(
            GateCheck(
                "live_authorization",
                not for_live or allow_live_capital,
                "info",
                f"for_live={for_live} allow_live_capital={allow_live_capital}",
            )
        )

    # 6) Paper account present
    paper_eq = float((state.get("paper_account") or {}).get("equity") or 0.0)
    paper_ok = paper_eq > 1000.0
    checks.append(
        GateCheck(
            "paper_equity",
            paper_ok,
            "high",
            f"paper_equity={paper_eq}",
        )
    )
    if not paper_ok:
        blockers.append("paper_equity_missing_or_too_low")

    # 7) RAG knowledge base non-empty (empty_index fail-closed for safety path)
    rag_index_ok = True
    rag_detail = "rag index check skipped"
    try:
        from src.rag.rag_pipeline import get_trading_rag_pipeline

        pipe = get_trading_rag_pipeline()
        n_lessons = pipe.index_size()
        rag_index_ok = n_lessons > 0
        rag_detail = f"rag_index_size={n_lessons}"
        if not rag_index_ok:
            blockers.append("empty_rag_index")
    except Exception as exc:  # noqa: BLE001
        # High but not critical: order path can still use gateway without FTS
        rag_index_ok = False
        rag_detail = f"rag_index_error={exc}"
        blockers.append("rag_index_unavailable")
    checks.append(
        GateCheck(
            "rag_index_non_empty",
            rag_index_ok,
            "high",
            rag_detail,
        )
    )

    # 8) LLM production control plane (process maturity; not edge)
    llm_ok = True
    llm_detail = "llm plane skipped"
    try:
        from src.observability.llm_production_control_plane import (
            evaluate_llm_production_control_plane,
        )

        llm_report = evaluate_llm_production_control_plane()
        # Require B+ process floor for new risk ops; do not require A+ cash engine
        llm_ok = llm_report.overall_score_0_10 >= 8.0
        llm_detail = (
            f"llm_grade={llm_report.overall_grade} score={llm_report.overall_score_0_10} "
            f"a_plus_ready={llm_report.a_plus_ready}"
        )
        if not llm_ok:
            blockers.append("llm_production_plane_below_b_plus")
    except Exception as exc:  # noqa: BLE001
        llm_ok = False
        llm_detail = f"llm_plane_error={exc}"
        blockers.append("llm_production_plane_error")
    checks.append(
        GateCheck(
            "llm_production_plane",
            llm_ok,
            "high",
            llm_detail,
        )
    )

    # Score: critical failures dominate
    critical_fail = [c for c in checks if c.severity == "critical" and not c.ok]
    high_fail = [c for c in checks if c.severity == "high" and not c.ok]
    n_ok = sum(1 for c in checks if c.ok)
    base = 10.0 * n_ok / max(len(checks), 1)
    if critical_fail:
        base = min(base, 4.0)
    if high_fail:
        base = min(base, 7.5)
    # Perfect ops: all critical/high pass
    if not critical_fail and not high_fail:
        base = max(base, 9.5)

    allow_new_risk = not critical_fail and not halted and family_ok
    if require_clean_inventory and not inv_ok:
        allow_new_risk = False
    if require_fresh_state and not state_ok:
        allow_new_risk = False
    # Empty knowledge base must not approve new risk (fail-closed)
    if not rag_index_ok:
        allow_new_risk = False
    if not llm_ok:
        # Process plane below B+ is a high-severity ops failure
        allow_new_risk = False
    if for_live:
        allow_new_risk = allow_new_risk and allow_live_capital

    # For ops A+: ok means all critical/high checks green (paper path)
    ops_ok = not critical_fail and not high_fail

    return ProductionGateResult(
        ok=ops_ok,
        score_0_10=round(base, 2),
        grade=_grade(base),
        checks=checks,
        blockers=blockers,
        allow_new_risk=allow_new_risk,
        allow_live_capital=allow_live_capital,
        generated_at=datetime.now(UTC).isoformat(),
    )


def assert_new_risk_allowed(*, for_live: bool = False) -> ProductionGateResult:
    """Raise RuntimeError if new risk must not open."""
    result = evaluate_production_gate(for_live=for_live)
    if for_live and not result.allow_live_capital:
        raise RuntimeError(
            "PRODUCTION GATE: live capital not authorized — "
            f"blockers={result.blockers} grade={result.grade}"
        )
    if not result.allow_new_risk:
        raise RuntimeError(
            f"PRODUCTION GATE: new risk blocked — blockers={result.blockers} grade={result.grade}"
        )
    return result
