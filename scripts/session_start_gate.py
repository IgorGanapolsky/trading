#!/usr/bin/env python3
"""
Session Start Gate - MANDATORY verification before any AI session work.

This script MUST be run at the start of every AI session to:
1. Query RAG for relevant lessons learned
2. Check documentation freshness
3. Verify system state
4. Load recent performance data

Prevents: LL_035 (Failed to use RAG), LL_044 (Stale docs)

Usage:
    python3 scripts/session_start_gate.py
    python3 scripts/session_start_gate.py --topic "options allocation"

Created: Dec 15, 2025
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_rag_lessons(topic: str = "trading strategy performance") -> list:
    """Query RAG for relevant lessons."""
    try:
        result = subprocess.run(
            ["python3", "scripts/mandatory_rag_check.py", topic],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        return result.stdout
    except Exception as e:
        return f"RAG check failed: {e}"


def check_doc_freshness() -> dict:
    """Check documentation freshness."""
    try:
        result = subprocess.run(
            ["python3", "scripts/check_doc_freshness.py"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=30,
        )
        return {
            "passed": result.returncode == 0,
            "output": result.stdout,
        }
    except Exception as e:
        return {"passed": False, "output": str(e)}


def load_system_state() -> dict:
    """Load current system state."""
    state_file = PROJECT_ROOT / "data" / "system_state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def load_recent_performance() -> dict:
    """Load recent trading performance."""
    state = load_system_state()
    
    # Extract key metrics
    account = state.get("account", {})
    performance = state.get("performance", {})
    strategies = state.get("strategies", {})
    
    # Calculate strategy P/L
    closed_trades = performance.get("closed_trades", [])
    strategy_pl = {}
    
    for trade in closed_trades:
        symbol = trade.get("symbol", "")
        pl = trade.get("pl", 0)

        # Categorize
        if "P0" in symbol or "C0" in symbol:
            cat = "OPTIONS"
        else:
            cat = "EQUITIES"

        if cat not in strategy_pl:
            strategy_pl[cat] = {"pl": 0, "trades": 0, "wins": 0}
        strategy_pl[cat]["pl"] += pl
        strategy_pl[cat]["trades"] += 1
        if pl > 0:
            strategy_pl[cat]["wins"] += 1
    
    return {
        "equity": account.get("current_equity", 0),
        "total_pl": account.get("total_pl", 0),
        "day": state.get("challenge", {}).get("current_day", 0),
        "strategy_pl": strategy_pl,
        "active_strategies": {k: v.get("status") for k, v in strategies.items()},
    }


def main():
    parser = argparse.ArgumentParser(description="Session Start Gate")
    parser.add_argument("--topic", type=str, default="trading performance strategy", 
                        help="Topic to query RAG for")
    args = parser.parse_args()
    
    print("=" * 70)
    print("🚀 SESSION START GATE - Mandatory Pre-Session Verification")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    issues = []
    
    # 1. Load and display system state
    print("\n📊 CURRENT SYSTEM STATE:")
    print("-" * 70)
    perf = load_recent_performance()
    print(f"   Day: {perf['day']}/90")
    print(f"   Equity: ${perf['equity']:,.2f}")
    print(f"   Total P/L: ${perf['total_pl']:,.2f}")
    
    print("\n   Strategy Performance:")
    for strategy, data in perf.get("strategy_pl", {}).items():
        wins = data.get("wins", 0)
        trades = data.get("trades", 0)
        wr = (wins / trades * 100) if trades > 0 else 0
        print(f"   - {strategy}: ${data['pl']:.2f} ({wr:.0f}% win rate, {trades} trades)")
    
    print("\n   Active Strategies:")
    for strategy, status in perf.get("active_strategies", {}).items():
        emoji = "✅" if status == "active" else "❌" if status == "disabled" else "⏳"
        print(f"   - {strategy}: {emoji} {status}")
    
    # 2. Check documentation freshness
    print("\n📋 DOCUMENTATION FRESHNESS:")
    print("-" * 70)
    doc_check = check_doc_freshness()
    if doc_check["passed"]:
        print("   ✅ All critical documentation is current")
    else:
        print("   ❌ Documentation is stale!")
        issues.append("Stale documentation - update before proceeding")
        print(doc_check["output"])
    
    # 3. Query RAG for relevant lessons
    print("\n🧠 RELEVANT LESSONS LEARNED:")
    print("-" * 70)
    rag_output = check_rag_lessons(args.topic)
    print(rag_output[:2000])  # Truncate if too long
    
    # 4. Summary
    print("\n" + "=" * 70)
    if issues:
        print("❌ SESSION START GATE: ISSUES FOUND")
        for issue in issues:
            print(f"   • {issue}")
        print("\nFix issues before proceeding with session work.")
        return 1
    else:
        print("✅ SESSION START GATE: PASSED")
        print("\nYou may proceed with session work.")
        print("\nRemember to:")
        print("   1. Read relevant lessons above before making changes")
        print("   2. Update docs with any code changes (same commit)")
        print("   3. Query RAG before strategic decisions")
        return 0


if __name__ == "__main__":
    sys.exit(main())
