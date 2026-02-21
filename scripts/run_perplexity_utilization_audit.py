#!/usr/bin/env python3
"""Run Perplexity utilization audit with optional live API probe."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
from src.analytics.perplexity_utilization_audit import (
    PERPLEXITY_ENDPOINT,
    append_jsonl,
    build_perplexity_usage_snapshot,
    render_markdown_report,
    write_json,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path.",
    )
    parser.add_argument(
        "--summary-out",
        default="data/analytics/perplexity_utilization_latest.json",
        help="JSON summary output path.",
    )
    parser.add_argument(
        "--jsonl-out",
        default="data/analytics/perplexity_utilization_history.jsonl",
        help="JSONL history output path.",
    )
    parser.add_argument(
        "--markdown-out",
        default="data/analytics/perplexity_utilization_latest.md.txt",
        help="Markdown summary output path.",
    )
    parser.add_argument(
        "--probe-live",
        action="store_true",
        help="Execute a live chat completion probe using PERPLEXITY_API_KEY.",
    )
    parser.add_argument(
        "--probe-model",
        default=os.getenv("PERPLEXITY_PROBE_MODEL", "sonar"),
        help="Model to probe (default: sonar).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="HTTP timeout for live probe.",
    )
    parser.add_argument(
        "--workflow-limit",
        type=int,
        default=2,
        help="Recent run count per workflow.",
    )
    return parser.parse_args()


def _run_gh_json(args: list[str]) -> Any:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def _recent_workflow_runs(workflow_paths: list[str], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workflow_path in workflow_paths:
        workflow_name = Path(workflow_path).name
        payload = _run_gh_json(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                workflow_name,
                "--limit",
                str(limit),
                "--json",
                "name,workflowName,status,conclusion,createdAt,updatedAt,url",
            ]
        )
        if not isinstance(payload, list):
            continue
        for run in payload:
            if not isinstance(run, dict):
                continue
            rows.append(
                {
                    "workflow": workflow_name,
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "created_at": run.get("createdAt"),
                    "updated_at": run.get("updatedAt"),
                    "url": run.get("url"),
                }
            )
    return rows


def _probe_live(model: str, timeout_seconds: int) -> dict[str, Any]:
    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        return {
            "enabled": True,
            "status": "skipped",
            "detail": "PERPLEXITY_API_KEY missing",
            "model": model,
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Respond with exactly one token: OK",
            }
        ],
        "max_tokens": 4,
    }

    t0 = time.perf_counter()
    try:
        response = requests.post(
            PERPLEXITY_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        body = {}
        try:
            body = response.json()
        except Exception:
            body = {}
        status = "success" if response.status_code < 300 else "failed"
        usage = body.get("usage", {}) if isinstance(body, dict) else {}
        return {
            "enabled": True,
            "status": status,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "model": model,
            "usage": usage if isinstance(usage, dict) else {},
            "detail": body.get("error", {}).get("message")
            if isinstance(body.get("error"), dict)
            else body.get("error"),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "failed",
            "model": model,
            "detail": str(exc),
        }


def _derive_gaps(report: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    workflow_scan = report.get("workflow_scan", {})
    if int(workflow_scan.get("count", 0)) == 0:
        gaps.append("No workflow currently references Perplexity.")

    source_presence = report.get("source_presence", {})
    for key in ("research_agent", "weekend_research_workflow", "pre_market_scan_workflow"):
        if not source_presence.get(key):
            gaps.append(f"Missing expected integration artifact: {key}.")

    live_probe = report.get("live_probe", {})
    if live_probe.get("enabled") and live_probe.get("status") != "success":
        gaps.append("Live API probe did not succeed.")

    recent_runs = report.get("recent_workflow_runs", [])
    if not recent_runs:
        gaps.append("No recent workflow-run evidence found via gh CLI.")

    return gaps


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()

    report = build_perplexity_usage_snapshot(repo_root)
    report["local_env"] = {
        "perplexity_api_key_present": bool(os.getenv("PERPLEXITY_API_KEY", "").strip())
    }

    workflow_paths = [
        row.get("path")
        for row in report.get("workflow_scan", {}).get("workflows_with_perplexity", [])
        if isinstance(row.get("path"), str)
    ]
    report["recent_workflow_runs"] = _recent_workflow_runs(workflow_paths, args.workflow_limit)

    if args.probe_live:
        report["live_probe"] = _probe_live(args.probe_model, args.timeout_seconds)

    report["gaps"] = _derive_gaps(report)

    summary_out = repo_root / args.summary_out
    jsonl_out = repo_root / args.jsonl_out
    markdown_out = repo_root / args.markdown_out

    write_json(summary_out, report)
    append_jsonl(jsonl_out, report)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown_report(report), encoding="utf-8")

    print(f"wrote {summary_out}")
    print(f"wrote {jsonl_out}")
    print(f"wrote {markdown_out}")
    print(json.dumps({"gaps": report.get("gaps", [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
