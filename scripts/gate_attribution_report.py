#!/usr/bin/env python3
"""
Gate Attribution Report - Diagnose which gates help/hurt trading performance.

Based on Dec 11, 2025 analysis recommendations:
1. Track rejection rate per gate
2. Measure incremental effect on win rate, Sharpe, P&L
3. Support ablation analysis (enable/disable gates)

Usage:
    python scripts/gate_attribution_report.py
    python scripts/gate_attribution_report.py --json
    python scripts/gate_attribution_report.py --ablation
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_TELEMETRY_PATH = Path("data/audit_trail/hybrid_funnel_runs.jsonl")
DEFAULT_OUTPUT_PATH = Path("reports/gate_attribution_report.json")


@dataclass
class GateStats:
    """Statistics for a single gate."""

    name: str
    total_candidates: int = 0
    rejected: int = 0
    passed: int = 0
    # P&L tracking for passed trades
    passed_trades_pnl: list[float] = field(default_factory=list)
    # Win rate for passed trades
    passed_trades_won: int = 0
    passed_trades_lost: int = 0

    @property
    def rejection_rate(self) -> float:
        if self.total_candidates == 0:
            return 0.0
        return self.rejected / self.total_candidates

    @property
    def pass_rate(self) -> float:
        if self.total_candidates == 0:
            return 0.0
        return self.passed / self.total_candidates

    @property
    def avg_pnl_per_passed_trade(self) -> float:
        if not self.passed_trades_pnl:
            return 0.0
        return sum(self.passed_trades_pnl) / len(self.passed_trades_pnl)

    @property
    def win_rate(self) -> float:
        total = self.passed_trades_won + self.passed_trades_lost
        if total == 0:
            return 0.0
        return self.passed_trades_won / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_candidates": self.total_candidates,
            "rejected": self.rejected,
            "passed": self.passed,
            "rejection_rate": round(self.rejection_rate * 100, 2),
            "pass_rate": round(self.pass_rate * 100, 2),
            "avg_pnl": round(self.avg_pnl_per_passed_trade, 2),
            "win_rate": round(self.win_rate * 100, 2),
            "total_pnl": round(sum(self.passed_trades_pnl), 2),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate gate attribution report.")
    parser.add_argument(
        "--telemetry",
        default=str(DEFAULT_TELEMETRY_PATH),
        help="Path to telemetry JSONL file.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to write JSON report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout.",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run ablation analysis (what-if scenarios).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30).",
    )
    return parser.parse_args()


def load_telemetry(path: Path) -> list[dict[str, Any]]:
    """Load telemetry entries from JSONL file."""
    entries = []
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def analyze_gate_attribution(entries: list[dict[str, Any]]) -> dict[str, GateStats]:
    """Analyze gate performance from telemetry entries."""
    # Define gate names in order
    gates = {
        "gate_0_coaching": GateStats("Mental Toughness Coach"),
        "gate_1_momentum": GateStats("Momentum Agent"),
        "gate_1_5_debate": GateStats("Bull/Bear Debate"),
        "gate_2_rl": GateStats("RL Filter"),
        "gate_3_sentiment": GateStats("LLM Sentiment"),
        "gate_4_risk": GateStats("Risk Manager"),
        "gate_4_5_gateway": GateStats("Trade Gateway"),
    }

    for entry in entries:
        # Track funnel progression
        gate_results = entry.get("gate_results", {})
        final_decision = entry.get("final_decision", "UNKNOWN")
        pnl = entry.get("realized_pnl", 0.0)

        # Process each gate
        for gate_key, stats in gates.items():
            # Check if this gate was reached
            gate_data = gate_results.get(gate_key, {})
            if not gate_data and gate_key not in entry:
                # Try alternate key formats
                alt_keys = {
                    "gate_0_coaching": ["coaching_check", "mental_check"],
                    "gate_1_momentum": ["momentum_passed", "momentum_check"],
                    "gate_1_5_debate": ["debate_passed", "debate_result"],
                    "gate_2_rl": ["rl_passed", "rl_check"],
                    "gate_3_sentiment": ["sentiment_passed", "llm_sentiment"],
                    "gate_4_risk": ["risk_passed", "risk_check"],
                    "gate_4_5_gateway": ["gateway_passed", "gateway_check"],
                }
                for alt_key in alt_keys.get(gate_key, []):
                    if alt_key in entry:
                        gate_data = {"passed": entry[alt_key]}
                        break

            if gate_data:
                stats.total_candidates += 1
                passed = gate_data.get("passed", True)  # Default to passed if not specified
                if passed:
                    stats.passed += 1
                    # If trade was executed, track P&L
                    if final_decision == "EXECUTE" and pnl != 0:
                        stats.passed_trades_pnl.append(pnl)
                        if pnl > 0:
                            stats.passed_trades_won += 1
                        else:
                            stats.passed_trades_lost += 1
                else:
                    stats.rejected += 1

    return gates


def run_ablation_analysis(
    entries: list[dict[str, Any]], gates: dict[str, GateStats]
) -> dict[str, Any]:
    """Run what-if scenarios with gates enabled/disabled."""
    scenarios = {}

    # Baseline: all gates enabled
    baseline_trades = sum(1 for e in entries if e.get("final_decision") == "EXECUTE")
    baseline_pnl = sum(
        e.get("realized_pnl", 0) for e in entries if e.get("final_decision") == "EXECUTE"
    )

    scenarios["baseline_all_gates"] = {
        "trades": baseline_trades,
        "total_pnl": round(baseline_pnl, 2),
        "avg_pnl": round(baseline_pnl / baseline_trades, 2) if baseline_trades > 0 else 0,
    }

    # Simulate disabling each gate
    for gate_key, stats in gates.items():
        if stats.rejected > 0:
            # Estimate additional trades if gate was disabled
            additional_trades = stats.rejected
            # Assume rejected trades would have avg market performance (0)
            scenarios[f"without_{gate_key}"] = {
                "additional_trades": additional_trades,
                "description": f"If {stats.name} was disabled",
                "risk": "Unknown - rejected trades have no realized P&L",
            }

    return scenarios


def generate_report(
    gates: dict[str, GateStats],
    ablation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the full attribution report."""
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_gates": len(gates),
            "gates_with_rejections": sum(1 for g in gates.values() if g.rejected > 0),
        },
        "gates": {k: v.to_dict() for k, v in gates.items()},
        "recommendations": [],
    }

    # Add recommendations based on data
    for gate_key, stats in gates.items():
        if stats.rejection_rate > 0.5:
            report["recommendations"].append(
                {
                    "gate": stats.name,
                    "issue": f"High rejection rate ({stats.rejection_rate * 100:.1f}%)",
                    "action": "Consider loosening threshold or investigating data quality",
                }
            )
        if stats.total_candidates > 0 and stats.passed == 0:
            report["recommendations"].append(
                {
                    "gate": stats.name,
                    "issue": "Zero passes - gate is blocking ALL candidates",
                    "action": "CRITICAL: Review gate configuration immediately",
                }
            )

    if ablation:
        report["ablation_analysis"] = ablation

    return report


def print_human_readable(report: dict[str, Any]) -> None:
    """Print human-readable report."""
    print("=" * 70)
    print("GATE ATTRIBUTION REPORT")
    print(f"Generated: {report['generated_at']}")
    print("=" * 70)
    print()

    print("GATE PERFORMANCE SUMMARY")
    print("-" * 70)
    print(f"{'Gate':<30} {'Reject%':>10} {'Pass%':>10} {'Avg P&L':>10} {'Win%':>10}")
    print("-" * 70)

    for gate_key, stats in report["gates"].items():
        print(
            f"{stats['name']:<30} "
            f"{stats['rejection_rate']:>9.1f}% "
            f"{stats['pass_rate']:>9.1f}% "
            f"${stats['avg_pnl']:>8.2f} "
            f"{stats['win_rate']:>9.1f}%"
        )

    print("-" * 70)
    print()

    if report.get("recommendations"):
        print("RECOMMENDATIONS")
        print("-" * 70)
        for rec in report["recommendations"]:
            print(f"  [{rec['gate']}]")
            print(f"    Issue: {rec['issue']}")
            print(f"    Action: {rec['action']}")
            print()

    if report.get("ablation_analysis"):
        print("ABLATION ANALYSIS (What-If Scenarios)")
        print("-" * 70)
        for scenario, data in report["ablation_analysis"].items():
            print(f"  {scenario}: {data}")
        print()


def main() -> None:
    args = parse_args()

    telemetry_path = Path(args.telemetry)
    entries = load_telemetry(telemetry_path)

    if not entries:
        print(f"No telemetry data found at {telemetry_path}")
        print("Run some trades first to generate telemetry data.")
        sys.exit(0)

    gates = analyze_gate_attribution(entries)

    ablation = None
    if args.ablation:
        ablation = run_ablation_analysis(entries, gates)

    report = generate_report(gates, ablation)

    # Save to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human_readable(report)
        print(f"\nFull report saved to: {output_path}")


if __name__ == "__main__":
    main()
