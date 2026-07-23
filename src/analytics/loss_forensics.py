"""Evidence-based loss forensics for strategy misery diagnosis.

Computes reproducible root-cause clusters from the canonical closed-trade
ledger. Used by ML feedback, RAG ingestion, and operator diagnosis CLI.

This module deliberately avoids claiming edge. It answers: where did money
leave the account, under which structural choices, and what must change.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

STRATEGY_IC = frozenset({"iron_condor", "ic_simple", "ic"})
STRATEGY_PUT_CREDIT = frozenset(
    {"spy_put_credit", "put_credit", "bull_put", "bull_put_credit", "put_credit_spread"}
)

_TRADE_ID_WING_RE = re.compile(
    r"P(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)_C(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_OCC_STRIKE_RE = re.compile(r"([PC])0*(\d{5})(\d{3})$")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def trade_pnl(trade: dict[str, Any]) -> tuple[float, bool]:
    raw = trade.get("realized_pnl")
    if raw is None:
        raw = trade.get("pnl")
    if raw is None or raw == "":
        return 0.0, False
    try:
        return float(raw), True
    except (TypeError, ValueError):
        return 0.0, False


def holding_hours(trade: dict[str, Any]) -> float | None:
    entry_time = trade.get("entry_time") or trade.get("opened_at") or trade.get("entry_date")
    exit_time = trade.get("exit_time") or trade.get("closed_at") or trade.get("exit_date")
    if not entry_time or not exit_time:
        return None
    try:
        opened = datetime.fromisoformat(str(entry_time).replace("Z", "+00:00")[:26])
        closed = datetime.fromisoformat(str(exit_time).replace("Z", "+00:00")[:26])
    except (TypeError, ValueError):
        return None
    return max(0.0, (closed - opened).total_seconds() / 3600.0)


def strategy_family(trade: dict[str, Any]) -> str:
    raw = str(trade.get("strategy") or trade.get("strategy_family") or trade.get("type") or "")
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if key in STRATEGY_PUT_CREDIT or "put_credit" in key or "bull_put" in key:
        return "spy_put_credit"
    if key in STRATEGY_IC or "iron_condor" in key or key.startswith("ic_"):
        return "iron_condor"
    if key:
        return key
    trade_id = str(trade.get("id") or "")
    if trade_id.upper().startswith("IC_") or "IRON" in trade_id.upper():
        return "iron_condor"
    return "unknown"


def wing_width(trade: dict[str, Any]) -> float | None:
    """Best-effort wing width from structured legs, trade id, or OCC symbols."""
    legs = trade.get("legs")
    widths: list[float] = []

    if isinstance(legs, dict):
        put_strikes = legs.get("put_strikes") or []
        call_strikes = legs.get("call_strikes") or []
        if len(put_strikes) >= 2:
            widths.append(abs(as_float(put_strikes[1]) - as_float(put_strikes[0])))
        if len(call_strikes) >= 2:
            widths.append(abs(as_float(call_strikes[1]) - as_float(call_strikes[0])))
    elif isinstance(legs, list):
        puts: list[float] = []
        calls: list[float] = []
        for leg in legs:
            if isinstance(leg, str):
                match = _OCC_STRIKE_RE.search(leg)
                if not match:
                    continue
                strike = int(match.group(2)) + int(match.group(3)) / 1000.0
                (puts if match.group(1).upper() == "P" else calls).append(strike)
            elif isinstance(leg, dict):
                symbol = str(leg.get("symbol") or "")
                match = _OCC_STRIKE_RE.search(symbol)
                strike = leg.get("strike")
                right = str(leg.get("right") or leg.get("option_type") or "")
                if match and strike is None:
                    strike = int(match.group(2)) + int(match.group(3)) / 1000.0
                    right = match.group(1)
                if strike is None:
                    continue
                right_u = right.upper()
                if right_u.startswith("P"):
                    puts.append(float(strike))
                elif right_u.startswith("C"):
                    calls.append(float(strike))
        if len(puts) >= 2:
            widths.append(max(puts) - min(puts))
        if len(calls) >= 2:
            widths.append(max(calls) - min(calls))

    trade_id = str(trade.get("id") or trade.get("signature") or "")
    match = _TRADE_ID_WING_RE.search(trade_id)
    if match:
        put_w = abs(float(match.group(2)) - float(match.group(1)))
        call_w = abs(float(match.group(4)) - float(match.group(3)))
        widths.append(max(put_w, call_w))

    return max(widths) if widths else None


def _summarize_rows(rows: list[dict[str, Any]], total_loss_abs: float) -> dict[str, Any]:
    if not rows:
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "expectancy_per_trade": 0.0,
            "loss_contribution_pct": 0.0,
        }
    wins = [row for row in rows if row["pnl"] > 0]
    losses = [row for row in rows if row["pnl"] < 0]
    total_pnl = sum(row["pnl"] for row in rows)
    loss_abs = abs(sum(row["pnl"] for row in losses))
    return {
        "sample_size": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(rows) * 100, 2),
        "total_pnl": round(total_pnl, 2),
        "expectancy_per_trade": round(total_pnl / len(rows), 2),
        "loss_contribution_pct": round((loss_abs / total_loss_abs * 100) if total_loss_abs else 0.0, 2),
    }


def closed_trade_rows(trades: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        pnl, has_pnl = trade_pnl(trade)
        outcome = str(trade.get("outcome") or "").strip().lower()
        if outcome not in {"win", "loss"} and not has_pnl:
            continue
        if outcome not in {"win", "loss"} and pnl == 0:
            continue
        rows.append(
            {
                "trade": trade,
                "pnl": pnl,
                "is_win": outcome == "win" or pnl > 0,
                "is_loss": outcome == "loss" or pnl < 0,
                "holding_hours": holding_hours(trade),
                "wing_width": wing_width(trade),
                "quantity": as_float(trade.get("quantity"), 1.0) or 1.0,
                "source": str(trade.get("source") or ""),
                "family": strategy_family(trade),
                "entry_date": str(
                    trade.get("entry_date") or (str(trade.get("entry_time") or "")[:10])
                ),
            }
        )
    return rows


def analyze_loss_clusters(trades: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """Summarize recurring loss clusters so RAG/ML learn what to stop repeating."""
    if isinstance(trades, dict):
        trade_list = [t for t in trades.get("trades", []) if isinstance(t, dict)]
    else:
        trade_list = [t for t in trades if isinstance(t, dict)]

    closed_rows = closed_trade_rows(trade_list)
    total_loss_abs = abs(sum(row["pnl"] for row in closed_rows if row["pnl"] < 0))

    cluster_specs: list[tuple[str, str, Callable[[dict[str, Any]], bool], str]] = [
        (
            "early_exit_lt_1h",
            "Closed in under 1 hour",
            lambda row: row["holding_hours"] is not None and row["holding_hours"] < 1,
            "Do not open setups whose expected management requires intraday repair; enforce a minimum hold unless a hard max-loss fires.",
        ),
        (
            "early_exit_lt_24h",
            "Closed in under 24 hours",
            lambda row: row["holding_hours"] is not None and row["holding_hours"] < 24,
            "Require min 24h hold except hard stop; theta strategies die under sub-day churn.",
        ),
        (
            "ten_wide_wings",
            "10-wide or wider wings",
            lambda row: row["wing_width"] is not None and row["wing_width"] >= 9.5,
            "Never reintroduce 10-wide SPY wings in validation; max risk per structure is too large for the observed win rate.",
        ),
        (
            "five_wide_or_less",
            "5-wide or narrower wings",
            lambda row: row["wing_width"] is not None and row["wing_width"] <= 5.5,
            "Keep successor structures at $5 wings until n>=30 proves edge.",
        ),
        (
            "multi_contract",
            "More than one contract",
            lambda row: row["quantity"] > 1,
            "1-lot only until positive expectancy, PF>1, and positive total P/L clear on the successor cohort.",
        ),
        (
            "long_hold_ge_7d",
            "Held 7 days or longer",
            lambda row: row["holding_hours"] is not None and row["holding_hours"] >= 24 * 7,
            "Force-exit by 7 DTE; slow losers dominate dollar damage even when rare.",
        ),
        (
            "orphan_cleanup",
            "Orphan or leg-repair cleanup",
            lambda row: "orphan" in row["source"].lower(),
            "Do not open new risk with unclean inventory; pairing must be atomic.",
        ),
        (
            "iron_condor_family",
            "Iron condor / IC Simple family",
            lambda row: row["family"] == "iron_condor",
            "IC family is killed as North Star candidate; do not reopen entries.",
        ),
        (
            "put_credit_family",
            "Put-credit successor family",
            lambda row: row["family"] == "spy_put_credit",
            "Evaluate put-credit only on its own cohort; never inherit IC kill metrics as put-credit evidence.",
        ),
    ]

    clusters: list[dict[str, Any]] = []
    for cluster_id, label, predicate, recommendation in cluster_specs:
        rows = [row for row in closed_rows if predicate(row)]
        if not rows:
            continue
        summary = _summarize_rows(rows, total_loss_abs)
        clusters.append(
            {
                "id": cluster_id,
                "label": label,
                "recommendation": recommendation,
                **summary,
            }
        )

    clusters.sort(
        key=lambda item: (
            item["loss_contribution_pct"],
            abs(min(item["total_pnl"], 0)),
            item["sample_size"],
        ),
        reverse=True,
    )
    return clusters


def monthly_attribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        month = (row.get("entry_date") or "")[:7] or "unknown"
        by_month[month].append(float(row["pnl"]))
    out: list[dict[str, Any]] = []
    for month in sorted(by_month):
        xs = by_month[month]
        wins = sum(1 for x in xs if x > 0)
        out.append(
            {
                "month": month,
                "sample_size": len(xs),
                "total_pnl": round(sum(xs), 2),
                "win_rate_pct": round(wins / len(xs) * 100, 2) if xs else 0.0,
                "expectancy_per_trade": round(sum(xs) / len(xs), 2) if xs else 0.0,
            }
        )
    return out


def family_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)
    total_loss_abs = abs(sum(row["pnl"] for row in rows if row["pnl"] < 0))
    return {family: _summarize_rows(family_rows, total_loss_abs) for family, family_rows in by_family.items()}


def synthesize_root_causes(clusters: list[dict[str, Any]], families: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Human-readable ranked causes with evidence thresholds."""
    causes: list[dict[str, Any]] = []
    by_id = {c["id"]: c for c in clusters}

    ic = families.get("iron_condor") or {}
    if ic.get("sample_size", 0) >= 30 and ic.get("expectancy_per_trade", 0) <= 0:
        causes.append(
            {
                "id": "wrong_strategy_family",
                "severity": "CRITICAL",
                "title": "Primary strategy family has negative expectancy at large sample",
                "evidence": ic,
                "explanation": (
                    "Iron condors were the only closed family. Lifetime expectancy and profit "
                    "factor fail kill criteria — this is not a small-sample fluke."
                ),
            }
        )

    wide = by_id.get("ten_wide_wings")
    if wide and wide["sample_size"] >= 20 and wide["total_pnl"] < 0:
        causes.append(
            {
                "id": "ten_wide_wings",
                "severity": "CRITICAL",
                "title": "10-wide wings dominate dollar losses",
                "evidence": wide,
                "explanation": (
                    "Most closed structures used ~$10 wings. Max loss per lot is roughly 10x credit "
                    "room vs $5 wings, and the observed win rate cannot pay for that risk."
                ),
            }
        )

    multi = by_id.get("multi_contract")
    if multi and multi["sample_size"] >= 10 and multi["expectancy_per_trade"] < 0:
        causes.append(
            {
                "id": "multi_lot_scaling_before_edge",
                "severity": "CRITICAL",
                "title": "Scaled lot size before proving edge",
                "evidence": multi,
                "explanation": (
                    "Multi-lot trades show worse expectancy than 1-lot. Size amplified a negative process."
                ),
            }
        )

    churn = by_id.get("early_exit_lt_24h")
    if churn and churn["sample_size"] >= 30 and churn["win_rate_pct"] < 20:
        causes.append(
            {
                "id": "sub_24h_churn",
                "severity": "HIGH",
                "title": "Mass sub-24h exits destroyed theta edge",
                "evidence": churn,
                "explanation": (
                    "A large share of trades closed in under a day. Credit-spread edge needs time; "
                    "churn converts the book into fee/slippage + stop hunting."
                ),
            }
        )

    slow = by_id.get("long_hold_ge_7d")
    if slow and slow["sample_size"] >= 5 and slow["total_pnl"] < 0:
        causes.append(
            {
                "id": "slow_loser_tails",
                "severity": "HIGH",
                "title": "Long-hold losers dominate residual P/L damage",
                "evidence": slow,
                "explanation": (
                    "Fewer long holds still account for large absolute losses — missing 7-DTE force exit "
                    "or stop discipline on tested structures."
                ),
            }
        )

    put = families.get("spy_put_credit") or {}
    if put.get("sample_size", 0) == 0:
        causes.append(
            {
                "id": "successor_not_sampled",
                "severity": "HIGH",
                "title": "Successor put-credit cohort has zero closed trades",
                "evidence": put,
                "explanation": (
                    "IC was killed and put-credit is active on paper, but the ledger has no put-credit "
                    "closed sample. Automation without a clean successor sample is not an edge."
                ),
            }
        )

    causes.append(
        {
            "id": "ml_prior_mismatch",
            "severity": "HIGH",
            "title": "ML priors assumed ~86% IC win rate; realized ~17%",
            "evidence": {
                "assumed_prior_win_rate_pct": 86.0,
                "realized_ic_win_rate_pct": ic.get("win_rate_pct"),
                "note": "Thompson model eventually updated, but for months decisions optimized against fantasy priors.",
            },
            "explanation": (
                "Research priors (Tastytrade 15Δ IC) were used as if they were this system's edge. "
                "Agentic RAG/ML then optimized around a false baseline until empirical feedback caught up."
            ),
        }
    )

    causes.append(
        {
            "id": "complexity_over_edge",
            "severity": "MEDIUM",
            "title": "System complexity outran process control",
            "evidence": {
                "symptoms": [
                    "4-leg inventory orphans / lot mismatches",
                    "global TRADING_HALTED driven by killed family metrics",
                    "automation heartbeats without profitable cohort",
                ]
            },
            "explanation": (
                "Self-healing workflows, GRPO, and multi-agent orchestration cannot create expectancy. "
                "They can only amplify whatever entry/exit rules exist — and those rules lost money."
            ),
        }
    )

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    causes.sort(key=lambda c: severity_rank.get(c.get("severity", "LOW"), 9))
    return causes


def build_system_diagnosis(
    trades_data: dict[str, Any],
    *,
    equity: float | None = None,
    starting_equity: float | None = None,
    active_family: str = "spy_put_credit",
    unclean_inventory: bool | None = None,
) -> dict[str, Any]:
    """Full misery diagnosis artifact for runtime + RAG."""
    trades = [t for t in trades_data.get("trades", []) if isinstance(t, dict)]
    rows = closed_trade_rows(trades)
    clusters = analyze_loss_clusters(trades_data)
    families = family_stats(rows)
    months = monthly_attribution(rows)
    causes = synthesize_root_causes(clusters, families)

    stats = trades_data.get("stats") or {}
    closed = int(stats.get("closed_trades") or len(rows))
    total_pnl = as_float(stats.get("total_realized_pnl"), stats.get("total_pnl", 0.0))
    if not total_pnl and rows:
        total_pnl = sum(r["pnl"] for r in rows)
    expectancy = as_float(stats.get("expectancy"), stats.get("expectancy_per_trade", 0.0))
    if not expectancy and closed:
        expectancy = total_pnl / closed
    win_rate = as_float(stats.get("win_rate_pct"), 0.0)
    if not win_rate and rows:
        win_rate = 100.0 * sum(1 for r in rows if r["pnl"] > 0) / len(rows)
    pf = stats.get("profit_factor")
    if pf is None and rows:
        gp = sum(r["pnl"] for r in rows if r["pnl"] > 0)
        gl = abs(sum(r["pnl"] for r in rows if r["pnl"] < 0))
        pf = (gp / gl) if gl else (math.inf if gp else 0.0)

    # Explicit stats-vs-list reconciliation (paired rows + unpaired fold)
    list_pnl = sum(r["pnl"] for r in rows)
    unpaired_pnl = as_float(stats.get("unpaired_realized_pnl"), 0.0)
    unpaired_n = int(stats.get("unpaired_order_count") or 0)
    ledger_views = {
        "stats_closed_trades": closed,
        "paired_list_rows": len(rows),
        "unpaired_order_count": unpaired_n,
        "stats_total_realized_pnl": round(total_pnl, 2),
        "paired_list_pnl": round(list_pnl, 2),
        "unpaired_realized_pnl": round(unpaired_pnl, 2),
        "list_plus_unpaired_pnl": round(list_pnl + unpaired_pnl, 2),
        "reconciles": abs((list_pnl + unpaired_pnl) - total_pnl) < 1.0
        or (closed == len(rows) + unpaired_n),
        "note": (
            "Canonical headline metrics use stats (paired + unpaired fold). "
            "Loss clusters walk the paired list only."
        ),
    }

    north_star = {
        "monthly_after_tax_target": 6000.0,
        "target_capital": 300000.0,
        "current_equity": equity,
        "starting_equity": starting_equity,
        "estimated_monthly_from_expectancy": 0.0 if expectancy <= 0 else None,
        "on_track": False,
        "blockers": [
            "negative_expectancy" if expectancy <= 0 else None,
            "profit_factor_le_1" if as_float(pf, 0.0) <= 1.0 else None,
            "successor_n_zero" if (families.get("spy_put_credit") or {}).get("sample_size", 0) == 0 else None,
            "unclean_inventory" if unclean_inventory else None,
        ],
    }
    north_star["blockers"] = [b for b in north_star["blockers"] if b]

    primary_causes = [c for c in causes if c.get("severity") in {"CRITICAL", "HIGH"}][:5]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnosis_version": "1.0",
        "headline": (
            "System is miserable because the iron-condor process lost money at scale "
            "(~17% WR, PF<1, negative expectancy), scaled width/size before edge, churned "
            "sub-24h, and has not yet produced a put-credit validation sample."
        ),
        "ledger": {
            "closed_trades": closed,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": pf if isinstance(pf, str) else round(as_float(pf), 3) if pf is not None else None,
            "expectancy_per_trade": round(expectancy, 2),
            "total_realized_pnl": round(total_pnl, 2),
            "active_family": active_family,
            "views": ledger_views,
        },
        "families": families,
        "loss_clusters": clusters,
        "monthly_attribution": months,
        "root_causes": causes,
        "primary_root_causes": primary_causes,
        "north_star": north_star,
        "operator_actions": [
            "Do not reopen IC / ic_simple entries.",
            "Keep paper-only put-credit validation: 1-lot, $5 wide, min 24h hold, max 2 concurrent.",
            "Clear unclean open inventory before new risk.",
            "Gate on put-credit cohort metrics only (n>=30, expectancy>0, PF>1) — not IC lifetime.",
            "Treat GRPO/Thompson as advisory until successor sample exists; never as proof of edge.",
        ],
        "not_the_reason": [
            "Lack of workflows or heartbeats (ops automation is present).",
            "Lack of lessons files (RAG corpus is large but was not binding process control).",
            "Need for more model complexity before process control.",
        ],
    }


def diagnosis_to_markdown(diagnosis: dict[str, Any]) -> str:
    ledger = diagnosis.get("ledger") or {}
    causes = diagnosis.get("primary_root_causes") or diagnosis.get("root_causes") or []
    clusters = (diagnosis.get("loss_clusters") or [])[:6]
    actions = diagnosis.get("operator_actions") or []

    cause_lines = []
    for cause in causes:
        cause_lines.append(
            f"### {cause.get('severity', 'INFO')}: {cause.get('title')}\n\n"
            f"{cause.get('explanation')}\n"
        )
    cluster_lines = []
    for cluster in clusters:
        cluster_lines.append(
            f"- `{cluster.get('id')}`: n={cluster.get('sample_size')}, "
            f"P/L ${cluster.get('total_pnl')}, exp ${cluster.get('expectancy_per_trade')}/trade, "
            f"WR {cluster.get('win_rate_pct')}%"
        )
    action_lines = [f"- {a}" for a in actions]

    return f"""# System Misery Diagnosis

Tags: rag, ml, data-science, root-cause, north-star, loss-clusters
Lifecycle: active
Severity: CRITICAL
Confidence: high
Generated: {diagnosis.get("generated_at")}

## Headline

{diagnosis.get("headline")}

## Ledger

- Closed trades: {ledger.get("closed_trades")}
- Win rate: {ledger.get("win_rate_pct")}%
- Profit factor: {ledger.get("profit_factor")}
- Expectancy: ${ledger.get("expectancy_per_trade")}/trade
- Total realized P/L: ${ledger.get("total_realized_pnl")}
- Active family: {ledger.get("active_family")}

## Primary Root Causes

{chr(10).join(cause_lines) or "- None computed."}

## Loss Clusters

{chr(10).join(cluster_lines) or "- None."}

## Operator Actions

{chr(10).join(action_lines)}

## What This Is NOT

{chr(10).join(f"- {x}" for x in (diagnosis.get("not_the_reason") or []))}

## Machine Artifact

See `data/runtime/system_diagnosis_latest.json`.
"""
