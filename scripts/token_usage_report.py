#!/usr/bin/env python3
"""
Token Usage Report Script

View LLM token consumption metrics for the trading system.
Helps identify context growth issues and optimization opportunities.

Usage:
    python3 scripts/token_usage_report.py          # Summary
    python3 scripts/token_usage_report.py --json   # JSON output
    python3 scripts/token_usage_report.py --save   # Save detailed report
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.token_monitor import get_token_monitor


def main():
    parser = argparse.ArgumentParser(description="View LLM token usage metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--save", action="store_true", help="Save detailed report")
    parser.add_argument(
        "--agent", type=str, help="Filter by agent name", default=None
    )
    args = parser.parse_args()

    monitor = get_token_monitor()

    if args.agent:
        stats = monitor.get_agent_stats(args.agent)
        data = {
            "agent": args.agent,
            "total_tokens": stats.total_tokens,
            "call_count": stats.call_count,
            "avg_input": round(stats.avg_input_tokens),
            "avg_output": round(stats.avg_output_tokens),
            "max_input": stats.max_input_tokens,
        }
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"\n📊 Token Usage for {args.agent}")
            print("=" * 40)
            print(f"Total Tokens:  {stats.total_tokens:,}")
            print(f"Call Count:    {stats.call_count}")
            print(f"Avg Input:     {stats.avg_input_tokens:,.0f}")
            print(f"Avg Output:    {stats.avg_output_tokens:,.0f}")
            print(f"Max Input:     {stats.max_input_tokens:,}")
        return

    summary = monitor.get_summary()

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    if args.save:
        report_path = monitor.save_report()
        print(f"✅ Report saved to: {report_path}")
        return

    # Pretty print summary
    session = summary["session"]
    daily = summary["daily"]
    thresholds = summary["thresholds"]

    print("\n" + "=" * 50)
    print("📊 LLM TOKEN USAGE REPORT")
    print("=" * 50)

    print(f"\n📅 Session (started {summary['session_start'][:19]})")
    print(f"   Total Tokens:    {session['total_tokens']:,}")
    print(f"   LLM Calls:       {session['call_count']}")
    print(f"   Avg per Call:    {session['avg_tokens_per_call']:,}")

    if session["tokens_by_agent"]:
        print("\n   By Agent:")
        for agent, tokens in sorted(
            session["tokens_by_agent"].items(), key=lambda x: -x[1]
        ):
            print(f"     {agent}: {tokens:,}")

    print(f"\n📆 Daily Usage")
    print(f"   Total Tokens:    {daily['total_tokens']:,}")
    print(f"   % of Threshold:  {daily['threshold_pct']}%")

    print(f"\n⚠️  Thresholds")
    print(f"   Single Call:  {thresholds['single_call']:,}")
    print(f"   Session:      {thresholds['session']:,}")
    print(f"   Daily:        {thresholds['daily']:,}")

    if session["alerts"]:
        print("\n🚨 ALERTS:")
        for alert in session["alerts"]:
            print(f"   - {alert}")

    print("\n💡 Recommendations:")
    for rec in summary["recommendations"]:
        print(f"   - {rec}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
