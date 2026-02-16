#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

METRIC_RE = re.compile(r"^- ([^:]+): (.+) \[([A-Z]+)\] \((.*)\)$")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def checklist_progress(path: Path) -> tuple[int, int]:
    text = read_text(path)
    done = 0
    total = 0
    for line in text.splitlines():
        if line.startswith("- [x] ") or line.startswith("- [ ] "):
            total += 1
            if line.startswith("- [x] "):
                done += 1
    return done, total


def parse_metrics(path: Path) -> list[tuple[str, str, str, str]]:
    metrics: list[tuple[str, str, str, str]] = []
    for line in read_text(path).splitlines():
        m = METRIC_RE.match(line.strip())
        if m:
            metrics.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    return metrics


def extract_lines(path: Path, prefixes: list[str]) -> list[str]:
    out: list[str] = []
    for line in read_text(path).splitlines():
        s = line.strip()
        for p in prefixes:
            if s.startswith(p):
                out.append(s)
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one-page KPI summary.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--out", default="artifacts/devloop/kpi_page.md", help="Output markdown path"
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    scorecard = repo_root / "artifacts/devloop/profit_readiness_scorecard.md"
    checklist = repo_root / "artifacts/tars/judge_demo_checklist.md"

    done, total = checklist_progress(checklist)
    metrics = parse_metrics(scorecard)
    seven_day_lines = extract_lines(
        scorecard,
        prefixes=[
            "- Equity delta",
            "- Monthly run-rate estimate",
            "- Data source",
            "- North Star target",
        ],
    )
    pass_count = sum(1 for _, _, status, _ in metrics if status == "PASS")
    warn_count = sum(1 for _, _, status, _ in metrics if status == "WARN")
    unknown_count = sum(1 for _, _, status, _ in metrics if status == "UNKNOWN")

    lines: list[str] = []
    lines.append("# KPI Page")
    lines.append("")
    lines.append("## Snapshot")
    lines.append(f"- Demo checklist completion: {done}/{total}")
    lines.append(
        f"- Readiness metrics: PASS={pass_count}, WARN={warn_count}, UNKNOWN={unknown_count}"
    )
    lines.append("")
    lines.append("## Reliability")
    lines.append("- Dev loop status: `artifacts/devloop/tasks.md`")
    lines.append("- Scorecard: `artifacts/devloop/profit_readiness_scorecard.md`")
    lines.append("")
    lines.append("## Business Readiness")
    if not metrics:
        lines.append("- No metrics found. Generate scorecard first.")
    else:
        for name, value, status, _ in metrics:
            lines.append(f"- {name}: {value} [{status}]")
    lines.append("")
    lines.append("## 7-Day Trend")
    if seven_day_lines:
        lines.extend(seven_day_lines)
    else:
        lines.append("- 7-day trend unavailable.")
    lines.append("")
    lines.append("## Demo Readiness")
    lines.append("- Judge checklist: `artifacts/tars/judge_demo_checklist.md`")
    lines.append("- Submission summary: `artifacts/tars/submission_summary.md`")
    lines.append("- Smoke metrics: `artifacts/tars/smoke_metrics.txt`")
    lines.append("")
    lines.append("## Next Actions")
    lines.append("1. Clear WARN metrics in scorecard, starting with win rate/run-rate.")
    lines.append("2. Keep checklist at 100% before demo/submission.")
    lines.append("3. Re-run `./scripts/layered_tdd_loop.sh run` after every meaningful change.")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok: kpi page generated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
