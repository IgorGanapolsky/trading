#!/usr/bin/env python3
"""
Evaluation Summary - Quick visibility into evaluation results

Shows recent evaluations, detected issues, and patterns.
FREE - No API costs, local processing only.
"""

import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.trading_evaluator import TradingSystemEvaluator


def main():
    """Show evaluation summary."""
    evaluator = TradingSystemEvaluator()

    # Get summary for last 7 days
    summary = evaluator.get_evaluation_summary(days=7)

    print("=" * 70)
    print("EVALUATION SUMMARY - Last 7 Days")
    print("=" * 70)
    print()

    print("📊 OVERVIEW:")
    print(f"   Total Evaluations: {summary['total_evaluations']}")
    print(f"   Passed: {summary['passed']} ✅")
    print(f"   Failed: {summary['failed']} ❌")
    print(f"   Avg Score: {summary['avg_score']:.2f}")
    print()

    if summary["critical_issues"]:
        print(f"🚨 CRITICAL ISSUES ({len(summary['critical_issues'])}):")
        # Count unique issues
        issue_counts = defaultdict(int)
        for issue in summary["critical_issues"]:
            issue_counts[issue] += 1

        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   [{count}x] {issue}")
        print()

    if summary["error_patterns"]:
        print("🔍 ERROR PATTERNS DETECTED:")
        for pattern_num, count in sorted(summary["error_patterns"].items()):
            pattern_names = {
                "1": "Order size >10x expected",
                "2": "System state stale",
                "3": "Network/DNS errors",
                "4": "Wrong script executed",
                "5": "Weekend trade",
            }
            name = pattern_names.get(pattern_num, f"Pattern #{pattern_num}")
            print(f"   Pattern #{pattern_num}: {name} - {count} occurrence(s)")
        print()

    if summary["total_evaluations"] == 0:
        print("ℹ️  No evaluations found in last 7 days")
        print("   Evaluations are created automatically after each trade")
        print()

    print("=" * 70)
    print("💡 TIP: Run this after each trading day to see detected issues")
    print("=" * 70)


if __name__ == "__main__":
    main()
