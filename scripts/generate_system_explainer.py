#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def parse_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def box(ok: bool) -> str:
    return "[x]" if ok else "[ ]"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate continuously updated system explainer doc."
    )
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--out",
        default="docs/_reports/hackathon-system-explainer.md",
        help="Markdown output path",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out = (repo_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    tars_dir = repo_root / "artifacts/tars"
    devloop_dir = repo_root / "artifacts/devloop"
    scorecard = read_text(devloop_dir / "profit_readiness_scorecard.md")
    kpi = read_text(devloop_dir / "kpi_priority_report.md")
    status = parse_kv(devloop_dir / "status.txt")
    smoke_metrics = parse_kv(tars_dir / "smoke_metrics.txt")
    smoke_response = read_json(tars_dir / "smoke_response.json")
    trade_smoke = read_json(tars_dir / "trade_opinion_smoke.json")

    checks = [
        ("Devloop status present", bool(status)),
        ("Profit readiness scorecard present", bool(scorecard.strip())),
        ("KPI priority report present", bool(kpi.strip())),
        ("Tetrate smoke metrics present", bool(smoke_metrics)),
        ("Tetrate smoke response present", bool(smoke_response)),
        ("Trade opinion smoke actionable", bool(trade_smoke.get("actionable"))),
    ]

    latest_cycle = status.get("cycle", "n/a")
    latest_profile = status.get("profile", "n/a")
    latest_timestamp = status.get("timestamp_utc", "n/a")
    latency_ms = smoke_metrics.get("latency_ms", "n/a")
    est_cost = smoke_metrics.get("estimated_total_cost_usd", "n/a")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = []
    lines.append("---")
    lines.append('title: "Hackathon System Explainer"')
    lines.append(
        'description: "How the layered TDD loop, Tetrate gateway checks, and RAG learning system work together."'
    )
    lines.append(
        'summary: "Simple-to-technical walkthrough of the continuous build-test-learn engine."'
    )
    lines.append('hero_image: "/assets/img/agent-loop-diagram.png"')
    lines.append("---")
    lines.append("")
    lines.append("# Hackathon System Explainer")
    lines.append("")
    lines.append(f"Last Updated (UTC): {now_utc}")
    lines.append("")
    lines.append("## Current Runtime Snapshot")
    lines.append(f"- Latest cycle: `{latest_cycle}`")
    lines.append(f"- Latest profile: `{latest_profile}`")
    lines.append(f"- Latest loop status timestamp: `{latest_timestamp}`")
    lines.append(f"- Latest Tetrate latency: `{latency_ms} ms`")
    lines.append(f"- Latest Tetrate estimated call cost: `{est_cost}`")
    lines.append("")
    lines.append("## Proof Checklist")
    for label, ok in checks:
        lines.append(f"- {box(ok)} {label}")
    lines.append("")
    lines.append("## How It Works (Simple)")
    lines.append("1. The system writes a task list.")
    lines.append("2. It builds one task at a time.")
    lines.append("3. It runs tests and smoke checks.")
    lines.append("4. It stores evidence and learns from results.")
    lines.append("5. It repeats until no high-value tasks remain.")
    lines.append("")
    lines.append("## How It Works (Technical)")
    lines.append("1. `scripts/continuous_devloop.sh` runs loop cycles.")
    lines.append("2. `scripts/layered_tdd_loop.sh` handles layered TDD analyze/execute.")
    lines.append("3. `scripts/tars_autopilot.sh` creates Tetrate evidence artifacts.")
    lines.append("4. `scripts/devloop_commit_and_report.sh` snapshots progress and checks PR.")
    lines.append("5. `scripts/rag_refresh_and_report.sh` refreshes retrieval memory.")
    lines.append("")
    lines.append("## System Flow Diagram")
    lines.append("```mermaid")
    lines.append("flowchart TD")
    lines.append("  A[Goals and Constraints] --> B[Layered Task Board]")
    lines.append("  B --> C[Implement Minimal Change]")
    lines.append("  C --> D[Lint and Tests]")
    lines.append("  D -->|Fail| C")
    lines.append("  D -->|Pass| E[Tetrate Smoke and Resilience]")
    lines.append("  E --> F[Scorecards and KPI Reports]")
    lines.append("  F --> G[RAG Refresh and Reindex]")
    lines.append("  G --> H[Next Tasks Generated]")
    lines.append("  H --> B")
    lines.append("```")
    lines.append("")
    lines.append("## Demo Artifacts")
    lines.append("- `artifacts/tars/submission_summary.md`")
    lines.append("- `artifacts/tars/judge_demo_checklist.md`")
    lines.append("- `artifacts/tars/smoke_metrics.txt`")
    lines.append("- `artifacts/tars/trade_opinion_smoke.json`")
    lines.append("- `artifacts/devloop/profit_readiness_scorecard.md`")
    lines.append("- `artifacts/devloop/kpi_priority_report.md`")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok: system explainer updated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
