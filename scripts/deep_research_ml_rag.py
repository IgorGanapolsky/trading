#!/usr/bin/env python3
"""Deep research, ML, and RAG decision packet for SPY iron condors.

This is an offline evidence generator. It does not place orders. It combines
ledger performance, validation status, ML drift, reconciliation health, current
research-state data, and relevant RAG lessons into one machine-readable gate.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from scripts import rag_pre_deployment_check as rag_check
from scripts import research_strategies
from scripts import update_ml_from_trades as ml_update

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = PROJECT_ROOT / "data" / "reports"
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"

RESEARCH_REFERENCES = [
    {
        "id": "cboe_cndr_methodology",
        "title": "Cboe S&P 500 Iron Condor Index methodology",
        "url": "https://cdn.cboe.com/api/global/us_indices/governance/CNDR_Methodology.pdf",
        "takeaway": (
            "Cboe's CNDR benchmark is a mechanical monthly SPX iron condor with "
            "roughly 20-delta short legs and 5-delta long wings; it is a benchmark, "
            "not proof that this repo's current rule set has positive expectancy."
        ),
    },
    {
        "id": "cboe_strategy_benchmarks",
        "title": "Cboe strategy benchmark indices",
        "url": "https://www.cboe.com/us/indices/benchmark_indices/",
        "takeaway": (
            "Cboe publishes option-writing benchmarks, which makes CNDR a useful "
            "baseline for comparing systematic option-selling performance."
        ),
    },
    {
        "id": "sepp_ml_volatility_trading",
        "title": "Machine Learning for Volatility Trading",
        "url": "https://memento.epfl.ch/public/upload/files/A.Sepp.pdf",
        "takeaway": (
            "Short-volatility P/L should be conditioned on volatility risk premium, "
            "realized volatility, and convexity loss, not only entry delta."
        ),
    },
    {
        "id": "ssrn_ic_conditions",
        "title": "Historical analysis of iron condors on SPX and VIX",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4643378",
        "takeaway": (
            "Historical SPX/VIX analysis reports that iron-condor outcomes vary "
            "materially by market and volatility conditions; regime filters should "
            "be tested before scaling."
        ),
    },
    {
        "id": "alpaca_iron_condor_api",
        "title": "Alpaca iron condor options API guide",
        "url": "https://alpaca.markets/learn/iron-condor",
        "takeaway": (
            "Alpaca supports API-driven options workflows; broker execution health "
            "and protection orders still need local verification before any entry."
        ),
    },
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def finite(value: float) -> float | str:
    return round(value, 4) if math.isfinite(value) else "inf"


def validation_snapshot(entries: dict[str, Any], trades_data: dict[str, Any]) -> dict[str, Any]:
    validation_entries = {
        key: entry
        for key, entry in entries.items()
        if isinstance(entry, dict)
        and (entry.get("validation_phase") or str(entry.get("date", "")) >= "2026-04-10")
    }
    closed_trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else []
    closed_validation = [
        trade
        for trade in closed_trades
        if isinstance(trade, dict)
        and (trade.get("validation_phase") or str(trade.get("entry_date", "")) >= "2026-04-10")
    ]

    pnls = [as_float(trade.get("realized_pnl"), 0.0) for trade in closed_validation]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    total_pnl = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0)
    expectancy = total_pnl / len(pnls) if pnls else 0.0

    violations: list[str] = []
    for idx, (key, entry) in enumerate(
        sorted(validation_entries.items(), key=lambda item: item[1].get("date", "")), start=1
    ):
        method = entry.get("selection_method", entry.get("strike_selection_method", "unknown"))
        profile = entry.get("profile_name", "unknown")
        qty = as_float(entry.get("quantity"), 1.0)
        if qty > 1:
            violations.append(f"Trade {idx}: qty={qty:g} > 1-lot maximum")
        if method != "live_delta":
            violations.append(f"Trade {idx}: method={method} (should be live_delta)")
        if profile != "spy-core":
            violations.append(f"Trade {idx}: profile={profile} (should be spy-core)")
        if key == "IC_260731" and "backfilled" in entry:
            violations.append("Trade 3: entry was backfilled after blind hold path")

    return {
        "entries": len(validation_entries),
        "closed_trades": len(closed_validation),
        "remaining_for_30_trade_gate": max(0, 30 - len(closed_validation)),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round((len(wins) / len(pnls) * 100) if pnls else 0.0, 2),
        "profit_factor": finite(profit_factor),
        "expectancy_per_trade": round(expectancy, 2),
        "total_pnl": round(total_pnl, 2),
        "protocol_violations": violations,
    }


def model_drift_snapshot(model: dict[str, Any], ledger_stats: dict[str, Any]) -> dict[str, Any]:
    iron_condor = model.get("iron_condor", {}) if isinstance(model, dict) else {}
    alpha = as_float(iron_condor.get("alpha"), 0.0)
    beta = as_float(iron_condor.get("beta"), 0.0)
    expected = (alpha / (alpha + beta) * 100) if (alpha + beta) > 0 else 0.0
    realized = as_float(ledger_stats.get("win_rate_pct"), 0.0)
    drift = abs(expected - realized)
    empirical_alpha = int(ledger_stats.get("wins") or 0) + 1
    empirical_beta = int(ledger_stats.get("losses") or 0) + 1
    return {
        "model_alpha": alpha,
        "model_beta": beta,
        "model_expected_win_rate_pct": round(expected, 2),
        "realized_win_rate_pct": round(realized, 2),
        "drift_pct": round(drift, 2),
        "drift_alert": drift > ml_update.DRIFT_ALERT_THRESHOLD,
        "empirical_alpha": empirical_alpha,
        "empirical_beta": empirical_beta,
    }


def latest_reconciliation_snapshot(report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    reports = sorted(report_dir.glob("reconciliation_*.json"))
    if not reports:
        return {"status": "missing", "alert_fired": True}
    latest = reports[-1]
    payload = load_json(latest, {})
    try:
        display_path = str(latest.relative_to(PROJECT_ROOT))
    except ValueError:
        display_path = str(latest)
    return {
        "status": "ok",
        "path": display_path,
        "date": payload.get("date"),
        "alert_fired": bool(payload.get("alert_fired")),
        "broker_realized_pnl": as_float(payload.get("broker_realized_pnl"), 0.0),
        "paired_realized_pnl": as_float(payload.get("paired_realized_pnl"), 0.0),
        "delta_dollars": as_float(payload.get("delta_dollars"), 0.0),
        "threshold_dollars": as_float(payload.get("threshold_dollars"), 0.0),
    }


def rag_snapshot(query: str, limit: int = 5) -> dict[str, Any]:
    lessons = rag_check.load_lessons()
    matches = rag_check.keyword_search(query, lessons)[:limit]
    return {
        "query": query,
        "lesson_count": len(lessons),
        "matches": [
            {
                "id": match.get("id", "unknown"),
                "severity": match.get("severity", "unknown"),
                "score": round(as_float(match.get("score"), 0.0), 4),
            }
            for match in matches
        ],
    }


def market_research_snapshot() -> dict[str, Any]:
    vix_data = research_strategies.fetch_url(research_strategies.SOURCES[0]["url"])
    vix = research_strategies.analyze_vix_regime(vix_data)
    return {
        "source": research_strategies.SOURCES[0]["url"],
        "vix": vix,
        "trade_implication": (
            "Regime data is advisory only. It cannot override negative expectancy, "
            "reconciliation breaches, stale ML priors, or validation protocol violations."
        ),
    }


def build_packet(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    trades_data = ml_update.load_trades()
    entries = load_json(PROJECT_ROOT / "data" / "ic_entries.json", {})
    model = load_json(PROJECT_ROOT / "models" / "ml" / "trade_confidence_model.json", {})
    research_state = load_json(PROJECT_ROOT / "data" / "research_state.json", {})

    ledger_stats = trades_data.get("stats", {}) if isinstance(trades_data, dict) else {}
    gate = ml_update.check_trading_gate(ledger_stats)
    validation = validation_snapshot(entries, trades_data)
    drift = model_drift_snapshot(model, ledger_stats)
    reconciliation = latest_reconciliation_snapshot()
    loss_clusters = ml_update.analyze_loss_clusters(trades_data)[:5]
    rag = rag_snapshot(
        "SPY iron condor negative expectancy stale priors reconciliation breach trade gate"
    )
    market_research = market_research_snapshot()

    blockers = []
    if not gate.get("should_trade"):
        blockers.append(gate.get("block_reason") or "ML profitability gate is blocked")
    if validation["expectancy_per_trade"] <= 0:
        blockers.append(
            f"Validation expectancy is ${validation['expectancy_per_trade']:.2f}/trade"
        )
    if validation["remaining_for_30_trade_gate"] > 0:
        blockers.append(
            f"Validation sample incomplete: {validation['closed_trades']}/30 closed trades"
        )
    if validation["protocol_violations"]:
        blockers.append("Validation protocol violations remain open")
    if reconciliation.get("alert_fired"):
        blockers.append(
            "Broker-vs-paired reconciliation breach remains open "
            f"(${reconciliation.get('delta_dollars', 0.0):.2f} delta)"
        )
    if drift["drift_alert"]:
        blockers.append(
            "ML priors are stale: "
            f"{drift['model_expected_win_rate_pct']:.2f}% expected vs "
            f"{drift['realized_win_rate_pct']:.2f}% realized"
        )

    next_hypotheses = [
        {
            "id": "regime_filtered_ic",
            "status": "research_only",
            "test": "Backtest and paper-validate IC entries only when VIX/IV regime shows positive volatility-risk-premium evidence.",
            "kill_criteria": "Stop if 30-trade cohort expectancy <= 0, profit factor <= 1.0, or reconciliation alert fires.",
        },
        {
            "id": "width_and_size_reduction",
            "status": "research_only",
            "test": "Compare 5-wide one-lot structures against historical 10-wide and multi-contract loss clusters.",
            "kill_criteria": "Reject if drawdown or expectancy is worse than current validation baseline.",
        },
        {
            "id": "agentic_rag_pre_entry",
            "status": "required_before_trade",
            "test": "Require a RAG retrieval packet with loss clusters, reconciliation status, and current research-state regime before every entry.",
            "kill_criteria": "No entry when RAG returns unresolved negative-expectancy or blind-hold lessons.",
        },
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": today.isoformat(),
        "decision": "BLOCKED" if blockers else "RESEARCH_READY",
        "profit_claim": "No profit claim. Current evidence blocks scaling.",
        "blockers": blockers,
        "ledger": {
            "closed_trades": int(ledger_stats.get("closed_trades") or 0),
            "wins": int(ledger_stats.get("wins") or 0),
            "losses": int(ledger_stats.get("losses") or 0),
            "win_rate_pct": as_float(ledger_stats.get("win_rate_pct"), 0.0),
            "profit_factor": as_float(ledger_stats.get("profit_factor"), 0.0),
            "expectancy_per_trade": as_float(
                ledger_stats.get("expectancy_per_trade"), ledger_stats.get("expectancy", 0.0)
            ),
            "total_realized_pnl": as_float(
                ledger_stats.get("total_realized_pnl"), ledger_stats.get("total_pnl", 0.0)
            ),
        },
        "ml_gate": gate,
        "validation": validation,
        "model_drift": drift,
        "reconciliation": reconciliation,
        "market_research": market_research,
        "research_state": research_state,
        "rag": rag,
        "loss_clusters": loss_clusters,
        "research_references": RESEARCH_REFERENCES,
        "next_hypotheses": next_hypotheses,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    blockers = "\n".join(f"- {item}" for item in packet["blockers"]) or "- None"
    ledger = packet["ledger"]
    validation = packet["validation"]
    drift = packet["model_drift"]
    reconciliation = packet["reconciliation"]
    market_research = packet.get("market_research", {})
    vix = market_research.get("vix", {}) if isinstance(market_research, dict) else {}
    clusters = "\n".join(
        (
            f"- `{cluster['id']}`: {cluster['sample_size']} trades, "
            f"P/L ${cluster['total_pnl']:.2f}, expectancy "
            f"${cluster['expectancy_per_trade']:.2f}/trade"
        )
        for cluster in packet["loss_clusters"]
    )
    rag_matches = "\n".join(
        f"- `{match['id']}` score `{match['score']}` severity `{match['severity']}`"
        for match in packet["rag"]["matches"]
    )
    hypotheses = "\n".join(
        f"- `{item['id']}` ({item['status']}): {item['test']}" for item in packet["next_hypotheses"]
    )
    refs = "\n".join(
        f"- [{ref['title']}]({ref['url']}): {ref['takeaway']}"
        for ref in packet["research_references"]
    )
    return f"""# Deep Research ML RAG Packet - {packet['date']}

## Decision

`{packet['decision']}` - {packet['profit_claim']}

## Blockers

{blockers}

## Ledger Evidence

- Closed trades: `{ledger['closed_trades']}`
- Wins / losses: `{ledger['wins']} / {ledger['losses']}`
- Win rate: `{ledger['win_rate_pct']:.2f}%`
- Profit factor: `{ledger['profit_factor']:.2f}`
- Expectancy: `${ledger['expectancy_per_trade']:.2f}/trade`
- Total realized P/L: `${ledger['total_realized_pnl']:.2f}`

## Validation Cohort

- Validation entries: `{validation['entries']}`
- Closed validation trades: `{validation['closed_trades']}/30`
- Validation expectancy: `${validation['expectancy_per_trade']:.2f}/trade`
- Validation profit factor: `{validation['profit_factor']}`
- Protocol violations: `{len(validation['protocol_violations'])}`

## ML Drift

- Model expected win rate: `{drift['model_expected_win_rate_pct']:.2f}%`
- Realized win rate: `{drift['realized_win_rate_pct']:.2f}%`
- Drift: `{drift['drift_pct']:.2f}%`
- Empirical Thompson priors should be: `alpha={drift['empirical_alpha']}`, `beta={drift['empirical_beta']}`

## Reconciliation

- Latest report: `{reconciliation.get('path', 'missing')}`
- Alert fired: `{reconciliation.get('alert_fired')}`
- Delta: `${reconciliation.get('delta_dollars', 0.0):.2f}`
- Threshold: `${reconciliation.get('threshold_dollars', 0.0):.2f}`

## Live Market Research

- VIX source: `{market_research.get('source', 'unknown')}`
- VIX: `{vix.get('vix', 'unknown')}`
- VIX regime: `{vix.get('regime', 'unknown')}`
- VIX trend: `{vix.get('vix_trend', 'unknown')}`
- Implication: {market_research.get('trade_implication', 'No implication available.')}

## Loss Clusters

{clusters or "- None detected"}

## Agentic RAG Retrieval

- Query: `{packet['rag']['query']}`
- Lessons loaded: `{packet['rag']['lesson_count']}`

{rag_matches or "- No matches"}

## Next Research Hypotheses

{hypotheses}

## External Research References

{refs}

Generated by `scripts/deep_research_ml_rag.py`.
"""


def write_outputs(packet: dict[str, Any], dry_run: bool = False) -> dict[str, str]:
    stamp = packet["date"].replace("-", "")
    report_json = REPORT_DIR / f"deep_research_ml_rag_{packet['date']}.json"
    report_md = REPORT_DIR / f"deep_research_ml_rag_{packet['date']}.md"
    lesson_md = LESSONS_DIR / f"deep_research_ml_rag_{stamp}.md"
    markdown = render_markdown(packet)
    if not dry_run:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(packet, indent=2) + "\n")
        report_md.write_text(markdown)
        lesson_md.write_text(markdown)
    return {
        "json": str(report_json.relative_to(PROJECT_ROOT)),
        "markdown": str(report_md.relative_to(PROJECT_ROOT)),
        "rag_lesson": str(lesson_md.relative_to(PROJECT_ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deep research ML/RAG packet")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    packet = build_packet(today=date.fromisoformat(args.date))
    outputs = write_outputs(packet, dry_run=args.dry_run)
    print(json.dumps({"decision": packet["decision"], "outputs": outputs}, indent=2))
    return 2 if packet["decision"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
