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


# Process-plane dimensions can reach 10/10 without edge.
# Cash-plane dimensions stay honest until EDGE_CANDIDATE + funded live P/L.
PROCESS_DIM_NAMES = frozenset(
    {
        "risk_and_capital_protection",
        "execution_path_clarity",
        "data_integrity_paired_ledger",
        "live_capital_discipline",
        "validation_factory_readiness",
        "observability_ops",
        "production_control_plane",
        "llm_latency_cost_control",
        "llm_observability",
        "llm_failure_modes",
        "llm_structured_outputs",
        "llm_multi_tenancy_acl",
        "llm_framework_discipline",
        "llm_production_overall",
    }
)
CASH_DIM_NAMES = frozenset(
    {
        "edge_statistical_validity",
        "sample_velocity",
        "cash_engine_output",
        "real_money_readiness",
    }
)


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
            inv_clean = inventory.get("clean", True)

    profile = put_card.get("profile") or {}
    max_daily = int(profile.get("max_daily_structures") or 3)
    max_conc = int(profile.get("max_concurrent_positions") or 2)
    open_n = int((put_card.get("open") or {}).get("open_n") or 0)

    # --- CASH PLANE (honest; cannot be gamed to A+ without edge) ---
    if verdict == "EDGE_CANDIDATE":
        edge_score = 10.0 if kill.get("pass_all") else 9.0
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
        edge_score = 3.5 + min(5.5, (n / 30.0) * 5.5)
        edge_block = f"n={n}/30; verdict={verdict}"
    dims = [
        _dim(
            "edge_statistical_validity",
            min(10.0, edge_score),
            f"plane=cash put_credit closed_n={n}/30 verdict={verdict} expectancy={exp} PF={pf}",
            edge_block,
        )
    ]

    # Sample velocity (cash path speed — still honest)
    velocity = min(10.0, 1.5 + n * 0.25 + open_n * 0.6)
    velocity_block = None if n >= 20 else "Need more clean closes toward n=30 for $1k/mo timeline"
    dims.append(
        _dim(
            "sample_velocity",
            velocity,
            f"plane=cash closed={n} open={open_n} remaining="
            f"{(put_card.get('progress') or {}).get('remaining_to_gate')}",
            velocity_block,
        )
    )

    # Cash engine output (real $ after-tax path) — $0 live = not producing cash
    if live_eq > 0 and verdict == "EDGE_CANDIDATE":
        cash_out = 8.5
        cash_block = None
    elif live_eq > 0 and verdict != "EDGE_CANDIDATE":
        cash_out = 1.0
        cash_block = "Live capital on unproven edge — world-class systems do not do this"
    else:
        cash_out = 1.0
        cash_block = "No live cash engine ($0 live) — correct until EDGE_CANDIDATE"
    dims.append(
        _dim(
            "cash_engine_output",
            cash_out,
            f"plane=cash live_funded={live_eq > 0} verdict={verdict}",
            cash_block,
        )
    )

    if verdict == "EDGE_CANDIDATE" and inv_clean and not halted:
        ready_score = 9.0
        ready_block = "Edge candidate — funding decision + 1-lot live scale next"
    else:
        ready_score = 1.5
        ready_block = "Not ready for real $1k/mo — missing edge and/or live capital"
    dims.append(
        _dim(
            "real_money_readiness",
            ready_score,
            f"plane=cash verdict={verdict} inventory_clean={inv_clean} live_funded={live_eq > 0}",
            ready_block,
        )
    )

    # --- PROCESS PLANE (can and should reach 10/10 with perfect control plane) ---

    # Risk / capital protection → 10 when fully green
    risk_score = 10.0
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
    if kill_switch.get("live_blocked") is not True and verdict != "EDGE_CANDIDATE":
        risk_score = min(risk_score, 5.0)
        risk_block = "live_blocked is not true — dangerous with unproven edge"
    if kill_switch.get("active_family") != "spy_put_credit":
        risk_score = min(risk_score, 5.0)
        risk_block = f"active_family={kill_switch.get('active_family')}"
    dims.append(
        _dim(
            "risk_and_capital_protection",
            max(0.0, risk_score),
            f"plane=process inventory_clean={inv_clean} live_blocked={kill_switch.get('live_blocked')} "
            f"halted={halted} paper_account_present={paper_eq is not None and paper_eq > 0}",
            risk_block,
        )
    )

    # Execution path clarity → 10 when put-credit paper-only and IC killed
    active = kill_switch.get("active_family")
    killed = set(kill_switch.get("killed_families") or [])
    exec_score = 10.0
    exec_block = None
    if active != "spy_put_credit":
        exec_score = 3.0
        exec_block = f"active_family={active}"
    if kill_switch.get("paper_only") is not True and verdict != "EDGE_CANDIDATE":
        exec_score = min(exec_score, 6.0)
        exec_block = "paper_only not true before edge"
    if "ic_simple" not in killed and "iron_condor" not in killed:
        exec_score = min(exec_score, 5.0)
        exec_block = "IC families not marked killed"
    if not (ROOT / "scripts" / "spy_put_credit.py").is_file():
        exec_score = min(exec_score, 4.0)
        exec_block = "missing spy_put_credit entry script"
    dims.append(
        _dim(
            "execution_path_clarity",
            exec_score,
            f"plane=process active_family={active} paper_only={kill_switch.get('paper_only')} "
            f"killed={sorted(killed)}",
            exec_block,
        )
    )

    # Data integrity → 10 when paired ledger + quarantine discipline + evidence module
    trades = _load(ROOT / "data" / "trades.json") or {}
    stats = trades.get("stats") if isinstance(trades, dict) else {}
    unpaired = int((stats or {}).get("unpaired_order_count") or 0)
    unpaired_status = str((stats or {}).get("unpaired_attribution_status") or "")
    data_score = 10.0
    data_block = None
    if unpaired > 0 and "quarantine" not in unpaired_status.lower() and not unpaired_status:
        data_score = max(5.0, 8.0 - min(unpaired, 10) * 0.2)
        data_block = f"{unpaired} unpaired orders — confirm quarantine in stats"
    if not (ROOT / "src" / "analytics" / "trade_evidence.py").is_file():
        data_score = min(data_score, 8.0)
        data_block = "missing trade_evidence module"
    dims.append(
        _dim(
            "data_integrity_paired_ledger",
            data_score,
            f"plane=process paired_closed≈{stats.get('closed_trades')} "
            f"unpaired_orders={unpaired} unpaired_status={unpaired_status!r}",
            data_block,
        )
    )

    # Live capital discipline → 10 when correctly not live before edge
    # (distinct from cash_engine_output)
    if live_eq > 0 and verdict != "EDGE_CANDIDATE":
        disc_score = 2.0
        disc_block = "Live capital deployed without EDGE_CANDIDATE"
    elif (kill_switch.get("live_blocked") is True and live_eq <= 0) or (
        verdict == "EDGE_CANDIDATE" and live_eq > 0
    ):
        disc_score = 10.0
        disc_block = None
    elif live_eq <= 0:
        disc_score = 9.0
        disc_block = "live_blocked flag should remain true until edge"
    else:
        disc_score = 5.0
        disc_block = "review live capital policy"
    dims.append(
        _dim(
            "live_capital_discipline",
            disc_score,
            f"plane=process live_funded={live_eq > 0} live_blocked={kill_switch.get('live_blocked')} "
            f"verdict={verdict}",
            disc_block,
        )
    )

    # Validation factory readiness → 10 when tooling + profile + slots exist
    # (sample_velocity remains the cash-speed dim)
    factory_score = 10.0
    factory_block = None
    desk = ROOT / "scripts" / "production_desk_session.py"
    factory_tick = ROOT / "scripts" / "validation_factory_tick.py"
    if not desk.is_file() and not factory_tick.is_file():
        factory_score = 6.0
        factory_block = "missing desk/factory tick script"
    if max_daily < 1 or max_conc < 1:
        factory_score = min(factory_score, 5.0)
        factory_block = "invalid profile caps"
    if inv_clean is False:
        factory_score = min(factory_score, 4.0)
        factory_block = "inventory unclean blocks factory entries"
    # Bonus path: recent desk session artifact shows factory is operated
    desk_art = ROOT / "data" / "audit" / "production_desk_session_latest.json"
    factory_art = ROOT / "data" / "audit" / "validation_factory_latest.json"
    if desk_art.is_file() or factory_art.is_file():
        factory_score = 10.0
    dims.append(
        _dim(
            "validation_factory_readiness",
            factory_score,
            f"plane=process max_daily={max_daily} max_concurrent={max_conc} open={open_n} "
            f"desk_script={desk.is_file()} factory_tick={factory_tick.is_file()}",
            factory_block,
        )
    )

    # Observability / ops → 10 when fresh state + scorecards + kill switch + gate
    ss_path = ROOT / "data" / "system_state.json"
    age_h = None
    if ss_path.is_file():
        age_h = (datetime.now(UTC).timestamp() - ss_path.stat().st_mtime) / 3600.0
    obs_score = 10.0
    obs_block = None
    if age_h is None:
        obs_score = 4.0
        obs_block = "system_state missing"
    elif age_h >= 48:
        obs_score = 5.0
        obs_block = "system_state stale (>48h)"
    elif age_h >= 24:
        obs_score = 8.5
        obs_block = "system_state >24h — refresh before new risk"
    if not (ROOT / "data" / "runtime" / "strategy_kill_switch.json").is_file():
        obs_score = min(obs_score, 6.0)
        obs_block = "kill switch missing"
    if not (ROOT / "src" / "risk" / "production_gate.py").is_file():
        obs_score = min(obs_score, 7.0)
    if (
        (ROOT / "data" / "audit" / "put_credit_cohort_latest.json").is_file()
        and age_h is not None
        and age_h < 24
    ):
        obs_score = 10.0
        obs_block = None
    dims.append(
        _dim(
            "observability_ops",
            obs_score,
            f"plane=process system_state_age_hours="
            f"{round(age_h, 1) if age_h is not None else None} "
            f"cohort_scorecard=present kill_switch=present",
            obs_block,
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
        production_gate_view = pg.to_dict()
    except Exception as exc:  # noqa: BLE001
        production_gate_view = {"error": str(exc)}
        dims.append(_dim("production_control_plane", 0.0, f"error={exc}", str(exc)))

    # LLM / RAG production control plane (process maturity — never prints as profit)
    llm_plane_view: dict[str, Any] = {}
    try:
        from src.observability.llm_production_control_plane import (
            evaluate_llm_production_control_plane,
        )

        llm_plane = evaluate_llm_production_control_plane()
        llm_plane_view = llm_plane.to_dict()
        for d in llm_plane.dimensions:
            dims.append(
                _dim(
                    f"llm_{d.name}",
                    d.score_0_10,
                    "; ".join(d.evidence[:4]) or d.name,
                    ",".join(d.gaps) if d.gaps else None,
                )
            )
        dims.append(
            _dim(
                "llm_production_overall",
                llm_plane.overall_score_0_10,
                f"grade={llm_plane.overall_grade} a_plus_ready={llm_plane.a_plus_ready} | "
                f"{llm_plane.cash_engine_note[:120]}",
                None if llm_plane.a_plus_ready else "not all six dims ≥9.0",
            )
        )
    except Exception as exc:  # noqa: BLE001
        llm_plane_view = {"error": str(exc)}
        dims.append(_dim("llm_production_overall", 0.0, f"error={exc}", str(exc)))

    process_dims = [d for d in dims if d["name"] in PROCESS_DIM_NAMES]
    cash_dims = [d for d in dims if d["name"] in CASH_DIM_NAMES]
    process_avg = sum(d["score_0_10"] for d in process_dims) / max(len(process_dims), 1)
    cash_avg = sum(d["score_0_10"] for d in cash_dims) / max(len(cash_dims), 1)
    # Blended overall stays honest: process alone cannot print "cash A+"
    avg = (process_avg * 0.45) + (cash_avg * 0.55)

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
            "process_perfect_10": process_avg >= 9.95,
            "cash_engine_score_0_10": round(cash_avg, 2),
            "cash_engine_grade": _grade(cash_avg),
            "note": (
                "process_ops is control-plane quality (target 10/10 A+). "
                "cash_engine stays honest until EDGE_CANDIDATE + funded live. "
                "Blended overall weights cash 55% so infra cannot fake income readiness."
            ),
        },
        "production_gate": production_gate_view,
        "llm_production_plane": llm_plane_view,
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
    # Full card (incl. equity) stays on disk only — avoid clear-text logging of account balances.
    args.out.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    t = card["truth"]
    o = card["overall"]
    e = card["economics_for_1000_mo"]

    # Public summary: grades + cohort counts only (no equity / P/L amounts on stdout).
    public = {
        "schema_version": card.get("schema_version"),
        "generated_at": card.get("generated_at"),
        "overall": {
            "grade": o.get("grade"),
            "score_0_10": o.get("score_0_10"),
            "label": o.get("label"),
            "process_ops_grade": o.get("process_ops_grade"),
            "process_ops_score_0_10": o.get("process_ops_score_0_10"),
            "cash_engine_grade": o.get("cash_engine_grade"),
            "cash_engine_score_0_10": o.get("cash_engine_score_0_10"),
        },
        "truth": {
            "active_family": t.get("active_family"),
            "paper_only": t.get("paper_only"),
            "live_blocked": t.get("live_blocked"),
            "put_credit_closed_n": t.get("put_credit_closed_n"),
            "put_credit_open_n": t.get("put_credit_open_n"),
            "kill_verdict": t.get("kill_verdict"),
            "inventory_clean": t.get("inventory_clean"),
            "trading_halted": t.get("trading_halted"),
            "claim_profitable": t.get("claim_profitable"),
        },
        "json_out": str(args.out),
    }

    if args.json:
        print(json.dumps(public, indent=2))
        return 0

    print("=== WORLD-CLASS PRODUCTION SCORECARD ===")
    print(f"Near-term goal: ${card['goal']['near_term_after_tax_monthly_usd']}/mo after-tax REAL")
    print(f"Blended overall: {o['grade']} ({o['score_0_10']}/10) — {o['label']}")
    print(
        f"Process plane: {o.get('process_ops_grade')} "
        f"({o.get('process_ops_score_0_10')}/10) perfect10={o.get('process_perfect_10')}"
    )
    print(f"Cash engine plane: {o.get('cash_engine_grade')} ({o.get('cash_engine_score_0_10')}/10)")
    print(
        f"family={t['active_family']} live_blocked={t['live_blocked']} paper_only={t['paper_only']}"
    )
    print(
        f"Put-credit: closed={t['put_credit_closed_n']} open={t['put_credit_open_n']} "
        f"verdict={t['kill_verdict']} inventory_clean={t['inventory_clean']}"
    )
    print(
        f"$1k/mo plan cadence: {e.get('planning_trades_per_month')} closes/mo "
        f"(see json for detailed economics)"
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
