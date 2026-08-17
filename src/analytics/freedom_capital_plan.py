"""Freedom Number + 3-bucket capital jobs + 30-day paced sprint.

Steals high-ROI *process* from income-portfolio bootcamps (e.g. Freedom Builder):

1. Define a precise monthly Freedom Number before scaling
2. Give every dollar a job (3 buckets) matched to risk / proof stage
3. Prefer messy action + paced 30-day build over content binge
4. Explicitly NOT stock picks or signal service

Adapted to this lab: North Star passive income + paper put-credit validation.
Does NOT submit trades or unlock live capital.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

# Default North Star (repo policy) — caller may override.
DEFAULT_MONTHLY_AFTER_TAX = 6000.0
DEFAULT_TAX_RESERVE_RATE = 0.30  # set-aside heuristic, not tax advice
DEFAULT_GROSS_YIELD_ANNUAL = 0.08  # planning assumption for "passive bucket" only


@dataclass(frozen=True)
class FreedomNumber:
    """Monthly income that makes work optional — defined by the operator."""

    monthly_after_tax: float
    annual_after_tax: float
    tax_reserve_rate: float
    monthly_pre_tax_approx: float
    capital_at_assumed_yield: float
    assumed_gross_yield_annual: float
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


def compute_freedom_number(
    monthly_after_tax: float = DEFAULT_MONTHLY_AFTER_TAX,
    *,
    tax_reserve_rate: float = DEFAULT_TAX_RESERVE_RATE,
    assumed_gross_yield_annual: float = DEFAULT_GROSS_YIELD_ANNUAL,
) -> FreedomNumber:
    """Define Freedom Number and illustrative capital required at a yield.

    Yield capital is for the *passive* bucket planning only — not a promise that
    put-credit or any strategy delivers that yield.
    """
    if monthly_after_tax <= 0:
        raise ValueError("monthly_after_tax must be positive")
    if not 0 <= tax_reserve_rate < 1:
        raise ValueError("tax_reserve_rate must be in [0, 1)")
    if assumed_gross_yield_annual <= 0:
        raise ValueError("assumed_gross_yield_annual must be positive")

    annual = monthly_after_tax * 12.0
    # rough: need more pre-tax if setting aside tax_reserve_rate of pre-tax
    pre_tax_monthly = monthly_after_tax / (1.0 - tax_reserve_rate)
    capital = annual / assumed_gross_yield_annual
    return FreedomNumber(
        monthly_after_tax=round(monthly_after_tax, 2),
        annual_after_tax=round(annual, 2),
        tax_reserve_rate=tax_reserve_rate,
        monthly_pre_tax_approx=round(pre_tax_monthly, 2),
        capital_at_assumed_yield=round(capital, 2),
        assumed_gross_yield_annual=assumed_gross_yield_annual,
        notes=(
            "Not financial advice. Yield is a planning assumption for the passive bucket only.",
            "Put-credit paper edge is proven only via kill criteria (n>=30, E>0, PF>1), not this yield.",
            "Messy action: fund Lab bucket and run protocol before optimizing passive capital.",
        ),
    )


# Three buckets: every dollar has a job (bootcamp "3-Bucket System" spirit).
BUCKET_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "ops_safety",
        "name": "Ops / Safety",
        "job": "Runway, taxes reserve, business ops — no market risk",
        "risk": "none",
        "allows_trading": False,
        "default_fraction_hint": 0.40,
    },
    {
        "id": "lab_validation",
        "name": "Lab (paper validation)",
        "job": "Prove spy_put_credit edge under kill criteria — paper only",
        "risk": "paper_market",
        "allows_trading": True,
        "paper_only": True,
        "default_fraction_hint": 0.35,
    },
    {
        "id": "field_or_passive",
        "name": "Field / Passive",
        "job": "Live trading capital OR long-horizon passive income — gated",
        "risk": "live_or_market",
        "allows_trading": True,
        "live_requires_edge_candidate": True,
        "default_fraction_hint": 0.25,
    },
)


def allocate_three_buckets(
    total_liquid: float,
    *,
    ops_fraction: float = 0.40,
    lab_fraction: float = 0.35,
    field_fraction: float = 0.25,
    live_edge_candidate: bool = False,
    paper_equity: float | None = None,
) -> dict[str, Any]:
    """Assign liquid capital to three jobs. Fractions must sum to ~1."""
    if total_liquid < 0:
        raise ValueError("total_liquid must be >= 0")
    s = ops_fraction + lab_fraction + field_fraction
    if abs(s - 1.0) > 1e-6:
        raise ValueError(f"fractions must sum to 1.0, got {s}")

    ops = round(total_liquid * ops_fraction, 2)
    lab = round(total_liquid * lab_fraction, 2)
    field = round(total_liquid * field_fraction, 2)
    # fix rounding residue on ops
    residue = round(total_liquid - (ops + lab + field), 2)
    ops = round(ops + residue, 2)

    field_status = (
        "live_deploy_allowed_if_operator_chooses"
        if live_edge_candidate
        else "live_blocked_until_EDGE_CANDIDATE_or_hold_as_passive"
    )

    buckets = [
        {
            **BUCKET_SPECS[0],
            "allocated": ops,
            "fraction": ops_fraction,
            "status": "active",
        },
        {
            **BUCKET_SPECS[1],
            "allocated": lab,
            "fraction": lab_fraction,
            "status": "active_paper",
            "paper_equity_observed": paper_equity,
        },
        {
            **BUCKET_SPECS[2],
            "allocated": field,
            "fraction": field_fraction,
            "status": field_status,
            "live_edge_candidate": live_edge_candidate,
        },
    ]
    return {
        "schema_version": "three-bucket-capital/1",
        "total_liquid": round(total_liquid, 2),
        "buckets": buckets,
        "honesty": {
            "not_stock_picks": True,
            "not_signal_service": True,
            "note": (
                "Buckets assign jobs to capital. They do not recommend tickers or "
                "authorize live put-credit until kill criteria pass."
            ),
        },
    }


# Paced 30-day build (two "modules" per week spirit — actions, not video dump).
SPRINT_DAYS = 30
SPRINT_MODULES: tuple[dict[str, Any], ...] = (
    {
        "id": "w1_m1_mindset",
        "week": 1,
        "title": "Freedom mindset + messy action",
        "actions": [
            "Write Freedom Number (monthly after-tax) and why",
            "Confirm paper-only lab; live remains blocked",
            "Refuse multi-name / futures / signal-club scope creep",
        ],
    },
    {
        "id": "w1_m2_number",
        "week": 1,
        "title": "Know your number",
        "actions": [
            "Run freedom-number CLI with your monthly target",
            "Compute capital_at_assumed_yield as planning only",
            "Record tax_reserve_rate heuristic (CPA confirms later)",
        ],
    },
    {
        "id": "w2_m3_buckets",
        "week": 2,
        "title": "3-Bucket capital jobs",
        "actions": [
            "List total liquid across Mercury/cash/paper",
            "Allocate ops_safety / lab_validation / field_or_passive",
            "Ensure Field live risk is blocked without EDGE_CANDIDATE",
        ],
    },
    {
        "id": "w2_m4_protocol",
        "week": 2,
        "title": "Income system = validation protocol",
        "actions": [
            "Review put-credit risk framework (1-lot, concurrent, TP/SL/DTE)",
            "Run research protocol baseline + critic audit",
            "Run weekly accountability packet",
        ],
    },
    {
        "id": "w3_m5_account",
        "week": 3,
        "title": "Account hygiene",
        "actions": [
            "Broker sync + inventory audit clean",
            "Reconcile put-credit journal to broker",
            "Confirm credentials path (Keychain paper keys)",
        ],
    },
    {
        "id": "w3_m6_first_structure",
        "week": 3,
        "title": "First / next structure (messy action)",
        "actions": [
            "If concurrent < 2 and regime allows: plan dry-run then paper entry",
            "Journal credit, delta, DTE, regime snapshot",
            "No freehand closes outside manager",
        ],
    },
    {
        "id": "w4_m7_taxes",
        "week": 4,
        "title": "Taxes & distributions hygiene",
        "actions": [
            "Run /llc-tax-ops checklist and quarterly schedule",
            "Keep trading ledger separate from business P&L",
            "SPY options = short-term process; do not invent 1256 for SPY",
        ],
    },
    {
        "id": "w4_m8_beyond",
        "week": 4,
        "title": "First 30 days & beyond",
        "actions": [
            "Score milestones (Foundation → Edge Candidate)",
            "Update Freedom Number if lifestyle costs changed",
            "Only plan live Field deployment after EDGE_CANDIDATE + operator decision",
        ],
    },
)


def build_30_day_sprint(
    *,
    day_index: int = 1,
    checklist_done: dict[str, bool] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Paced 30-day validation sprint status (unlock two modules per week spirit)."""
    now = now or datetime.now(UTC)
    day_index = max(1, min(SPRINT_DAYS, int(day_index)))
    # modules 1-2 week1, 3-4 week2, ...
    week = (day_index - 1) // 7 + 1
    week = min(4, week)
    unlocked = [m for m in SPRINT_MODULES if m["week"] <= week]
    locked = [m for m in SPRINT_MODULES if m["week"] > week]
    done = checklist_done or {}
    progress = []
    for m in SPRINT_MODULES:
        actions = m["actions"]
        completed = sum(1 for i, _a in enumerate(actions) if done.get(f"{m['id']}:{i}"))
        progress.append(
            {
                "id": m["id"],
                "week": m["week"],
                "title": m["title"],
                "unlocked": m["week"] <= week,
                "actions_total": len(actions),
                "actions_done": completed,
                "complete": completed >= len(actions),
            }
        )
    unlocked_complete = sum(1 for p in progress if p["unlocked"] and p["complete"])
    return {
        "schema_version": "freedom-30-day-sprint/1",
        "generated_at": now.isoformat(),
        "day_index": day_index,
        "week": week,
        "modules_unlocked": len(unlocked),
        "modules_locked": len(locked),
        "modules_complete": unlocked_complete,
        "pacing_note": "Two modules per week unlock by design — do worksheets, do not binge.",
        "messy_action_principle": "Messy action beats perfect plan sitting in a note app.",
        "progress": progress,
        "modules": list(SPRINT_MODULES),
        "not_financial_advice": True,
    }


def build_freedom_capital_report(
    *,
    monthly_after_tax: float = DEFAULT_MONTHLY_AFTER_TAX,
    total_liquid: float,
    paper_equity: float | None = None,
    live_edge_candidate: bool = False,
    day_index: int = 1,
    tax_reserve_rate: float = DEFAULT_TAX_RESERVE_RATE,
    assumed_gross_yield_annual: float = DEFAULT_GROSS_YIELD_ANNUAL,
    ops_fraction: float = 0.40,
    lab_fraction: float = 0.35,
    field_fraction: float = 0.25,
) -> dict[str, Any]:
    """Full worksheet: number + buckets + 30-day sprint."""
    fn = compute_freedom_number(
        monthly_after_tax,
        tax_reserve_rate=tax_reserve_rate,
        assumed_gross_yield_annual=assumed_gross_yield_annual,
    )
    buckets = allocate_three_buckets(
        total_liquid,
        ops_fraction=ops_fraction,
        lab_fraction=lab_fraction,
        field_fraction=field_fraction,
        live_edge_candidate=live_edge_candidate,
        paper_equity=paper_equity,
    )
    sprint = build_30_day_sprint(day_index=day_index)
    gap = None
    if paper_equity is not None:
        gap = {
            "paper_equity": paper_equity,
            "freedom_capital_at_yield": fn.capital_at_assumed_yield,
            "capital_gap_to_assumed_passive": round(
                max(0.0, fn.capital_at_assumed_yield - total_liquid), 2
            ),
            "note": "Gap uses assumed yield on total liquid — not trading expectancy.",
        }
    return {
        "schema_version": "freedom-capital-plan/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_inspiration": "income-portfolio bootcamp process (Freedom Number, 3 buckets, 30-day paced build)",
        "freedom_number": fn.as_dict(),
        "three_buckets": buckets,
        "sprint_30_day": sprint,
        "gap": gap,
        "honesty": {
            "not_financial_advice": True,
            "not_stock_picks": True,
            "not_signal_service": True,
            "live_blocked_without_edge": not live_edge_candidate,
        },
    }
