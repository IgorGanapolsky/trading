#!/usr/bin/env python3
"""Autonomous historical learning backfill for RAG + RLHF/ML."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.learning.distributed_feedback import LocalBackend, aggregate_feedback  # noqa: E402

from scripts.build_rag_query_index import main as rebuild_rag_query_index  # noqa: E402
from scripts.train_from_feedback import recompute_from_history  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _closed_trades(trades_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = trades_payload.get("trades", [])
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("status", "")).lower() == "closed"
    ]


def _feedback_type(trade: dict[str, Any]) -> str | None:
    outcome = str(trade.get("outcome", "")).strip().lower()
    pnl = _to_float(trade.get("realized_pnl", trade.get("pnl", trade.get("pl"))), 0.0)
    if outcome == "win":
        return "positive"
    if outcome == "loss":
        return "negative"
    if outcome == "breakeven":
        return None
    if pnl > 0:
        return "positive"
    if pnl < 0:
        return "negative"
    return None


def _trade_fingerprint(trade: dict[str, Any]) -> str:
    material = {
        "trade_id": trade.get("trade_id"),
        "symbol": trade.get("symbol"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "status": trade.get("status"),
        "outcome": trade.get("outcome"),
        "realized_pnl": trade.get("realized_pnl", trade.get("pnl", trade.get("pl"))),
    }
    payload = json.dumps(material, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _event_key(trade: dict[str, Any]) -> str:
    return f"historical_trade_backfill::{_trade_fingerprint(trade)}"


def _context_for_trade(trade: dict[str, Any]) -> str:
    pnl = _to_float(trade.get("realized_pnl", trade.get("pnl", trade.get("pl"))), 0.0)
    symbol = str(trade.get("symbol") or "UNKNOWN")
    strategy = str(trade.get("strategy") or "trade")
    outcome = str(trade.get("outcome") or "").lower() or (
        "win" if pnl > 0 else "loss" if pnl < 0 else "flat"
    )
    exit_date = str(trade.get("exit_date") or trade.get("timestamp") or "unknown")
    return (
        "historical backfill trade outcome "
        f"symbol={symbol} strategy={strategy} outcome={outcome} pnl={pnl:.2f} "
        f"exit_date={exit_date}"
    )


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _render_lesson(
    now_utc: datetime, summary: dict[str, Any], strategy_rows: list[dict[str, Any]]
) -> str:
    lines: list[str] = []
    lines.append("# Historical Learning Backfill (Automated)")
    lines.append("")
    lines.append(f"**Date**: {now_utc.date().isoformat()}")
    lines.append("**Severity**: MEDIUM")
    lines.append("**Category**: rl-historical-backfill")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        "Automated historical backfill converted closed trades into RLHF events, "
        "updated Thompson model inputs, and refreshed RAG-discoverable historical evidence."
    )
    lines.append("")
    lines.append("## Backfill Metrics")
    lines.append(f"- Closed trades scanned: {summary.get('closed_trades_scanned', 0)}")
    lines.append(f"- Eligible events: {summary.get('eligible_events', 0)}")
    lines.append(f"- Positive events: {summary.get('positive_events', 0)}")
    lines.append(f"- Negative events: {summary.get('negative_events', 0)}")
    lines.append(f"- Applied events: {summary.get('applied_events', 0)}")
    lines.append(f"- Duplicate events skipped: {summary.get('duplicate_events', 0)}")
    lines.append(f"- Neutral events skipped: {summary.get('neutral_events_skipped', 0)}")
    lines.append("")
    lines.append("## Strategy Breakdown")
    lines.append("| Strategy | Trades | Net PnL | Wins | Losses |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in strategy_rows:
        lines.append(
            f"| {row['strategy']} | {row['trades']} | {row['net_pnl']:.2f} | {row['wins']} | {row['losses']} |"
        )
    if not strategy_rows:
        lines.append("| n/a | 0 | 0.00 | 0 | 0 |")
    lines.append("")
    lines.append("## Prevention")
    lines.append(
        "Use idempotent event keys from historical trades so RLHF model updates are deterministic "
        "and re-runs do not double-count prior outcomes."
    )
    lines.append("")
    lines.append("## Tags")
    lines.append("`rlhf`, `historical-data`, `thompson-sampling`, `rag`, `automation`")
    lines.append("")
    return "\n".join(lines)


def _strategy_breakdown(closed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_strategy: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "net_pnl": 0.0, "wins": 0, "losses": 0}
    )
    for trade in closed:
        strategy = str(trade.get("strategy") or "unknown")
        pnl = _to_float(trade.get("realized_pnl", trade.get("pnl", trade.get("pl"))), 0.0)
        ftype = _feedback_type(trade)
        row = by_strategy[strategy]
        row["trades"] += 1
        row["net_pnl"] += pnl
        if ftype == "positive":
            row["wins"] += 1
        elif ftype == "negative":
            row["losses"] += 1
    results = [
        {
            "strategy": strategy,
            "trades": int(row["trades"]),
            "net_pnl": float(row["net_pnl"]),
            "wins": int(row["wins"]),
            "losses": int(row["losses"]),
        }
        for strategy, row in by_strategy.items()
    ]
    results.sort(key=lambda item: item["trades"], reverse=True)
    return results


def run_pipeline(
    *,
    project_root: Path,
    trades_path: Path,
    lesson_path: Path,
    audit_log_path: Path,
    recompute_model: bool = True,
    rebuild_rag_index_flag: bool = True,
    dry_run: bool = False,
    max_events: int = 0,
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    trades_payload = _load_json(trades_path)
    closed = _closed_trades(trades_payload)
    if max_events > 0:
        closed = closed[:max_events]

    summary: dict[str, Any] = {
        "generated_at_utc": now_utc.isoformat().replace("+00:00", "Z"),
        "closed_trades_scanned": len(closed),
        "eligible_events": 0,
        "positive_events": 0,
        "negative_events": 0,
        "neutral_events_skipped": 0,
        "applied_events": 0,
        "duplicate_events": 0,
        "errors": 0,
        "recomputed_model": False,
        "reindexed_rag_query": False,
        "dry_run": dry_run,
    }

    for trade in closed:
        feedback_type = _feedback_type(trade)
        if feedback_type is None:
            summary["neutral_events_skipped"] += 1
            continue

        summary["eligible_events"] += 1
        if feedback_type == "positive":
            summary["positive_events"] += 1
        else:
            summary["negative_events"] += 1

        event_key = _event_key(trade)
        context = _context_for_trade(trade)

        if dry_run:
            continue

        try:
            outcome = aggregate_feedback(
                project_root=project_root,
                event_key=event_key,
                feedback_type=feedback_type,
                context=context,
                backend=LocalBackend(),
            )
        except Exception:
            summary["errors"] += 1
            continue

        if outcome.get("applied") is True:
            summary["applied_events"] += 1
            _append_jsonl(
                audit_log_path,
                {
                    "timestamp": now_utc.isoformat(),
                    "source": "historical_learning_backfill",
                    "event_key": event_key,
                    "feedback": feedback_type,
                    "symbol": trade.get("symbol"),
                    "strategy": trade.get("strategy"),
                    "outcome": trade.get("outcome"),
                    "realized_pnl": trade.get("realized_pnl", trade.get("pnl", trade.get("pl"))),
                },
            )
        elif outcome.get("skipped_reason") == "duplicate_event":
            summary["duplicate_events"] += 1

    strategy_rows = _strategy_breakdown(closed)
    summary["strategy_breakdown"] = strategy_rows

    if not dry_run:
        lesson_path.parent.mkdir(parents=True, exist_ok=True)
        lesson_path.write_text(_render_lesson(now_utc, summary, strategy_rows), encoding="utf-8")

        if recompute_model:
            recompute_from_history()
            summary["recomputed_model"] = True
        if rebuild_rag_index_flag:
            rebuild_rag_query_index()
            summary["reindexed_rag_query"] = True

    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill historical learning into RLHF + RAG.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--trades", default="data/trades.json")
    parser.add_argument(
        "--lesson",
        default="rag_knowledge/lessons_learned/ll_historical_learning_backfill.md",
    )
    parser.add_argument(
        "--audit-log",
        default="data/feedback/feedback_historical_backfill.jsonl",
    )
    parser.add_argument(
        "--json-out",
        default="artifacts/devloop/historical_learning_backfill.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-events", type=int, default=0)
    parser.add_argument("--skip-recompute-model", action="store_true")
    parser.add_argument("--skip-rebuild-rag-index", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    project_root = Path(args.project_root).resolve()
    summary = run_pipeline(
        project_root=project_root,
        trades_path=project_root / args.trades,
        lesson_path=project_root / args.lesson,
        audit_log_path=project_root / args.audit_log,
        recompute_model=not args.skip_recompute_model,
        rebuild_rag_index_flag=not args.skip_rebuild_rag_index,
        dry_run=bool(args.dry_run),
        max_events=max(0, int(args.max_events)),
    )
    _write_json(project_root / args.json_out, summary)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
