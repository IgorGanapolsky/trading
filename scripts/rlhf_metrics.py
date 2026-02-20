#!/usr/bin/env python3
"""Compute RLHF success metrics from JSONL feedback logs."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).parent.parent
FEEDBACK_LOG = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "feedback-log.jsonl"
DATA_FEEDBACK_DIR = PROJECT_ROOT / "data" / "feedback"
STATS_PATH = DATA_FEEDBACK_DIR / "stats.json"
METRICS_PATH = DATA_FEEDBACK_DIR / "metrics.json"
MEMALIGN_DIR = PROJECT_ROOT / ".claude" / "memory" / "memalign"
MEMALIGN_EPISODES = MEMALIGN_DIR / "episodes.jsonl"
MEMALIGN_PRINCIPLES = MEMALIGN_DIR / "principles.jsonl"
CORTEX_LEDGER = PROJECT_ROOT / ".claude" / "memory" / "feedback" / "cortex_ledger.jsonl"
PENDING_CORTEX_PATHS = [
    PROJECT_ROOT / ".claude" / "memory" / "feedback" / "pending_cortex_sync.jsonl",
    PROJECT_ROOT / ".claude" / "memory" / "pending_cortex_sync.jsonl",
]
SHIELDCORTEX_DB = Path.home() / ".shieldcortex" / "memories.db"

SUCCESS_TARGETS = {
    "satisfaction_rate": 70.0,
    "last_7d_satisfaction_rate": 60.0,
    "memalign_sync_rate": 0.9,
    "cortex_sync_rate": 0.9,
    "pending_cortex_sync_max": 0,
}


CATEGORY_RULES = {
    "testing": r"test|pytest|unittest|coverage",
    "ci": r"ci|workflow|action|pipeline",
    "trade": r"trade|order|position|entry|exit",
    "rag": r"rag|lesson|lancedb|retrieval",
    "pr": r"pr|pull request|merge|branch",
    "refactor": r"refactor|cleanup|simplify|format",
    "debugging": r"debug|error|stack trace|log",
    "security": r"security|secret|vulnerability|xss|injection",
    "research": r"research|backtest|analysis",
}


def iter_feedback_entries() -> Iterable[dict]:
    if FEEDBACK_LOG.exists():
        yield from _iter_jsonl(FEEDBACK_LOG)

    if DATA_FEEDBACK_DIR.exists():
        for path in sorted(DATA_FEEDBACK_DIR.glob("feedback_*.jsonl")):
            yield from _iter_jsonl(path)


def _iter_jsonl(path: Path) -> Iterable[dict]:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    except OSError:
        return


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _count_pending_cortex() -> int:
    for path in PENDING_CORTEX_PATHS:
        if path.exists():
            return _count_jsonl(path)
    return 0


def _shieldcortex_stats() -> dict:
    if not SHIELDCORTEX_DB.exists():
        return {"available": False}

    stats = {"available": True, "path": str(SHIELDCORTEX_DB)}
    try:
        conn = sqlite3.connect(str(SHIELDCORTEX_DB))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        stats["tables"] = tables
        table_queries = {
            "memories": "SELECT COUNT(*) FROM memories",
            "events": "SELECT COUNT(*) FROM events",
            "entities": "SELECT COUNT(*) FROM entities",
            "memory_links": "SELECT COUNT(*) FROM memory_links",
            "quarantine": "SELECT COUNT(*) FROM quarantine",
        }
        for table, query in table_queries.items():
            if table in tables:
                cur.execute(query)
                stats[f"{table}_count"] = cur.fetchone()[0]
        conn.close()
    except Exception as exc:
        stats["error"] = str(exc)
    return stats


def _evaluate_target(value: float | int | None, target: float | int) -> str:
    if value is None:
        return "no_data"
    return "pass" if value >= target else "fail"


def _normalize_signal(entry: dict) -> str | None:
    raw = entry.get("feedback") or entry.get("signal") or entry.get("type")
    if isinstance(raw, str):
        value = raw.lower()
        if value in {"positive", "thumbs_up"}:
            return "positive"
        if value in {"negative", "thumbs_down"}:
            return "negative"
    return None


def _parse_timestamp(entry: dict) -> datetime | None:
    ts = entry.get("timestamp") or entry.get("time")
    if not ts or not isinstance(ts, str):
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _extract_categories(entry: dict) -> list[str]:
    tags = entry.get("tags") or []
    if isinstance(tags, list) and tags:
        return [str(t) for t in tags]

    context = " ".join(
        str(entry.get(key, "")) for key in ("context", "summary", "user_message")
    ).lower()
    categories = []
    for name, pattern in CATEGORY_RULES.items():
        if re.search(pattern, context):
            categories.append(name)
    return categories


def compute_metrics() -> dict:
    entries = []
    for entry in iter_feedback_entries():
        signal = _normalize_signal(entry)
        if not signal or signal == "undo_revert":
            continue
        entry["_signal"] = signal
        entry["_timestamp"] = _parse_timestamp(entry)
        entry["_categories"] = _extract_categories(entry)
        entries.append(entry)

    total = len(entries)
    positive = sum(1 for e in entries if e["_signal"] == "positive")
    negative = total - positive
    satisfaction_rate = (positive / total * 100) if total else 0.0

    last_entry = max(
        (e for e in entries if e["_timestamp"] is not None),
        default=None,
        key=lambda e: e["_timestamp"],
    )

    last_feedback = last_entry["_signal"] if last_entry else None
    last_feedback_at = (
        last_entry["_timestamp"].isoformat() if last_entry and last_entry["_timestamp"] else None
    )

    cutoff = datetime.now() - timedelta(days=7)
    last_7d = [e for e in entries if e["_timestamp"] and e["_timestamp"] >= cutoff]
    last_7d_total = len(last_7d)
    last_7d_positive = sum(1 for e in last_7d if e["_signal"] == "positive")
    last_7d_rate = (last_7d_positive / last_7d_total * 100) if last_7d_total else 0.0

    category_counts: dict[str, int] = {}
    for entry in entries:
        for category in entry.get("_categories", []):
            category_counts[category] = category_counts.get(category, 0) + 1

    memalign_episodes = _count_jsonl(MEMALIGN_EPISODES)
    memalign_principles = _count_jsonl(MEMALIGN_PRINCIPLES)
    cortex_ledger_entries = _count_jsonl(CORTEX_LEDGER)
    pending_cortex_sync = _count_pending_cortex()

    metrics = {
        "positive": positive,
        "negative": negative,
        "total": total,
        "satisfaction_rate": round(satisfaction_rate, 2),
        "last_feedback": last_feedback,
        "last_feedback_at": last_feedback_at,
        "last_updated": datetime.now().isoformat(),
        "last_7d_total": last_7d_total,
        "last_7d_positive": last_7d_positive,
        "last_7d_satisfaction_rate": round(last_7d_rate, 2),
        "category_counts": dict(sorted(category_counts.items())),
        "rlhf_pipeline": {
            "feedback_log_entries": total,
            "memalign_episodes": memalign_episodes,
            "memalign_principles": memalign_principles,
            "cortex_ledger_entries": cortex_ledger_entries,
            "pending_cortex_sync": pending_cortex_sync,
            "memalign_sync_rate": round((memalign_episodes / total), 2) if total else None,
            "cortex_sync_rate": round((cortex_ledger_entries / total), 2) if total else None,
        },
        "shieldcortex": _shieldcortex_stats(),
    }

    pipeline = metrics["rlhf_pipeline"]
    metrics["success_targets"] = {
        "satisfaction_rate": {
            "target": SUCCESS_TARGETS["satisfaction_rate"],
            "value": metrics["satisfaction_rate"],
            "status": _evaluate_target(
                metrics["satisfaction_rate"], SUCCESS_TARGETS["satisfaction_rate"]
            ),
        },
        "last_7d_satisfaction_rate": {
            "target": SUCCESS_TARGETS["last_7d_satisfaction_rate"],
            "value": metrics["last_7d_satisfaction_rate"],
            "status": _evaluate_target(
                metrics["last_7d_satisfaction_rate"],
                SUCCESS_TARGETS["last_7d_satisfaction_rate"],
            ),
        },
        "memalign_sync_rate": {
            "target": SUCCESS_TARGETS["memalign_sync_rate"],
            "value": pipeline["memalign_sync_rate"],
            "status": _evaluate_target(
                pipeline["memalign_sync_rate"], SUCCESS_TARGETS["memalign_sync_rate"]
            ),
        },
        "cortex_sync_rate": {
            "target": SUCCESS_TARGETS["cortex_sync_rate"],
            "value": pipeline["cortex_sync_rate"],
            "status": _evaluate_target(
                pipeline["cortex_sync_rate"], SUCCESS_TARGETS["cortex_sync_rate"]
            ),
        },
        "pending_cortex_sync": {
            "target": SUCCESS_TARGETS["pending_cortex_sync_max"],
            "value": pipeline["pending_cortex_sync"],
            "status": "pass"
            if pipeline["pending_cortex_sync"] <= SUCCESS_TARGETS["pending_cortex_sync_max"]
            else "fail",
        },
    }

    return metrics


def write_metrics(metrics: dict) -> None:
    DATA_FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(
        json.dumps(
            {
                "positive": metrics["positive"],
                "negative": metrics["negative"],
                "total": metrics["total"],
                "last_feedback": metrics["last_feedback"],
                "last_updated": metrics["last_updated"],
                "satisfaction_rate": metrics["satisfaction_rate"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute RLHF metrics")
    parser.add_argument("--print", action="store_true", help="Print metrics JSON")
    args = parser.parse_args()

    metrics = compute_metrics()
    write_metrics(metrics)
    if args.print:
        print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
