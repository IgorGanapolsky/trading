"""Near-term cash goal vs long-horizon North Star.

CEO near-term: $1,000/month after-tax real money.
North Star (canonical): $6,000/month after-tax (~$300K capital path).

This module never invents edge. It only converts capital + return assumptions
into required economics so operators cannot confuse infra work with profit.
"""

from __future__ import annotations

from typing import Any

# Near-term cash goal (CEO 2026-08). Does not replace NORTH_STAR_MONTHLY_AFTER_TAX.
NEAR_TERM_MONTHLY_AFTER_TAX: float = 1_000.0
# Conservative effective tax drag on SPY equity options (short-term CG).
# Section 1256 (XSP/SPX) can improve this; do not assume 60/40 until we trade it.
DEFAULT_TAX_RATE: float = 0.30
# Paper account reference capital (not a projection of future deposits).
DEFAULT_REFERENCE_EQUITY: float = 100_000.0


def pre_tax_monthly_required(
    after_tax_monthly: float = NEAR_TERM_MONTHLY_AFTER_TAX,
    tax_rate: float = DEFAULT_TAX_RATE,
) -> float:
    """After-tax target → approximate pre-tax monthly requirement."""
    tr = min(max(float(tax_rate), 0.0), 0.9)
    return float(after_tax_monthly) / (1.0 - tr)


def required_monthly_return_pct(equity: float, pre_tax_monthly: float) -> float | None:
    """Pre-tax monthly $ needed as % of equity. None if equity invalid."""
    eq = float(equity or 0.0)
    if eq <= 0:
        return None
    return (float(pre_tax_monthly) / eq) * 100.0


def required_expectancy_per_trade(
    pre_tax_monthly: float,
    *,
    trades_per_month: float,
) -> float | None:
    """If you close N put-credit structures/month, required $ expectancy each."""
    n = float(trades_per_month or 0.0)
    if n <= 0:
        return None
    return float(pre_tax_monthly) / n


def path_economics(
    *,
    paper_equity: float,
    live_equity: float = 0.0,
    closed_n: int = 0,
    expectancy: float | None = None,
    profit_factor: float | None = None,
    kill_verdict: str = "INSUFFICIENT_SAMPLE",
    max_concurrent: int = 2,
    max_daily_structures: int = 3,
    tax_rate: float = DEFAULT_TAX_RATE,
    after_tax_monthly: float = NEAR_TERM_MONTHLY_AFTER_TAX,
) -> dict[str, Any]:
    """Honest economics for the $1k/mo near-term goal (not a forecast)."""
    pre_tax = pre_tax_monthly_required(after_tax_monthly, tax_rate)
    # Realistic cadence upper bound under profile: ~2 concurrent, hold weeks,
    # ~8–12 clean closes/month is optimistic; use 10 as planning midpoint.
    planning_trades_per_month = 10.0
    req_exp = required_expectancy_per_trade(pre_tax, trades_per_month=planning_trades_per_month)
    req_ret_paper = required_monthly_return_pct(paper_equity, pre_tax)
    req_ret_live = required_monthly_return_pct(live_equity, pre_tax) if live_equity > 0 else None

    # Capital needed at 1.5% monthly pre-tax (ambitious defined-risk credit selling)
    # to hit pre_tax: capital = pre_tax / 0.015
    capital_at_1_5pct = pre_tax / 0.015
    capital_at_1_0pct = pre_tax / 0.01

    edge_proven = kill_verdict == "EDGE_CANDIDATE"
    live_ready = edge_proven and live_equity <= 0  # ready to *consider* funding, not auto-deposit

    blockers: list[str] = []
    if kill_verdict == "INSUFFICIENT_SAMPLE":
        blockers.append(f"Put-credit cohort n={closed_n}/30 — no statistical edge claim allowed")
    if kill_verdict == "NO_EDGE_KILL":
        blockers.append("Cohort failed kill criteria — redesign required, not scale")
    if live_equity <= 0:
        blockers.append("Live equity $0 — no real-money engine running")
    if paper_equity < 50_000:
        blockers.append("Paper equity under $50k — validation capital stressed")
    if expectancy is not None and closed_n >= 10 and expectancy <= 0:
        blockers.append(f"Observed expectancy {expectancy} ≤ 0 on partial sample")
    if profit_factor is not None and closed_n >= 10 and profit_factor <= 1:
        blockers.append(f"Observed PF {profit_factor} ≤ 1 on partial sample")
    if not edge_proven:
        blockers.append("live_blocked until EDGE_CANDIDATE (kill switch)")

    return {
        "near_term_after_tax_monthly": after_tax_monthly,
        "assumed_tax_rate": tax_rate,
        "pre_tax_monthly_required": round(pre_tax, 2),
        "paper_equity": round(float(paper_equity), 2),
        "live_equity": round(float(live_equity), 2),
        "required_monthly_return_pct_on_paper": round(req_ret_paper, 3)
        if req_ret_paper is not None
        else None,
        "required_monthly_return_pct_on_live": round(req_ret_live, 3)
        if req_ret_live is not None
        else None,
        "planning_trades_per_month": planning_trades_per_month,
        "required_expectancy_usd_per_trade_at_plan_cadence": round(req_exp, 2)
        if req_exp is not None
        else None,
        "capital_for_goal_at_1pct_monthly_pretax": round(capital_at_1_0pct, 0),
        "capital_for_goal_at_1_5pct_monthly_pretax": round(capital_at_1_5pct, 0),
        "profile_caps": {
            "max_concurrent": max_concurrent,
            "max_daily_structures": max_daily_structures,
        },
        "edge_proven": edge_proven,
        "live_deposit_consideration_allowed": live_ready and edge_proven,
        "blockers": blockers,
        "honesty": (
            "These numbers are requirements and constraints, not forecasts. "
            "With n<30 closed put-credits, projected monthly income is undefined."
        ),
    }
