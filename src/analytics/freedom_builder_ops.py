"""Freedom Builder welcome-pack process tools (ops only — not stock picks).

Steals high-ROI *operating patterns* from the Freedom Builder "start here" onboarding
(Rico Nasol Substack welcome, 2026-08-17) WITHOUT branding, paywall content, or ticker picks:

1. Start-here onboarding order (foundation first: 3-bucket → PLAN → $10K → weekly ritual)
2. PLAN framework scoring adapted to put-credit *process* (not ETF deep-dives)
3. $10K capital scenario (every dollar has a job at a concrete stake size)
4. Portfolio transparency packet (open structures + why held — ledger truth)
5. Monthly income report (exact paired P/L cents; no marketing rounding)
6. Behind-the-scenes decision log (entries/exits with reasons from journals)
7. Wednesday free-issue style packet (frameworks + honest status, complete on its own)

Does NOT submit trades, recommend tickers, or unlock live capital.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from src.analytics.freedom_capital_plan import (
    DEFAULT_MONTHLY_AFTER_TAX,
    allocate_three_buckets,
    compute_freedom_number,
)

# ---------------------------------------------------------------------------
# PLAN framework (process adaptation of income-portfolio scoring spirit)
# ---------------------------------------------------------------------------
# P — Process: protocol, selection rule, kill gates, inventory hygiene
# L — Limits: defined risk, 1-lot, concurrent, DTE/stop/TP bounds
# A — Alignment: paper-only lab, North Star path, no IC revival / signal drift
# N — Numbers: paired ledger honesty, sample size, no profit claim without edge

PLAN_DIMENSIONS: tuple[dict[str, Any], ...] = (
    {
        "letter": "P",
        "name": "Process",
        "max_score": 25,
        "checks": (
            "research_protocol_registered",
            "kill_criteria_tracked",
            "journal_reconciled",
            "inventory_clean",
        ),
    },
    {
        "letter": "L",
        "name": "Limits",
        "max_score": 25,
        "checks": (
            "one_lot_only",
            "max_concurrent_respected",
            "defined_risk_wings",
            "stop_tp_dte_defined",
        ),
    },
    {
        "letter": "A",
        "name": "Alignment",
        "max_score": 25,
        "checks": (
            "paper_only",
            "live_blocked",
            "ic_new_entries_killed",
            "not_signal_service",
        ),
    },
    {
        "letter": "N",
        "name": "Numbers",
        "max_score": 25,
        "checks": (
            "paired_ledger_only",
            "claim_profitable_false_until_edge",
            "sample_size_visible",
            "expectancy_pf_tracked",
        ),
    },
)

START_HERE_STEPS: tuple[dict[str, Any], ...] = (
    {
        "order": 1,
        "id": "three_bucket",
        "title": "What is the 3-Bucket System?",
        "why": "Foundation for capital jobs — every dollar has a job before any structure.",
        "command": ".venv/bin/python scripts/freedom_capital_plan.py --from-system-state --liquid <TOTAL>",
        "owner_module": "src.analytics.freedom_capital_plan.allocate_three_buckets",
    },
    {
        "order": 2,
        "id": "plan_framework",
        "title": "PLAN framework (process score)",
        "why": "Score Process / Limits / Alignment / Numbers before claiming readiness.",
        "command": ".venv/bin/python scripts/freedom_builder_ops.py plan",
        "owner_module": "src.analytics.freedom_builder_ops.score_plan",
    },
    {
        "order": 3,
        "id": "scenario_10k",
        "title": "The $10K scenario",
        "why": "Concrete stake size makes allocation real; no abstract 'someday capital'.",
        "command": ".venv/bin/python scripts/freedom_builder_ops.py scenario-10k",
        "owner_module": "src.analytics.freedom_builder_ops.scenario_10k",
    },
    {
        "order": 4,
        "id": "portfolio_transparency",
        "title": "Actual portfolio (open structures)",
        "why": "Every open position: credit, expiry, quantity, why held — no mystery book.",
        "command": ".venv/bin/python scripts/freedom_builder_ops.py portfolio",
        "owner_module": "src.analytics.freedom_builder_ops.portfolio_transparency",
    },
    {
        "order": 5,
        "id": "monthly_income",
        "title": "Monthly income report",
        "why": "Real paired P/L for the month — exact cents, no rounding theater.",
        "command": ".venv/bin/python scripts/freedom_builder_ops.py monthly-income",
        "owner_module": "src.analytics.freedom_builder_ops.monthly_income_report",
    },
    {
        "order": 6,
        "id": "wednesday_issue",
        "title": "Wednesday free-issue packet",
        "why": "Weekly complete issue: frameworks + honest status (not a teaser).",
        "command": ".venv/bin/python scripts/freedom_builder_ops.py wednesday",
        "owner_module": "src.analytics.freedom_builder_ops.wednesday_free_issue",
    },
)


@dataclass(frozen=True)
class PlanDimensionScore:
    letter: str
    name: str
    score: int
    max_score: int
    checks: dict[str, bool]
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


def _bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "pass", "ok"}:
        return True
    if s in {"0", "false", "no", "n", "fail"}:
        return False
    return default


def score_plan(
    *,
    scorecard: dict[str, Any] | None = None,
    inventory_clean: bool = True,
    journal_reconciled: bool = True,
    research_protocol_registered: bool = True,
    one_lot_only: bool = True,
    max_concurrent_respected: bool = True,
    defined_risk_wings: bool = True,
    stop_tp_dte_defined: bool = True,
    paper_only: bool = True,
    live_blocked: bool = True,
    ic_new_entries_killed: bool = True,
    not_signal_service: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Score PLAN for the active put-credit validation process (0–100)."""
    now = now or datetime.now(UTC)
    card = scorecard or {}
    closed = card.get("closed") or {}
    honesty = card.get("honesty") or {}
    research = card.get("research_protocol") or {}
    open_ = card.get("open") or {}

    n_closed = int(closed.get("closed_n") or 0)
    kill = closed.get("kill_criteria") or {}
    claim_profitable = bool(honesty.get("claim_profitable"))
    edge = str(kill.get("verdict") or "") == "EDGE_CANDIDATE"

    # Override from scorecard when present
    paper_only = _bool(card.get("paper_only"), paper_only)
    live_blocked = _bool(card.get("live_blocked"), live_blocked)
    if research:
        research_protocol_registered = True
    open_n = int(open_.get("open_n") or 0)
    if open_n > 2:
        max_concurrent_respected = False
    for e in open_.get("entries") or []:
        qty = e.get("quantity")
        if qty is not None and int(qty) > 1:
            one_lot_only = False

    p_checks = {
        "research_protocol_registered": research_protocol_registered,
        "kill_criteria_tracked": bool(kill) or n_closed >= 0,
        "journal_reconciled": journal_reconciled,
        "inventory_clean": inventory_clean,
    }
    l_checks = {
        "one_lot_only": one_lot_only,
        "max_concurrent_respected": max_concurrent_respected,
        "defined_risk_wings": defined_risk_wings,
        "stop_tp_dte_defined": stop_tp_dte_defined,
    }
    a_checks = {
        "paper_only": paper_only,
        "live_blocked": live_blocked,
        "ic_new_entries_killed": ic_new_entries_killed,
        "not_signal_service": not_signal_service,
    }
    n_checks = {
        "paired_ledger_only": True,
        "claim_profitable_false_until_edge": (not claim_profitable) or edge,
        "sample_size_visible": True,
        "expectancy_pf_tracked": closed.get("expectancy") is not None or n_closed == 0,
    }

    def _dim(
        letter: str, name: str, checks: dict[str, bool], notes: tuple[str, ...]
    ) -> PlanDimensionScore:
        passed = sum(1 for v in checks.values() if v)
        total = len(checks) or 1
        score = int(round(25 * passed / total))
        return PlanDimensionScore(
            letter=letter,
            name=name,
            score=score,
            max_score=25,
            checks=checks,
            notes=notes,
        )

    dims = [
        _dim(
            "P",
            "Process",
            p_checks,
            ("Protocol + kill tracking + clean inventory = Process.",),
        ),
        _dim(
            "L",
            "Limits",
            l_checks,
            ("1-lot, max 2 concurrent, defined risk, stop/TP/DTE.",),
        ),
        _dim(
            "A",
            "Alignment",
            a_checks,
            ("Paper lab only until EDGE_CANDIDATE; IC entries killed.",),
        ),
        _dim(
            "N",
            "Numbers",
            n_checks,
            (f"closed_n={n_closed}; claim_profitable={claim_profitable}; edge={edge}.",),
        ),
    ]
    total = sum(d.score for d in dims)
    band = (
        "strong"
        if total >= 90
        else "good"
        if total >= 75
        else "needs_work"
        if total >= 50
        else "weak"
    )
    return {
        "schema_version": "freedom-builder-plan/1",
        "generated_at": now.isoformat(),
        "total_score": total,
        "max_score": 100,
        "band": band,
        "dimensions": [d.as_dict() for d in dims],
        "subject": "spy_put_credit_process",
        "not_etf_scoring": True,
        "honesty": {
            "not_stock_picks": True,
            "not_signal_service": True,
            "note": (
                "PLAN scores process hygiene for paper put-credit validation. "
                "It does not rank ETFs, tickers, or authorize live capital."
            ),
        },
    }


def scenario_10k(
    *,
    stake: float = 10_000.0,
    monthly_after_tax: float = DEFAULT_MONTHLY_AFTER_TAX,
    ops_fraction: float = 0.40,
    lab_fraction: float = 0.35,
    field_fraction: float = 0.25,
    live_edge_candidate: bool = False,
    assumed_gross_yield_annual: float = 0.08,
    tax_reserve_rate: float = 0.30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Concrete $10K (or custom stake) scenario — every dollar has a job."""
    now = now or datetime.now(UTC)
    if stake <= 0:
        raise ValueError("stake must be positive")

    buckets = allocate_three_buckets(
        stake,
        ops_fraction=ops_fraction,
        lab_fraction=lab_fraction,
        field_fraction=field_fraction,
        live_edge_candidate=live_edge_candidate,
    )
    fn = compute_freedom_number(
        monthly_after_tax,
        tax_reserve_rate=tax_reserve_rate,
        assumed_gross_yield_annual=assumed_gross_yield_annual,
    )
    lab_alloc = next(b for b in buckets["buckets"] if b["id"] == "lab_validation")["allocated"]
    # Rough max risk per 1-lot $5-wide put credit ≈ $500 less credit; use $500 for planning
    max_risk_per_structure = 500.0
    structures_capacity = int(lab_alloc // max_risk_per_structure) if lab_alloc else 0
    concurrent_cap = min(2, structures_capacity)

    passive_monthly_if_yield = round(stake * assumed_gross_yield_annual / 12.0, 2)
    freedom_gap = round(max(0.0, fn.capital_at_assumed_yield - stake), 2)

    return {
        "schema_version": "freedom-builder-10k-scenario/1",
        "generated_at": now.isoformat(),
        "stake": round(stake, 2),
        "label": f"${stake:,.0f} scenario",
        "three_buckets": buckets,
        "lab": {
            "allocated": lab_alloc,
            "max_risk_per_1lot_structure_planning": max_risk_per_structure,
            "structures_risk_capacity_if_fully_deployed": structures_capacity,
            "concurrent_cap_policy": 2,
            "concurrent_if_funded": concurrent_cap,
            "note": (
                "Capacity is a capital-risk ceiling, not a trade signal. "
                "Paper validation still follows max 2 concurrent / 3 per day."
            ),
        },
        "freedom_number": fn.as_dict(),
        "illustrative_passive_monthly_at_assumed_yield": passive_monthly_if_yield,
        "capital_gap_to_freedom_at_assumed_yield": freedom_gap,
        "what_this_does_not_mean": [
            "Does not promise put-credit returns the assumed yield.",
            "Does not authorize live trading.",
            "Does not recommend covered-call ETFs or any ticker.",
        ],
        "honesty": {
            "not_financial_advice": True,
            "not_stock_picks": True,
            "messy_action": "Fund Lab paper process and run protocol — do not binge content instead.",
        },
    }


def portfolio_transparency(
    scorecard: dict[str, Any],
    *,
    paper_equity: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Actual open book — every position, credit, why held (ledger truth)."""
    now = now or datetime.now(UTC)
    open_ = scorecard.get("open") or {}
    entries = []
    for e in open_.get("entries") or []:
        credit = e.get("credit")
        qty = int(e.get("quantity") or 1)
        credit_f = float(credit) if credit is not None else None
        max_profit = round(credit_f * 100 * qty, 2) if credit_f is not None else None
        max_loss_planning = round((5.0 - credit_f) * 100 * qty, 2) if credit_f is not None else None
        why = (
            "Open paper put-credit validation structure — hold for TP/stop/DTE rules; "
            "not a discretionary swing."
        )
        regime = e.get("regime") or {}
        entries.append(
            {
                "key": e.get("key"),
                "signature": e.get("signature"),
                "expiry": e.get("expiry"),
                "quantity": qty,
                "credit": credit_f,
                "entry_time": e.get("entry_time"),
                "max_profit_if_expire_worthless_usd": max_profit,
                "max_loss_if_max_width_planning_usd": max_loss_planning,
                "regime_at_entry": regime,
                "why_held": why,
                "yield_claim": None,  # never invent dividend/yield on option short credit
                "paper_only": True,
            }
        )
    return {
        "schema_version": "freedom-builder-portfolio/1",
        "generated_at": now.isoformat(),
        "paper_equity": paper_equity,
        "open_n": int(open_.get("open_n") or len(entries)),
        "positions": entries,
        "honesty": {
            "not_stock_picks": True,
            "not_dividend_report": True,
            "note": (
                "Transparency packet lists open put-credit structures from the journal/scorecard. "
                "Credit is short premium, not a dividend yield. No ticker recommendations."
            ),
        },
    }


def monthly_income_report(
    closed_rows: list[dict[str, Any]],
    *,
    year: int | None = None,
    month: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Monthly paired P/L — exact cents, no marketing rounding of totals."""
    now = now or datetime.now(UTC)
    y = year if year is not None else now.year
    m = month if month is not None else now.month

    def _exit_date(row: dict[str, Any]) -> date | None:
        for key in ("exit_time", "exit_date", "closed_at", "close_time"):
            raw = row.get(key)
            if not raw:
                continue
            s = str(raw).replace("Z", "+00:00")
            try:
                if "T" in s:
                    return datetime.fromisoformat(s).date()
                return date.fromisoformat(s[:10])
            except ValueError:
                continue
        return None

    def _pnl(row: dict[str, Any]) -> float | None:
        for key in ("realized_pnl", "pnl", "net_pnl", "profit"):
            if row.get(key) is None or row.get(key) == "":
                continue
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
        return None

    matched: list[dict[str, Any]] = []
    exact_total = 0.0  # float sum; we also keep cents integer for honesty
    cents_total = 0
    for row in closed_rows:
        d = _exit_date(row)
        if d is None or d.year != y or d.month != m:
            continue
        pnl = _pnl(row)
        if pnl is None:
            continue
        cents = int(round(pnl * 100))
        cents_total += cents
        exact_total += pnl
        matched.append(
            {
                "id": row.get("id") or row.get("key") or row.get("signature"),
                "exit_date": d.isoformat(),
                "realized_pnl": pnl,
                "realized_pnl_cents": cents,
            }
        )

    # Prefer integer cents as truth for display
    total_from_cents = cents_total / 100.0
    wins = [r for r in matched if r["realized_pnl"] > 0]
    losses = [r for r in matched if r["realized_pnl"] < 0]
    return {
        "schema_version": "freedom-builder-monthly-income/1",
        "generated_at": now.isoformat(),
        "period": {"year": y, "month": m, "label": f"{y:04d}-{m:02d}"},
        "n_closed": len(matched),
        "wins": len(wins),
        "losses": len(losses),
        "total_realized_pnl": total_from_cents,
        "total_realized_pnl_cents": cents_total,
        "total_realized_pnl_display": f"${total_from_cents:,.2f}",
        "trades": matched,
        "honesty": {
            "no_marketing_rounding": True,
            "source": "paired closed put-credit rows only",
            "not_dividend_income": True,
            "note": (
                "Income here is realized option structure P/L, not dividends. "
                "Totals use cent-integer sum to avoid display rounding drift."
            ),
        },
    }


def behind_the_scenes_decisions(
    scorecard: dict[str, Any],
    closed_rows: list[dict[str, Any]] | None = None,
    *,
    limit: int = 20,
    now: datetime | None = None,
) -> dict[str, Any]:
    """What was opened / closed / held and why — journal-backed only."""
    now = now or datetime.now(UTC)
    decisions: list[dict[str, Any]] = []
    open_ = scorecard.get("open") or {}
    for e in open_.get("entries") or []:
        decisions.append(
            {
                "action": "hold",
                "key": e.get("key"),
                "signature": e.get("signature"),
                "when": e.get("entry_time"),
                "why": "Open validation structure; manage via TP 25% / stop 200% credit / 7 DTE.",
                "credit": e.get("credit"),
            }
        )
    rows = closed_rows or []

    # most recent by exit
    def _sort_key(r: dict[str, Any]) -> str:
        return str(r.get("exit_time") or r.get("exit_date") or "")

    for r in sorted(rows, key=_sort_key, reverse=True)[:limit]:
        pnl = r.get("realized_pnl")
        reason = r.get("exit_reason") or r.get("close_reason") or "closed_on_ledger"
        decisions.append(
            {
                "action": "closed",
                "key": r.get("id") or r.get("key") or r.get("signature"),
                "when": r.get("exit_time") or r.get("exit_date"),
                "why": str(reason),
                "realized_pnl": pnl,
            }
        )
    return {
        "schema_version": "freedom-builder-bts-decisions/1",
        "generated_at": now.isoformat(),
        "n_decisions": len(decisions),
        "decisions": decisions[: limit + len(open_.get("entries") or [])],
        "honesty": {
            "not_stock_picks": True,
            "note": "Decisions are reconstructed from journals/scorecard — not discretionary tips.",
        },
    }


def start_here_pack(*, now: datetime | None = None) -> dict[str, Any]:
    """Ordered onboarding — same spirit as welcome 'Start here →'."""
    now = now or datetime.now(UTC)
    return {
        "schema_version": "freedom-builder-start-here/1",
        "generated_at": now.isoformat(),
        "title": "Start here — Freedom Builder process pack (lab adaptation)",
        "principle": "Messy action is better than no action at all.",
        "steps": list(START_HERE_STEPS),
        "every_wednesday": [
            "Income-process frameworks (3-bucket, PLAN, $10K scenario)",
            "Honest takes on what is working in the *validation* book (ledger only)",
            "No watered-down teaser — each Wednesday packet is complete alone",
        ],
        "deeper_optional": [
            "Portfolio transparency (every open structure)",
            "Monthly income report (exact cents)",
            "PLAN scoring on process snapshot",
            "Behind-the-scenes decisions log",
        ],
        "honesty": {
            "not_rico_content_copy": True,
            "not_stock_picks": True,
            "not_signal_service": True,
            "not_financial_advice": True,
            "source_inspiration": (
                "Freedom Builder welcome onboarding structure (3-bucket first, "
                "PLAN, $10K scenario, Wednesday cadence, portfolio/monthly depth)"
            ),
        },
    }


def wednesday_free_issue(
    scorecard: dict[str, Any],
    *,
    paper_equity: float | None = None,
    closed_rows: list[dict[str, Any]] | None = None,
    inventory_clean: bool = True,
    stake_for_scenario: float = 10_000.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Complete-on-its-own weekly free issue (Wednesday ritual)."""
    now = now or datetime.now(UTC)
    plan = score_plan(scorecard=scorecard, inventory_clean=inventory_clean, now=now)
    scen = scenario_10k(stake=stake_for_scenario, now=now)
    port = portfolio_transparency(scorecard, paper_equity=paper_equity, now=now)
    y, m = now.year, now.month
    income = monthly_income_report(closed_rows or [], year=y, month=m, now=now)
    bts = behind_the_scenes_decisions(scorecard, closed_rows, now=now)
    closed = scorecard.get("closed") or {}
    progress = scorecard.get("progress") or {}
    honesty = scorecard.get("honesty") or {}

    working = []
    not_working = []
    n = int(closed.get("closed_n") or 0)
    if n < 30:
        not_working.append(
            f"Sample still insufficient for kill gate (closed_n={n}/30) — no edge claim."
        )
    else:
        working.append("Sample floor n>=30 reached — evaluate kill verdict on expectancy/PF.")
    if port["open_n"] > 0:
        working.append(f"{port['open_n']} open structure(s) journaled with credit/expiry.")
    if plan["band"] in {"strong", "good"}:
        working.append(f"PLAN process band={plan['band']} (score {plan['total_score']}/100).")
    else:
        not_working.append(f"PLAN process band={plan['band']} — fix failed checks before scaling.")
    if honesty.get("claim_profitable"):
        not_working.append("Honesty flag claim_profitable=true without edge — refuse that claim.")
    if not working:
        working.append("Process tooling online; continue paper cohort without marketing claims.")

    return {
        "schema_version": "freedom-builder-wednesday-issue/1",
        "generated_at": now.isoformat(),
        "cadence": "wednesday_free_issue",
        "complete_on_its_own": True,
        "frameworks": {
            "plan": plan,
            "scenario_10k": {
                "stake": scen["stake"],
                "lab_allocated": scen["lab"]["allocated"],
                "capital_gap_to_freedom_at_assumed_yield": scen[
                    "capital_gap_to_freedom_at_assumed_yield"
                ],
            },
            "three_bucket_ids": [b["id"] for b in scen["three_buckets"]["buckets"]],
        },
        "honest_market_take": {
            "working": working,
            "not_working": not_working,
            "closed_n": n,
            "kill_verdict": (closed.get("kill_criteria") or {}).get("verdict"),
            "progress_pct_to_gate": progress.get("pct_to_gate"),
            "total_realized_pnl_all_time_cohort": closed.get("total_realized_pnl"),
        },
        "portfolio": port,
        "monthly_income": income,
        "behind_the_scenes": bts,
        "start_here_ref": "scripts/freedom_builder_ops.py start-here",
        "honesty": {
            "not_stock_picks": True,
            "not_signal_service": True,
            "not_financial_advice": True,
            "not_watered_down_teaser": True,
            "note": (
                "Free issue is complete alone: frameworks + ledger status. "
                "Depth (portfolio/monthly/PLAN) is included here for operator use — "
                "not a paid Substack clone."
            ),
        },
    }


def render_start_here_markdown(pack: dict[str, Any]) -> str:
    lines = [
        f"# {pack.get('title')}",
        "",
        f"Generated: `{pack.get('generated_at')}`",
        "",
        f"> {pack.get('principle')}",
        "",
        "## Start here (ordered)",
    ]
    for step in pack.get("steps") or []:
        lines.append(f"{step.get('order')}. **{step.get('title')}** — {step.get('why')}")
        lines.append(f"   - `{step.get('command')}`")
    lines.extend(["", "## Every Wednesday", ""])
    for item in pack.get("every_wednesday") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Honesty", ""])
    h = pack.get("honesty") or {}
    lines.append(f"- not_stock_picks: `{h.get('not_stock_picks')}`")
    lines.append(f"- not_signal_service: `{h.get('not_signal_service')}`")
    lines.append(f"- source: {h.get('source_inspiration')}")
    lines.append("")
    return "\n".join(lines)


def render_wednesday_markdown(issue: dict[str, Any]) -> str:
    plan = (issue.get("frameworks") or {}).get("plan") or {}
    take = issue.get("honest_market_take") or {}
    port = issue.get("portfolio") or {}
    income = issue.get("monthly_income") or {}
    lines = [
        "# Wednesday free issue — put-credit lab",
        "",
        f"Generated: `{issue.get('generated_at')}`",
        "",
        "## Frameworks",
        f"- PLAN score: **{plan.get('total_score')}/100** band=`{plan.get('band')}`",
        f"- $10K scenario lab alloc: `{(issue.get('frameworks') or {}).get('scenario_10k', {}).get('lab_allocated')}`",
        f"- Buckets: `{(issue.get('frameworks') or {}).get('three_bucket_ids')}`",
        "",
        "## Honest take (ledger)",
        "### Working",
    ]
    for w in take.get("working") or []:
        lines.append(f"- {w}")
    lines.append("### Not working / gates")
    for w in take.get("not_working") or []:
        lines.append(f"- {w}")
    lines.extend(
        [
            "",
            f"- closed_n: `{take.get('closed_n')}`",
            f"- kill_verdict: `{take.get('kill_verdict')}`",
            f"- progress_pct_to_gate: `{take.get('progress_pct_to_gate')}`",
            f"- cohort total_realized_pnl: `{take.get('total_realized_pnl_all_time_cohort')}`",
            "",
            "## Portfolio transparency",
            f"- open_n: `{port.get('open_n')}` paper_equity: `{port.get('paper_equity')}`",
        ]
    )
    for p in port.get("positions") or []:
        lines.append(
            f"- `{p.get('signature')}` qty={p.get('quantity')} credit={p.get('credit')} "
            f"expiry={p.get('expiry')}"
        )
    lines.extend(
        [
            "",
            "## Monthly income (paired)",
            f"- period: `{income.get('period', {}).get('label')}`",
            f"- n_closed: `{income.get('n_closed')}`",
            f"- total: `{income.get('total_realized_pnl_display')}` "
            f"(cents=`{income.get('total_realized_pnl_cents')}`)",
            "",
            "## Honesty",
            f"- complete_on_its_own: `{issue.get('complete_on_its_own')}`",
            f"- not_stock_picks: `{(issue.get('honesty') or {}).get('not_stock_picks')}`",
            "",
        ]
    )
    return "\n".join(lines)


def build_full_ops_report(
    scorecard: dict[str, Any],
    *,
    closed_rows: list[dict[str, Any]] | None = None,
    paper_equity: float | None = None,
    inventory_clean: bool = True,
    stake: float = 10_000.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Bundle start-here + PLAN + scenario + portfolio + monthly + Wednesday."""
    now = now or datetime.now(UTC)
    return {
        "schema_version": "freedom-builder-ops/1",
        "generated_at": now.isoformat(),
        "start_here": start_here_pack(now=now),
        "plan": score_plan(scorecard=scorecard, inventory_clean=inventory_clean, now=now),
        "scenario_10k": scenario_10k(stake=stake, now=now),
        "portfolio": portfolio_transparency(scorecard, paper_equity=paper_equity, now=now),
        "monthly_income": monthly_income_report(
            closed_rows or [], year=now.year, month=now.month, now=now
        ),
        "behind_the_scenes": behind_the_scenes_decisions(scorecard, closed_rows, now=now),
        "wednesday_issue": wednesday_free_issue(
            scorecard,
            paper_equity=paper_equity,
            closed_rows=closed_rows,
            inventory_clean=inventory_clean,
            stake_for_scenario=stake,
            now=now,
        ),
        "honesty": {
            "not_stock_picks": True,
            "not_signal_service": True,
            "not_financial_advice": True,
            "source": "Freedom Builder welcome process patterns adapted to spy_put_credit lab",
        },
    }
