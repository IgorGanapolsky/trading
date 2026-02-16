#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

METRIC_LINE_RE = re.compile(r"^- ([^:]+): (.+) \[([A-Z]+)\]")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def section_lines(path: Path, header: str) -> list[str]:
    lines = read_text(path).splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("## ") and stripped == f"## {header}":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            out.append(stripped)
    return out


def parse_number(text: str) -> float | None:
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not matches:
        return None
    try:
        return float(matches[0])
    except Exception:
        return None


def parse_scorecard(scorecard_path: Path) -> list[dict]:
    metrics: list[dict] = []
    for header in ("Metrics", "7-Day Delta"):
        for line in section_lines(scorecard_path, header):
            m = METRIC_LINE_RE.match(line.strip())
            if not m:
                continue
            name = m.group(1).strip()
            value_text = m.group(2).strip()
            status = m.group(3).strip()
            value = parse_number(value_text)
            metrics.append(
                {
                    "name": name,
                    "value_text": value_text,
                    "value": value,
                    "status": status,
                    "section": header,
                }
            )
    return metrics


def metric_deficit(metric: dict) -> float:
    name = metric["name"]
    value = metric["value"]
    status = metric["status"]
    if status == "UNKNOWN":
        return 100.0

    if name == "Win Rate":
        if value is None:
            return 100.0
        return max(0.0, ((55.0 - value) / 55.0) * 100.0)
    if name == "Monthly run-rate estimate":
        if value is None:
            return 100.0
        return max(0.0, ((6000.0 - value) / 6000.0) * 100.0)
    if name.startswith("Equity delta"):
        if value is None:
            return 100.0
        return 0.0 if value > 0 else 100.0
    if name == "Max Drawdown (sync history)":
        if value is None:
            return 100.0
        return max(0.0, ((value - 5.0) / 5.0) * 100.0)
    if name == "Execution Quality (valid trade records)":
        if value is None:
            return 100.0
        return max(0.0, ((95.0 - value) / 95.0) * 100.0)
    if name == "Gateway Latency":
        if value is None:
            return 100.0
        return max(0.0, ((value - 2500.0) / 2500.0) * 100.0)
    if name == "Gateway Cost (smoke call)":
        if value is None:
            return 100.0
        return 0.0
    if name == "Weekly Qualified Setups":
        if value is None:
            return 100.0
        return max(0.0, ((3.0 - value) / 3.0) * 100.0)
    if name == "Weekly Closed Trades":
        if value is None:
            return 100.0
        return max(0.0, ((1.0 - value) / 1.0) * 100.0)
    return 0.0 if status == "PASS" else 25.0


def task_bank(metric_name: str) -> list[str]:
    mapping = {
        "Win Rate": [
            "Design and implement stricter entry gating (trend/volatility/session filters) and add integration tests proving reduced bad entries.",
            "Create a win-rate validation artifact comparing baseline vs new filter over recent sample and block promotion if <55%.",
        ],
        "Monthly run-rate estimate": [
            "Add a run-rate promotion gate artifact that fails when monthly estimate is below $6,000 target.",
            "Implement one measurable strategy improvement and produce before/after run-rate artifact using same sampling window.",
        ],
        "Equity delta": [
            "Add weekly equity-delta guardrails with warning flags and an auto-generated trend artifact for 7d/30d deltas.",
            "Implement drawup-focused risk/reward tuning and produce before/after equity-delta artifact.",
        ],
        "Max Drawdown (sync history)": [
            "Tighten drawdown controls and add integration checks that enforce max drawdown <=5% in simulation outputs.",
        ],
        "Execution Quality (valid trade records)": [
            "Strengthen execution record validation pipeline and add tests that enforce >=95% valid trade records.",
        ],
        "Gateway Latency": [
            "Add gateway timeout/fallback tuning and generate p95 latency artifact proving under-threshold behavior.",
        ],
        "Gateway Cost (smoke call)": [
            "Implement prompt/token budget regression check and artifact that tracks cost trend by cycle.",
        ],
        "Weekly Qualified Setups": [
            "Run no-trade weekly diagnostics and relax/adjust entry filters in paper mode to achieve at least 3 qualified setups per week.",
            "Add setup-cadence telemetry artifact (daily setup count and gate reached) and fail cadence check when <3/week.",
        ],
        "Weekly Closed Trades": [
            "Add weekly execution conversion checks from qualified setups to closed trades and alert if fewer than 1 close/week.",
            "Review strategy cadence and blocked-gate categories; propose either defined-risk strategy expansion or North Star assumption revision when repeated misses persist.",
        ],
    }
    return mapping.get(
        metric_name, [f"Improve KPI metric: {metric_name} with measurable artifact proof."]
    )


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate KPI priority and stall-pivot recommendations for devloop."
    )
    parser.add_argument(
        "--scorecard",
        default="artifacts/devloop/profit_readiness_scorecard.md",
        help="Scorecard markdown path",
    )
    parser.add_argument(
        "--state",
        default="artifacts/devloop/kpi_priority_state.json",
        help="State file for stall tracking",
    )
    parser.add_argument(
        "--out-md",
        default="artifacts/devloop/kpi_priority_report.md",
        help="Markdown report output",
    )
    parser.add_argument(
        "--out-json",
        default="artifacts/devloop/kpi_priority.json",
        help="JSON output for automation",
    )
    parser.add_argument(
        "--stall-window",
        type=int,
        default=6,
        help="Cycles with same focus metric before pivot mode",
    )
    args = parser.parse_args()

    scorecard_path = Path(args.scorecard)
    state_path = Path(args.state)
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    metrics = parse_scorecard(scorecard_path)
    ranked: list[dict] = []
    for metric in metrics:
        deficit = metric_deficit(metric)
        ranked.append({**metric, "deficit": round(deficit, 4)})
    ranked.sort(key=lambda x: x["deficit"], reverse=True)

    focus = ranked[0]["name"] if ranked else "None"
    focus_deficit = ranked[0]["deficit"] if ranked else 0.0

    prev_state = load_state(state_path)
    prev_focus = str(prev_state.get("focus_metric", ""))
    prev_cycles = int(prev_state.get("same_focus_cycles", 0))
    same_focus_cycles = prev_cycles + 1 if focus == prev_focus else 1
    stall_pivot = same_focus_cycles >= max(1, args.stall_window) and focus != "None"

    recommended_tasks = task_bank(focus)[:2] if focus != "None" else []
    pivot_tasks: list[str] = []
    if stall_pivot:
        pivot_tasks = [
            f"STALL PIVOT: For focus metric `{focus}`, run a simulation/backtest matrix and generate artifact proving best configuration before further feature work.",
            "STALL PIVOT: Add an implementation-level gate test that must fail if KPI regresses versus baseline artifact.",
        ]

    new_state = {
        "focus_metric": focus,
        "focus_deficit": focus_deficit,
        "same_focus_cycles": same_focus_cycles,
        "stall_pivot": stall_pivot,
        "stall_window": args.stall_window,
    }
    state_path.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")

    out_payload = {
        "focus_metric": focus,
        "focus_deficit": focus_deficit,
        "same_focus_cycles": same_focus_cycles,
        "stall_pivot": stall_pivot,
        "recommended_tasks": recommended_tasks,
        "pivot_tasks": pivot_tasks,
        "ranked_metrics": ranked[:8],
    }
    out_json.write_text(json.dumps(out_payload, indent=2) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# KPI Priority Report")
    lines.append("")
    lines.append("## Focus")
    lines.append(f"- Focus metric: {focus}")
    lines.append(f"- Deficit score: {focus_deficit:.2f}")
    lines.append(f"- Same-focus cycles: {same_focus_cycles}")
    lines.append(f"- Stall pivot active: {'yes' if stall_pivot else 'no'}")
    lines.append("")
    lines.append("## Ranked Gaps")
    if ranked:
        for metric in ranked[:8]:
            lines.append(
                f"- {metric['name']}: {metric['value_text']} [{metric['status']}] deficit={metric['deficit']:.2f}"
            )
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Recommended Tasks")
    if recommended_tasks:
        for task in recommended_tasks:
            lines.append(f"- {task}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Stall Pivot Tasks")
    if pivot_tasks:
        for task in pivot_tasks:
            lines.append(f"- {task}")
    else:
        lines.append("- None")
    lines.append("")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"ok: kpi priority report -> {out_md}")
    print(f"ok: kpi priority json -> {out_json}")
    print(f"focus_metric={focus}")
    print(f"stall_pivot={'1' if stall_pivot else '0'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
