#!/usr/bin/env python3
"""Collect and summarize agent handoff A/B metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_GATE_REPORT = "artifacts/devloop/agent_handoff_gate.json"
DEFAULT_POLICY_REPORT = "artifacts/devloop/trading_policy_ab_metrics.json"
DEFAULT_SUMMARY_OUT = "artifacts/devloop/agent_handoff_ab_metrics_latest.json"
DEFAULT_JSONL_OUT = "artifacts/devloop/agent_handoff_ab_metrics_history.jsonl"
DEFAULT_INCIDENT_ROOT = "rag_knowledge/lessons_learned"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "passed", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "failed", "fail"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _sum_gate_latency_seconds(gate_report: dict[str, Any]) -> float:
    total = 0.0
    for step in gate_report.get("steps", []):
        if isinstance(step, dict):
            total += float(step.get("duration_seconds") or 0.0)
    return round(total, 6)


def _step_passed(gate_report: dict[str, Any], step_name: str) -> bool | None:
    for step in gate_report.get("steps", []):
        if isinstance(step, dict) and step.get("name") == step_name:
            return _to_bool(step.get("passed"), default=False)
    return None


def _count_incident_files(incident_root: Path) -> int:
    if not incident_root.exists():
        return 0
    return sum(1 for p in incident_root.rglob("*.md") if p.is_file())


def _count_changed_incidents(gate_report: dict[str, Any], incident_root: Path) -> int:
    changed_paths = gate_report.get("changed_paths", [])
    if not isinstance(changed_paths, list):
        return 0

    def _norm(path: str) -> str:
        return path.replace("\\", "/").lstrip("./").lstrip("/")

    root_prefixes: set[str] = set()
    root_prefixes.add(_norm(incident_root.as_posix()).rstrip("/") + "/")

    # Gate reports usually emit repo-relative paths. Support that form even
    # when incident_root is provided as an absolute path.
    if incident_root.is_absolute():
        parts = [part for part in incident_root.parts if part not in ("/", "")]
        if len(parts) >= 2:
            root_prefixes.add("/".join(parts[-2:]).rstrip("/") + "/")

    changed = {
        _norm(path)
        for path in changed_paths
        if isinstance(path, str)
        and _norm(path).endswith(".md")
        and any(_norm(path).startswith(prefix) for prefix in root_prefixes)
    }
    return len(changed)


def collect_ab_metrics(
    *,
    variant: str,
    gate_report_path: Path,
    policy_report_path: Path,
    ci_conclusion: str,
    incident_root: Path,
) -> dict[str, Any]:
    gate_report = _load_json(gate_report_path)
    policy_report = _load_json(policy_report_path)

    policy_violations = int(
        policy_report.get("checks_failed")
        if "checks_failed" in policy_report
        else len(policy_report.get("drift_items", []))
    )

    metric = {
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "variant": variant,
        "gate_passed": _to_bool(gate_report.get("passed", False), default=False),
        "gate_latency_seconds": _sum_gate_latency_seconds(gate_report),
        "lint_passed": _step_passed(gate_report, "lint"),
        "format_passed": _step_passed(gate_report, "format"),
        "tests_passed": _step_passed(gate_report, "tests"),
        "policy_passed": _step_passed(gate_report, "trading policy drift"),
        "policy_violations": policy_violations,
        "ci_conclusion": ci_conclusion,
        "ci_pass": ci_conclusion == "success",
        "incident_count_total": _count_incident_files(incident_root),
        "incident_count_changed": _count_changed_incidents(gate_report, incident_root),
        "sources": {
            "gate_report": gate_report_path.as_posix(),
            "policy_report": policy_report_path.as_posix(),
            "incident_root": incident_root.as_posix(),
        },
    }
    return metric


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def summarize_records(records: list[dict[str, Any]], days: int) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    scoped: list[dict[str, Any]] = []
    for item in records:
        ts = _parse_timestamp(str(item.get("captured_at_utc") or ""))
        if ts and ts >= cutoff:
            scoped.append(item)

    by_variant: dict[str, list[dict[str, Any]]] = {}
    for item in scoped:
        variant = str(item.get("variant") or "unknown")
        by_variant.setdefault(variant, []).append(item)

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lookback_days": days,
        "samples": len(scoped),
        "variants": {},
    }

    for variant, items in sorted(by_variant.items()):
        total = len(items)
        gate_pass = sum(1 for x in items if x.get("gate_passed") is True)
        ci_pass = sum(1 for x in items if x.get("ci_pass") is True)
        latency = [float(x.get("gate_latency_seconds") or 0.0) for x in items]
        policy_violations = [int(x.get("policy_violations") or 0) for x in items]
        incident_total = [int(x.get("incident_count_total") or 0) for x in items]
        incident_changed = [int(x.get("incident_count_changed") or 0) for x in items]

        summary["variants"][variant] = {
            "samples": total,
            "gate_pass_rate": round(gate_pass / total, 4) if total else 0.0,
            "ci_pass_rate": round(ci_pass / total, 4) if total else 0.0,
            "avg_gate_latency_seconds": round(sum(latency) / total, 6) if total else 0.0,
            "avg_policy_violations": round(sum(policy_violations) / total, 6) if total else 0.0,
            "avg_incident_count_total": round(sum(incident_total) / total, 6) if total else 0.0,
            "avg_incident_count_changed": (
                round(sum(incident_changed) / total, 6) if total else 0.0
            ),
        }

    return summary


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and summarize agent handoff A/B metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect one metrics sample")
    collect.add_argument("--variant", choices=("A", "B"), required=True)
    collect.add_argument("--gate-report", default=DEFAULT_GATE_REPORT)
    collect.add_argument("--policy-report", default=DEFAULT_POLICY_REPORT)
    collect.add_argument(
        "--ci-conclusion",
        choices=("success", "failure", "cancelled", "unknown"),
        default="unknown",
    )
    collect.add_argument("--incident-root", default=DEFAULT_INCIDENT_ROOT)
    collect.add_argument("--summary-out", default=DEFAULT_SUMMARY_OUT)
    collect.add_argument("--jsonl-out", default=DEFAULT_JSONL_OUT)

    summarize = subparsers.add_parser("summarize", help="Summarize JSONL history")
    summarize.add_argument("--jsonl-in", default=DEFAULT_JSONL_OUT)
    summarize.add_argument("--days", type=int, default=7)
    summarize.add_argument("--summary-out", default=DEFAULT_SUMMARY_OUT)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "collect":
        record = collect_ab_metrics(
            variant=args.variant,
            gate_report_path=Path(args.gate_report),
            policy_report_path=Path(args.policy_report),
            ci_conclusion=args.ci_conclusion,
            incident_root=Path(args.incident_root),
        )
        _write_json(Path(args.summary_out), record)
        _append_jsonl(Path(args.jsonl_out), record)
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    history = _read_jsonl(Path(args.jsonl_in))
    summary = summarize_records(history, days=args.days)
    _write_json(Path(args.summary_out), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
