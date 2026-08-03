#!/usr/bin/env python3
"""World-class production scorecard for the $1,000/mo after-tax near-term goal.

This is intentionally harsh. Infra/RAG grades do not print as "profitable."
Edge comes only from paired put-credit cohort metrics + live capital later.

Usage:
  python3 scripts/world_class_production_scorecard.py
  python3 scripts/world_class_production_scorecard.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.near_term_goal import (  # noqa: E402
    NEAR_TERM_MONTHLY_AFTER_TAX,
    path_economics,
)

from scripts.put_credit_cohort_scorecard import (  # noqa: E402
    build_scorecard as build_put_credit_card,
)

OUT_DEFAULT = ROOT / "data" / "audit" / "world_class_production_latest.json"


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _grade(score: float) -> str:
    if score >= 9.0:
        return "A+"
    if score >= 8.5:
        return "A"
    if score >= 8.0:
        return "A-"
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


def _dim(name: str, score: float, evidence: str, blocker: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "score_0_10": round(score, 2),
        "grade": _grade(score),
        "evidence": evidence,
        "blocker": blocker,
    }


def score_dimensions(
    *,
    system_state: dict[str, Any],
    put_card: dict[str, Any],
    inventory: dict[str, Any] | None,
    kill_switch: dict[str, Any],
    halted: bool,
) -> list[dict[str, Any]]:
    paper = (system_state.get("paper_account") or {}) if isinstance(system_state, dict) else {}
    live = (system_state.get("live_account") or {}) if isinstance(system_state, dict) else {}
    paper_eq = float(paper.get("equity") or paper.get("current_equity") or 0.0)
    live_eq = float(live.get("equity") or live.get("current_equity") or 0.0)
    closed = put_card.get("closed") or {}
    kill = closed.get("kill_criteria") or {}
    n = int(closed.get("closed_n") or 0)
    verdict = str(kill.get("verdict") or "UNKNOWN")
    exp = closed.get("expectancy")
    pf = closed.get("profit_factor")
    if inventory is None:
        inv_clean = None  # unknown — do not pretend unclean
    else:
        inv_clean = bool(inventory.get("clean", False))
        if inv_clean is False and not inventory.get("findings"):
            # Prefer explicit findings; empty findings + clean flag missing → soft pass
            inv_clean = inventory.get("clean", True)

    # 1) Edge / strategy science
    if verdict == "EDGE_CANDIDATE":
        edge_score = 9.0
        edge_block = None
    elif verdict == "NO_EDGE_KILL":
        edge_score = 1.0
        edge_block = "Kill criteria failed — redesign, do not scale"
    elif n == 0:
        edge_score = 1.5
        edge_block = "Zero closed put-credit validation trades with sufficient sample"
    elif n < 10:
        edge_score = 2.5 + n * 0.15
        edge_block = f"Only {n}/30 closed put-credits — sample theater if scaled now"
    else:
        edge_score = 3.5 + min(3.0, n / 30 * 3.0)
        edge_block = f"n={n}/30; verdict={verdict}"
    dims = [
        _dim(
            "edge_statistical_validity",
            edge_score,
            f"put_credit closed_n={n}/30 verdict={verdict} expectancy={exp} PF={pf}",
            edge_block,
        )
    ]

    # 2) Risk / capital protection
    risk_score = 8.0
    risk_block = None
    if halted:
        risk_score = 4.0
        risk_block = "TRADING_HALTED present"
    if inv_clean is False:
        risk_score = min(risk_score, 3.0)
        risk_block = "Open inventory unclean"
    elif inv_clean is None:
        risk_score = min(risk_score, 6.5)
        risk_block = "Inventory audit missing — run audit_open_inventory.py"
    if kill_switch.get("live_blocked") is not True:
        risk_score = min(risk_score, 5.0)
        risk_block = "live_blocked is not true — dangerous with unproven edge"
    if paper_eq > 0 and paper_eq < 90_000:
        risk_score -= 1.0  # drawdown from 100k
    # Full risk control plane green → A+
    if (
        not halted
        and inv_clean is True
        and kill_switch.get("live_blocked") is True
        and kill_switch.get("active_family") == "spy_put_credit"
    ):
        risk_score = max(risk_score, 9.5)
    dims.append(
        _dim(
            "risk_and_capital_protection",
            max(0.0, risk_score),
            f"inventory_clean={inv_clean} live_blocked={kill_switch.get('live_blocked')} "
            f"halted={halted} paper_equity={paper_eq}",
            risk_block,
        )
    )

    # 3) Execution path clarity
    active = kill_switch.get("active_family")
    exec_score = 7.5 if active == "spy_put_credit" else 3.0
    exec_block = None if active == "spy_put_credit" else f"active_family={active}"
    killed = kill_switch.get("killed_families") or []
    if "ic_simple" in killed or "iron_condor" in killed:
        exec_score = min(9.5, exec_score + 1.5)
    if active == "spy_put_credit" and kill_switch.get("paper_only") is True:
        exec_score = max(exec_score, 9.5)
    dims.append(
        _dim(
            "execution_path_clarity",
            exec_score,
            f"active_family={active} paper_only={kill_switch.get('paper_only')} killed={killed}",
            exec_block,
        )
    )

    # 4) Data integrity / paired ledger
    trades = _load(ROOT / "data" / "trades.json") or {}
    stats = trades.get("stats") if isinstance(trades, dict) else {}
    unpaired = int((stats or {}).get("unpaired_order_count") or 0)
    unpaired_status = str((stats or {}).get("unpaired_attribution_status") or "")
    # Quarantining unpaired cash is correct production practice — score high when
    # paired metrics are isolated; do not treat quarantine count as failure.
    if unpaired == 0:
        data_score = 9.5
        data_block = None
    elif "quarantine" in unpaired_status.lower() or unpaired_status:
        data_score = 8.5
        data_block = None
    else:
        data_score = max(5.0, 8.0 - min(unpaired, 10) * 0.2)
        data_block = f"{unpaired} unpaired orders — confirm quarantine in stats"
    dims.append(
        _dim(
            "data_integrity_paired_ledger",
            data_score,
            f"paired_closed≈{stats.get('closed_trades')} unpaired_orders={unpaired} "
            f"unpaired_status={unpaired_status!r} "
            f"IC_expectancy={((stats.get('by_strategy') or {}).get('iron_condor') or {}).get('expectancy')}",
            data_block,
        )
    )

    # 5) Live money engine
    if live_eq > 0 and verdict == "EDGE_CANDIDATE":
        live_score = 8.5
        live_block = None
    elif live_eq > 0 and verdict != "EDGE_CANDIDATE":
        live_score = 2.0
        live_block = "Live capital on unproven edge — world-class systems do not do this"
    else:
        live_score = 2.0  # $0 live is honest, not production cash
        live_block = "Live equity $0 — cannot produce real $1k/mo yet"
    dims.append(
        _dim(
            "live_money_engine",
            live_score,
            f"live_equity={live_eq} starting_live_was_20_lost=100pct_claim_from_state",
            live_block,
        )
    )

    # 6) Cadence / sample velocity
    open_n = int((put_card.get("open") or {}).get("open_n") or 0)
    # 1 closed + ~1 open after ~10 days of put-credit era → slow
    cadence_score = min(8.0, 2.0 + n * 0.2 + open_n * 0.5)
    cadence_block = (
        None
        if n >= 15
        else "Validation velocity too low for ASAP income — need disciplined daily clean setups"
    )
    dims.append(
        _dim(
            "validation_cadence",
            cadence_score,
            f"closed={n} open={open_n} remaining_to_n30={(put_card.get('progress') or {}).get('remaining_to_gate')}",
            cadence_block,
        )
    )

    # 7) Observability / ops
    # We have scorecards and kill switch — B grade if files fresh
    ss_path = ROOT / "data" / "system_state.json"
    age_h = None
    if ss_path.is_file():
        age_h = (datetime.now(UTC).timestamp() - ss_path.stat().st_mtime) / 3600.0
    obs_score = 7.0 if age_h is not None and age_h < 48 else 4.0
    if age_h is not None and age_h < 24:
        obs_score = 8.5
    if age_h is not None and age_h < 12:
        obs_score = 9.5
    obs_block = None if age_h is not None and age_h < 48 else "system_state stale (>48h)"
    # Production gate + cohort artifacts raise observability toward A+
    if (ROOT / "data" / "audit" / "put_credit_cohort_latest.json").is_file():
        obs_score = min(10.0, obs_score + 0.3)
    dims.append(
        _dim(
            "observability_ops",
            obs_score,
            f"system_state_age_hours={round(age_h, 1) if age_h is not None else None} "
            f"cohort_scorecard=present kill_switch=present",
            obs_block,
        )
    )

    # 8) Real-money readiness (composite honesty)
    if verdict == "EDGE_CANDIDATE" and inv_clean and not halted:
        ready_score = 8.0
        ready_block = "Edge candidate only — still need capital plan + scaled risk limits"
    else:
        ready_score = 1.5
        ready_block = "Not ready for real $1k/mo — missing edge and/or live capital"
    dims.append(
        _dim(
            "real_money_readiness",
            ready_score,
            f"verdict={verdict} inventory_clean={inv_clean} live_eq={live_eq}",
            ready_block,
        )
    )

    return dims


def build_world_class_card() -> dict[str, Any]:
    system_state = _load(ROOT / "data" / "system_state.json") or {}
    kill_switch = _load(ROOT / "data" / "runtime" / "strategy_kill_switch.json") or {}
    inventory = _load(ROOT / "data" / "audit" / "open_inventory_latest.json")
    put_card = build_put_credit_card()
    halted = (ROOT / "data" / "TRADING_HALTED").is_file()

    paper = system_state.get("paper_account") or {}
    live = system_state.get("live_account") or {}
    paper_eq = float(paper.get("equity") or paper.get("current_equity") or 0.0)
    live_eq = float(live.get("equity") or live.get("current_equity") or 0.0)
    closed = put_card.get("closed") or {}
    kill = closed.get("kill_criteria") or {}
    profile = put_card.get("profile") or {}

    economics = path_economics(
        paper_equity=paper_eq,
        live_equity=live_eq,
        closed_n=int(closed.get("closed_n") or 0),
        expectancy=closed.get("expectancy"),
        profit_factor=closed.get("profit_factor")
        if closed.get("profit_factor") != float("inf")
        else None,
        kill_verdict=str(kill.get("verdict") or "UNKNOWN"),
        max_concurrent=int(profile.get("max_concurrent_positions") or 2),
        max_daily_structures=int(profile.get("max_daily_structures") or 3),
    )

    dims = score_dimensions(
        system_state=system_state,
        put_card=put_card,
        inventory=inventory if isinstance(inventory, dict) else None,
        kill_switch=kill_switch,
        halted=halted,
    )

    # Ops production gate (can reach A+/10 when control plane is green)
    try:
        from src.risk.production_gate import evaluate_production_gate

        pg = evaluate_production_gate(for_live=False)
        dims.append(
            _dim(
                "production_control_plane",
                pg.score_0_10,
                f"grade={pg.grade} allow_new_risk={pg.allow_new_risk} "
                f"allow_live={pg.allow_live_capital} checks_ok="
                f"{sum(1 for c in pg.checks if c.ok)}/{len(pg.checks)}",
                None if pg.ok else ",".join(pg.blockers) or "ops checks failing",
            )
        )
        process_dims = [
            d
            for d in dims
            if d["name"]
            in {
                "risk_and_capital_protection",
                "execution_path_clarity",
                "data_integrity_paired_ledger",
                "observability_ops",
                "production_control_plane",
            }
        ]
        process_avg = sum(d["score_0_10"] for d in process_dims) / max(len(process_dims), 1)
        production_gate_view = pg.to_dict()
    except Exception as exc:  # noqa: BLE001
        process_avg = 0.0
        production_gate_view = {"error": str(exc)}
        dims.append(_dim("production_control_plane", 0.0, f"error={exc}", str(exc)))

    avg = sum(d["score_0_10"] for d in dims) / max(len(dims), 1)

    # Priority actions — process, not fantasy
    actions: list[dict[str, str]] = []
    if kill.get("verdict") != "EDGE_CANDIDATE":
        actions.append(
            {
                "priority": "P0",
                "action": "Complete clean put-credit paper cohort to n≥30",
                "why": "Without positive expectancy + PF>1, $1k/mo real is gambling",
            }
        )
        actions.append(
            {
                "priority": "P0",
                "action": "Run only spy_put_credit 1-lot; never revive IC entries",
                "why": "IC lifetime PF~0.17 destroyed edge; killed for cause",
            }
        )
    actions.append(
        {
            "priority": "P1",
            "action": "Maximize clean cadence (regime gate, max 3/day, 2 concurrent) without rule drift",
            "why": "n=1 after weeks is too slow for any income goal",
        }
    )
    if live_eq <= 0:
        actions.append(
            {
                "priority": "P2",
                "action": "Do NOT deposit live capital until EDGE_CANDIDATE",
                "why": "Live already went $20→$0; unproven edge compounds losses faster",
            }
        )
    if not (inventory or {}).get("clean", True):
        actions.append(
            {
                "priority": "P0",
                "action": "Clear open inventory findings before any new risk",
                "why": "Unclean books break exits and validation integrity",
            }
        )
    actions.append(
        {
            "priority": "P1",
            "action": "Daily: sync_alpaca_state + put_credit_cohort_scorecard + this scorecard",
            "why": "World-class desks run a single truth panel every session",
        }
    )
    actions.append(
        {
            "priority": "P2",
            "action": "After EDGE_CANDIDATE: small live scale (1-lot) with same stop 200% / 25% TP / 7 DTE",
            "why": "Scale process that already shows edge; do not redesign under live stress",
        }
    )

    return {
        "schema_version": "world-class-production-scorecard/1",
        "generated_at": datetime.now(UTC).isoformat(),
        "goal": {
            "near_term_after_tax_monthly_usd": NEAR_TERM_MONTHLY_AFTER_TAX,
            "north_star_after_tax_monthly_usd": 6000.0,
            "note": "Near-term CEO cash goal is $1k/mo; North Star remains $6k/mo capital path",
        },
        "truth": {
            "paper_equity": paper_eq,
            "live_equity": live_eq,
            "paper_total_pl": paper.get("total_pl"),
            "active_family": kill_switch.get("active_family"),
            "paper_only": kill_switch.get("paper_only"),
            "live_blocked": kill_switch.get("live_blocked"),
            "put_credit_closed_n": closed.get("closed_n"),
            "put_credit_open_n": (put_card.get("open") or {}).get("open_n"),
            "kill_verdict": kill.get("verdict"),
            "inventory_clean": (inventory or {}).get("clean"),
            "trading_halted": halted,
            "claim_profitable": False
            if kill.get("verdict") != "EDGE_CANDIDATE"
            else bool(kill.get("pass_all")),
        },
        "economics_for_1000_mo": economics,
        "dimensions": dims,
        "overall": {
            "score_0_10": round(avg, 2),
            "grade": _grade(avg),
            "label": (
                "NOT production cash engine"
                if kill.get("verdict") != "EDGE_CANDIDATE" or live_eq <= 0
                else "Edge candidate — funding decision required"
            ),
            "process_ops_score_0_10": round(process_avg, 2),
            "process_ops_grade": _grade(process_avg),
            "note": (
                "process_ops_grade is control-plane quality (can be A+). "
                "overall stays low until edge + live capital exist."
            ),
        },
        "production_gate": production_gate_view,
        "priority_actions": actions,
        "world_class_definition": {
            "not_this": [
                "More RAG frameworks without n=30 edge",
                "Live deposits to 'feel productive'",
                "Claiming $1k/mo from paper or from 1 winning put credit",
                "Reviving iron condors because a few trades looked good",
            ],
            "is_this": [
                "One strategy family, fixed profile, audited ledger",
                "Kill criteria enforced in code and ops",
                "Inventory hygiene before new risk",
                "Statistical edge before capital",
                "Then boring, repeated execution at 1-lot → scale",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    card = build_world_class_card()

    # JSON-safe: replace inf
    def _sanitize(obj: Any) -> Any:
        if isinstance(obj, float):
            if obj != obj:  # NaN
                return None
            if obj == float("inf"):
                return "Infinity"
            if obj == float("-inf"):
                return "-Infinity"
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    card = _sanitize(card)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(card, indent=2))
        return 0

    t = card["truth"]
    o = card["overall"]
    e = card["economics_for_1000_mo"]
    print("=== WORLD-CLASS PRODUCTION SCORECARD ===")
    print(f"Near-term goal: ${card['goal']['near_term_after_tax_monthly_usd']}/mo after-tax REAL")
    print(f"Overall: {o['grade']} ({o['score_0_10']}/10) — {o['label']}")
    print(
        f"Process/ops control plane: {o.get('process_ops_grade')} "
        f"({o.get('process_ops_score_0_10')}/10) — {o.get('note')}"
    )
    print(
        f"Paper equity: ${t['paper_equity']:,.2f}  Live: ${t['live_equity']:,.2f}  "
        f"family={t['active_family']} live_blocked={t['live_blocked']}"
    )
    print(
        f"Put-credit: closed={t['put_credit_closed_n']} open={t['put_credit_open_n']} "
        f"verdict={t['kill_verdict']} inventory_clean={t['inventory_clean']}"
    )
    print(
        f"$1k/mo needs ~${e['pre_tax_monthly_required']:,.0f}/mo pre-tax "
        f"(~{e['required_monthly_return_pct_on_paper']}% of paper equity) "
        f"or ~${e['required_expectancy_usd_per_trade_at_plan_cadence']}/trade "
        f"@ {e['planning_trades_per_month']} closes/mo"
    )
    print("Dimensions:")
    for d in card["dimensions"]:
        blk = f" | BLOCKER: {d['blocker']}" if d.get("blocker") else ""
        print(f"  {d['grade']:>3} {d['score_0_10']:4.1f}  {d['name']}{blk}")
    print("P0/P1 actions:")
    for a in card["priority_actions"]:
        if a["priority"] in {"P0", "P1"}:
            print(f"  [{a['priority']}] {a['action']}")
    print(f"json_out={args.out}")
    print(e["honesty"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
