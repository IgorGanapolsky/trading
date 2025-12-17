#!/usr/bin/env python3
"""
Trace Analyzer - LangSmith Fetch equivalent for Claude Code.

This script fetches and analyzes execution traces, enabling Claude Code
to understand agent behavior and propose improvements - implementing the
"coding agent refactoring prompts" pattern from LangChain's webinar.

Usage:
    python scripts/trace_analyzer.py                    # Latest traces summary
    python scripts/trace_analyzer.py --last 10          # Last 10 traces
    python scripts/trace_analyzer.py --date 2025-12-17  # Specific day
    python scripts/trace_analyzer.py --errors           # Only errors
    python scripts/trace_analyzer.py --slow 1000        # Traces >1000ms
    python scripts/trace_analyzer.py --cost             # Cost analysis

The output is designed for Claude Code to consume and analyze.

Created: Dec 17, 2025
Purpose: Enable trace-based self-improvement loop
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TRACES_DIR = Path("data/traces")


def load_traces(date: str | None = None, days: int = 7) -> list[dict[str, Any]]:
    """Load traces from JSONL files."""
    traces = []

    if date:
        dates = [date]
    else:
        dates = [
            (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        ]

    for d in dates:
        trace_file = TRACES_DIR / f"traces_{d}.jsonl"
        if trace_file.exists():
            with open(trace_file) as f:
                for line in f:
                    try:
                        traces.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    return traces


def summarize_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a summary of traces for Claude Code analysis."""
    if not traces:
        return {"status": "no_traces", "message": "No traces found in data/traces/"}

    summary = {
        "total_traces": len(traces),
        "total_spans": 0,
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "avg_duration_ms": 0.0,
        "by_type": defaultdict(int),
        "by_status": defaultdict(int),
        "errors": [],
        "slow_operations": [],  # >500ms
        "cost_outliers": [],    # >$0.01 per trace
        "decision_chain": [],   # Recent decision flow
    }

    durations = []

    for trace in traces:
        summary["total_cost_usd"] += trace.get("total_cost_usd", 0)
        summary["total_tokens"] += trace.get("total_tokens", 0)
        durations.append(trace.get("total_duration_ms", 0))

        # Track cost outliers
        if trace.get("total_cost_usd", 0) > 0.01:
            summary["cost_outliers"].append({
                "trace_id": trace.get("trace_id", "unknown")[:8],
                "name": trace.get("name", "unknown"),
                "cost": trace.get("total_cost_usd", 0),
            })

        for span in trace.get("spans", []):
            summary["total_spans"] += 1
            summary["by_type"][span.get("trace_type", "unknown")] += 1
            summary["by_status"][span.get("status", "unknown")] += 1

            # Collect errors
            if span.get("status") == "error":
                summary["errors"].append({
                    "span_id": span.get("span_id", "unknown"),
                    "name": span.get("name", "unknown"),
                    "error": span.get("error", "Unknown error"),
                    "inputs": span.get("inputs", {}),
                })

            # Collect slow operations
            if span.get("duration_ms", 0) > 500:
                summary["slow_operations"].append({
                    "name": span.get("name", "unknown"),
                    "duration_ms": span.get("duration_ms", 0),
                    "type": span.get("trace_type", "unknown"),
                })

    if durations:
        summary["avg_duration_ms"] = sum(durations) / len(durations)

    # Convert defaultdicts to regular dicts for JSON
    summary["by_type"] = dict(summary["by_type"])
    summary["by_status"] = dict(summary["by_status"])

    return summary


def format_for_claude(summary: dict[str, Any], verbose: bool = False) -> str:
    """Format summary for Claude Code consumption."""
    lines = [
        "# Trace Analysis Report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overview",
        f"- Total traces: {summary.get('total_traces', 0)}",
        f"- Total spans: {summary.get('total_spans', 0)}",
        f"- Total cost: ${summary.get('total_cost_usd', 0):.4f}",
        f"- Total tokens: {summary.get('total_tokens', 0):,}",
        f"- Avg duration: {summary.get('avg_duration_ms', 0):.1f}ms",
        "",
    ]

    # By type
    by_type = summary.get("by_type", {})
    if by_type:
        lines.append("## Operations by Type")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"- {t}: {count}")
        lines.append("")

    # By status
    by_status = summary.get("by_status", {})
    if by_status:
        lines.append("## Operations by Status")
        for s, count in sorted(by_status.items(), key=lambda x: -x[1]):
            lines.append(f"- {s}: {count}")
        lines.append("")

    # Errors
    errors = summary.get("errors", [])
    if errors:
        lines.append("## ⚠️ Errors Detected")
        for err in errors[:10]:  # Limit to 10
            lines.append(f"- **{err['name']}**: {err['error']}")
            if verbose and err.get("inputs"):
                lines.append(f"  - Inputs: {json.dumps(err['inputs'], default=str)[:200]}")
        lines.append("")

    # Slow operations
    slow = summary.get("slow_operations", [])
    if slow:
        lines.append("## 🐢 Slow Operations (>500ms)")
        for op in sorted(slow, key=lambda x: -x["duration_ms"])[:10]:
            lines.append(f"- {op['name']}: {op['duration_ms']:.0f}ms ({op['type']})")
        lines.append("")

    # Cost outliers
    cost_outliers = summary.get("cost_outliers", [])
    if cost_outliers:
        lines.append("## 💰 High-Cost Operations (>$0.01)")
        for outlier in sorted(cost_outliers, key=lambda x: -x["cost"])[:5]:
            lines.append(f"- {outlier['name']}: ${outlier['cost']:.4f}")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations for Claude Code")

    if errors:
        lines.append("1. **Fix errors**: Review error patterns above and trace back to source")

    if slow:
        avg_slow = sum(op["duration_ms"] for op in slow) / len(slow)
        lines.append(f"2. **Optimize slow operations**: Average {avg_slow:.0f}ms for slow ops")

    if summary.get("total_cost_usd", 0) > 1.0:
        lines.append("3. **Review costs**: Daily spend may exceed budget - check LLM usage")

    error_rate = by_status.get("error", 0) / max(summary.get("total_spans", 1), 1)
    if error_rate > 0.1:
        lines.append(f"4. **High error rate**: {error_rate:.1%} of operations failing")

    if not any([errors, slow, cost_outliers]):
        lines.append("✅ No issues detected - system operating normally")

    return "\n".join(lines)


def get_latest_decision_chain(traces: list[dict[str, Any]], limit: int = 5) -> list[dict]:
    """Extract the most recent decision chain for analysis."""
    decisions = []

    for trace in sorted(traces, key=lambda x: x.get("start_time", ""), reverse=True):
        for span in trace.get("spans", []):
            if span.get("trace_type") == "decision":
                decisions.append({
                    "time": span.get("start_time", ""),
                    "name": span.get("name", "unknown"),
                    "inputs": span.get("inputs", {}),
                    "outputs": span.get("outputs", {}),
                    "status": span.get("status", "unknown"),
                    "duration_ms": span.get("duration_ms", 0),
                })
                if len(decisions) >= limit:
                    break
        if len(decisions) >= limit:
            break

    return decisions


def main():
    parser = argparse.ArgumentParser(
        description="Analyze execution traces for Claude Code"
    )
    parser.add_argument("--date", help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    parser.add_argument("--last", type=int, help="Show last N traces in detail")
    parser.add_argument("--errors", action="store_true", help="Show only errors")
    parser.add_argument("--slow", type=int, help="Show operations slower than N ms")
    parser.add_argument("--cost", action="store_true", help="Detailed cost analysis")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Load traces
    traces = load_traces(date=args.date, days=args.days)

    if not traces:
        print("No traces found in data/traces/")
        print("\nTo generate traces, run the trading orchestrator:")
        print("  python -c 'from src.orchestrator.main import TradingOrchestrator; t = TradingOrchestrator([\"SPY\"]); t.run()'")
        print("\nOr generate a test trace:")
        print("  python -c 'from src.observability.langsmith_tracer import get_tracer, TraceType; t = get_tracer(); t.trace(\"test\", TraceType.ANALYSIS).__enter__(); print(\"Trace created\")'")
        sys.exit(0)

    # Generate summary
    summary = summarize_traces(traces)

    # Add decision chain
    summary["recent_decisions"] = get_latest_decision_chain(traces)

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        output = format_for_claude(summary, verbose=args.verbose)
        print(output)

        # Show recent decisions
        if summary["recent_decisions"]:
            print("\n## Recent Decision Chain")
            for d in summary["recent_decisions"]:
                print(f"- [{d['time'][:19]}] {d['name']}: {d['status']} ({d['duration_ms']:.0f}ms)")
                if args.verbose and d.get("outputs"):
                    print(f"  → {json.dumps(d['outputs'], default=str)[:150]}")


if __name__ == "__main__":
    main()
