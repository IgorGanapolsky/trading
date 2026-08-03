#!/usr/bin/env python3
"""Fail-closed readiness contract for the $1,000/month after-tax objective.

This command proves engineering and evidence gates. It never submits an order,
changes a kill switch, transfers money, or promotes paper results to live proof.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics.statistical_edge import required_pretax_monthly, to_json_safe  # noqa: E402
from src.bank.live_gate import evaluate_live_bank_gate  # noqa: E402
from src.bank.remittance import (  # noqa: E402
    DEFAULT_SHORT_TERM_TAX_RATE,
    MONTHLY_AFTER_TAX_TARGET_USD,
    compute_remittance_progress,
)
from src.bank.transfer_ledger import load_transfer_ledger  # noqa: E402
from src.core.trading_constants import (  # noqa: E402
    MAX_CONCURRENT_IRON_CONDORS,
    MAX_CONTRACTS_PER_TRADE,
)
from src.rag.evaluation import RAGEvaluator  # noqa: E402
from src.rag.rag_pipeline import TradingRAGPipeline  # noqa: E402
from src.risk.open_inventory_audit import audit_from_files  # noqa: E402

from scripts.put_credit_cohort_scorecard import build_scorecard  # noqa: E402


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _state_freshness(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    updated = _parse_time(state.get("last_updated") or state.get("meta", {}).get("last_updated"))
    age_hours = (now - updated).total_seconds() / 3600.0 if updated else None
    return {
        "updated_at": updated.isoformat() if updated else None,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "fresh_within_24h": bool(age_hours is not None and 0.0 <= age_hours <= 24.0),
    }


def build_readiness(
    repo_root: Path = ROOT,
    *,
    include_rag_eval: bool = True,
) -> dict[str, Any]:
    """Build one current, evidence-linked readiness decision."""
    repo_root = repo_root.resolve()
    now = datetime.now(UTC)
    state = _load_json(repo_root / "data" / "system_state.json", {})
    kill = _load_json(repo_root / "data" / "runtime" / "strategy_kill_switch.json", {})
    cohort = build_scorecard(
        trades_path=repo_root / "data" / "trades.json",
        entries_path=repo_root / "data" / "put_credit_entries.json",
        kill_path=repo_root / "data" / "runtime" / "strategy_kill_switch.json",
    )

    with tempfile.TemporaryDirectory(prefix="world-class-trading-") as temporary:
        temp_root = Path(temporary)
        cohort_path = temp_root / "cohort.json"
        cohort_path.write_text(
            json.dumps(to_json_safe(cohort), allow_nan=False),
            encoding="utf-8",
        )
        live_gate = evaluate_live_bank_gate(cohort_path=cohort_path)

        pipeline = TradingRAGPipeline(
            db_path=temp_root / "rag.db",
            lessons_dir=repo_root / "rag_knowledge" / "lessons_learned",
        )
        ingestion = pipeline.sync_markdown_dir(
            repo_root / "rag_knowledge" / "lessons_learned",
            delete_missing=True,
            strict_quality=True,
        )
        warmup = pipeline.warmup()
        rag_health = pipeline.health()
        rag_eval: dict[str, Any] | None = None
        if include_rag_eval:
            report = RAGEvaluator(search_engine=pipeline).evaluate_all(
                k=5,
                include_unanswerable=True,
                unanswerable_threshold=0.04,
            )
            rag_eval = report.to_dict()
        pipeline.close()

    inventory = audit_from_files(
        repo_root,
        max_contracts_per_trade=float(MAX_CONTRACTS_PER_TRADE),
        max_concurrent_iron_condors=int(MAX_CONCURRENT_IRON_CONDORS),
    ).to_dict()
    state_freshness = _state_freshness(state if isinstance(state, dict) else {}, now)
    state_target = (
        state.get("north_star", {}).get("monthly_after_tax_target")
        if isinstance(state, dict) and isinstance(state.get("north_star"), dict)
        else None
    )
    target_consistent = bool(
        state_target is not None and abs(float(state_target) - MONTHLY_AFTER_TAX_TARGET_USD) < 1e-9
    )

    metrics = rag_eval.get("metrics", {}) if rag_eval else {}
    unanswerable = rag_eval.get("unanswerable", {}) if rag_eval else {}
    rag_eval_passed = bool(
        not include_rag_eval
        or (
            metrics.get("mean_precision_at_k", 0.0) >= 0.70
            and metrics.get("mean_recall_at_k", 0.0) >= 0.85
            and metrics.get("mrr", 0.0) >= 0.95
            and metrics.get("mean_ndcg_at_k", 0.0) >= 0.90
            and unanswerable.get("accuracy", 0.0) == 1.0
        )
    )
    rag_production_passed = bool(
        rag_health.get("ready")
        and not rag_health.get("degraded")
        and rag_health.get("quality_pass_rate") == 1.0
        and ingestion.ok
        and rag_eval_passed
    )

    closed = cohort["closed"]
    paper_validation_ready = bool(
        kill.get("active_family") == "spy_put_credit"
        and kill.get("paper_only") is True
        and kill.get("live_blocked") is True
        and inventory["clean"]
        and state_freshness["fresh_within_24h"]
    )

    remittance = compute_remittance_progress(
        load_transfer_ledger(),
        target_usd=MONTHLY_AFTER_TAX_TARGET_USD,
    )
    required_gross = required_pretax_monthly(
        MONTHLY_AFTER_TAX_TARGET_USD,
        DEFAULT_SHORT_TERM_TAX_RATE,
    )

    blockers: list[str] = []
    if not target_consistent:
        blockers.append(
            f"goal_contract_mismatch: state={state_target} canonical={MONTHLY_AFTER_TAX_TARGET_USD}"
        )
    if not state_freshness["fresh_within_24h"]:
        blockers.append(f"broker_snapshot_not_fresh: age_hours={state_freshness['age_hours']}")
    if not inventory["clean"]:
        blockers.extend(f"inventory: {reason}" for reason in inventory["block_reasons"])
    if not rag_production_passed:
        blockers.append(
            "rag_not_world_class: require semantic backend, 100% governed corpus, and eval gate"
        )
    blockers.extend(live_gate.blockers)

    return {
        "schema_version": "world-class-trading-readiness/1",
        "generated_at": now.isoformat(),
        "goal_contract": {
            "monthly_after_tax_target_usd": MONTHLY_AFTER_TAX_TARGET_USD,
            "tax_reserve_rate": DEFAULT_SHORT_TERM_TAX_RATE,
            "required_realized_pretax_monthly_usd": required_gross,
            "proof_surface": "confirmed broker-to-bank remittance ledger",
            "target_consistent_across_runtime_state": target_consistent,
        },
        "strategy_evidence": {
            "active_family": cohort["active_family"],
            "closed_n": closed["closed_n"],
            "expectancy": closed["expectancy"],
            "expectancy_lower_95": closed["expectancy_lower_95"],
            "profit_factor": closed["profit_factor"],
            "total_realized_pnl": closed["total_realized_pnl"],
            "interim_verdict": closed["kill_criteria"]["verdict"],
            "desk_grade_verdict": closed["desk_grade"]["verdict"],
        },
        "execution_evidence": {
            "inventory": inventory,
            "broker_snapshot": state_freshness,
            "paper_validation_ready": paper_validation_ready,
        },
        "rag_evidence": {
            "health": rag_health,
            "ingestion": ingestion.__dict__,
            "warmup": warmup,
            "governance_quarantined": ingestion.rejected,
            "evaluation": rag_eval,
            "world_class_passed": rag_production_passed,
        },
        "live_capital_gate": live_gate.as_dict(),
        "profit_outcome": remittance.as_dict(),
        "verdicts": {
            "engineering_world_class_ready": rag_production_passed and target_consistent,
            "paper_validation_ready": paper_validation_ready,
            "live_capital_ready": live_gate.allowed,
            "monthly_after_tax_goal_proven": remittance.claim_allowed,
            "world_class_system_ready": bool(
                rag_production_passed
                and target_consistent
                and paper_validation_ready
                and live_gate.allowed
            ),
        },
        "blockers": list(dict.fromkeys(blockers)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-rag-eval", action="store_true")
    parser.add_argument(
        "--allow-not-ready",
        action="store_true",
        help="Return zero for audit/reporting even when the gate is closed",
    )
    args = parser.parse_args()
    report = build_readiness(include_rag_eval=not args.skip_rag_eval)
    if args.json:
        print(json.dumps(to_json_safe(report), indent=2, allow_nan=False))
    else:
        print("=== WORLD-CLASS TRADING READINESS ===")
        print(json.dumps(report["verdicts"], indent=2))
        for blocker in report["blockers"]:
            print(f"BLOCK: {blocker}")
    if args.allow_not_ready:
        return 0
    return 0 if report["verdicts"]["world_class_system_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
