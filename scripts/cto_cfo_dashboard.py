#!/usr/bin/env python3
"""
CTO/CFO Executive Dashboard

Real-time performance monitoring and decision support.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.daily_summary import get_today_summary
from scripts.state_manager import StateManager


def analyze_performance():
    """CFO Analysis: Deep dive into performance metrics."""
    state = StateManager()
    data = state.state

    print("\n" + "=" * 80)
    print("💰 CFO PERFORMANCE ANALYSIS")
    print("=" * 80)

    account = data.get("account", {})
    performance = data.get("performance", {})

    # Financial metrics
    starting = account.get("starting_balance", 100000)
    current = account.get("current_equity", starting)
    total_pl = account.get("total_pl", 0)
    total_pl_pct = account.get("total_pl_pct", 0)

    print("\n📊 FINANCIAL POSITION")
    print(f"  Starting Capital:    ${starting:,.2f}")
    print(f"  Current Equity:      ${current:,.2f}")
    print(f"  Total P/L:           ${total_pl:+,.2f} ({total_pl_pct:+.4f}%)")
    print(f"  Cash Available:       ${account.get('cash', 0):,.2f}")
    print(f"  Positions Value:     ${account.get('positions_value', 0):,.2f}")

    # Position analysis
    positions = performance.get("open_positions", [])
    if positions:
        print("\n📦 POSITION ANALYSIS")
        total_unrealized = sum(p.get("unrealized_pl", 0) for p in positions)

        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            unrealized = pos.get("unrealized_pl", 0)
            unrealized_pct = pos.get("unrealized_pl_pct", 0)
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("current_price", 0)

            status = "🟢 PROFITABLE" if unrealized > 0 else "🔴 LOSING"
            print(f"\n  {symbol}: {status}")
            print(f"    Entry: ${entry_price:.2f} → Current: ${current_price:.2f}")
            print(f"    Unrealized P/L: ${unrealized:+,.2f} ({unrealized_pct:+.2f}%)")

            # Risk assessment
            if unrealized_pct < -2:
                print("    ⚠️  RISK: Loss exceeds 2% - consider stop-loss")
            if unrealized_pct < -5:
                print("    🚨 CRITICAL: Loss exceeds 5% - immediate review needed")

        print(f"\n  Total Unrealized P/L: ${total_unrealized:+,.2f}")

    # Performance metrics
    print("\n📈 TRADING METRICS")
    print(f"  Total Trades:        {performance.get('total_trades', 0)}")
    print(f"  Win Rate:            {performance.get('win_rate', 0):.1f}%")

    best = performance.get("best_trade", {})
    worst = performance.get("worst_trade", {})
    print(f"  Best Trade:          {best.get('symbol', 'N/A')} ${best.get('pl', 0):+,.2f}")
    print(f"  Worst Trade:         {worst.get('symbol', 'N/A')} ${worst.get('pl', 0):+,.2f}")

    # Strategy allocation
    strategies = data.get("strategies", {})
    print("\n🎯 STRATEGY ALLOCATION")
    for tier, config in strategies.items():
        if isinstance(config, dict) and "name" in config:
            invested = config.get("total_invested", 0)
            trades = config.get("trades_executed", 0)
            print(f"  {config.get('name', tier)}: ${invested:,.2f} ({trades} trades)")

    return {
        "total_pl": total_pl,
        "total_pl_pct": total_pl_pct,
        "positions": positions,
        "performance": performance,
    }


def technical_analysis():
    """CTO Analysis: System health and technical metrics."""
    print("\n" + "=" * 80)
    print("🔧 CTO TECHNICAL ANALYSIS")
    print("=" * 80)

    state = StateManager()
    data = state.state

    # Automation status
    automation = data.get("automation", {})
    print("\n🤖 AUTOMATION STATUS")
    print(
        f"  GitHub Actions:      {'✅ ENABLED' if automation.get('github_actions_enabled') else '❌ DISABLED'}"
    )
    print(f"  Workflow Status:     {automation.get('workflow_status', 'UNKNOWN')}")
    print(f"  Last Execution:      {automation.get('last_successful_execution', 'NEVER')}")
    print(f"  Execution Count:     {automation.get('execution_count', 0)}")
    print(f"  Failures:            {automation.get('failures', 0)}")

    # Challenge status
    challenge = data.get("challenge", {})
    print("\n📅 CHALLENGE STATUS")
    print(
        f"  Day:                 {challenge.get('current_day', 0)}/{challenge.get('total_days', 90)}"
    )
    print(f"  Phase:               {challenge.get('phase', 'Unknown')}")
    print(f"  Status:              {challenge.get('status', 'Unknown')}")

    # System health
    print("\n💚 SYSTEM HEALTH")
    today = datetime.now().strftime("%Y-%m-%d")
    last_update = data.get("meta", {}).get("last_updated", "")

    if last_update.startswith(today):
        print("  Status:              ✅ UP TO DATE")
    else:
        print("  Status:              ⚠️  STALE DATA")
        print(f"  Last Update:          {last_update}")

    # Learned patterns
    heuristics = data.get("heuristics", {})
    patterns = heuristics.get("learned_patterns", [])
    if patterns:
        print("\n🧠 KEY LEARNINGS")
        for pattern in patterns[-5:]:  # Last 5 patterns
            print(f"  • {pattern}")

    return {
        "automation": automation,
        "challenge": challenge,
        "health": "healthy" if last_update.startswith(today) else "stale",
    }


def generate_recommendations(perf_data, tech_data):
    """Generate CTO/CFO recommendations."""
    print("\n" + "=" * 80)
    print("💡 EXECUTIVE RECOMMENDATIONS")
    print("=" * 80)

    recommendations = []

    # CFO Recommendations
    total_pl = perf_data.get("total_pl", 0)
    positions = perf_data.get("positions", [])

    if total_pl < -20:
        recommendations.append(
            {
                "priority": "HIGH",
                "category": "CFO",
                "action": "Implement stop-loss on losing positions",
                "reason": f"Total P/L is ${total_pl:.2f} - need risk management",
            }
        )

    losing_positions = [p for p in positions if p.get("unrealized_pl", 0) < -10]
    if losing_positions:
        for pos in losing_positions:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "CFO",
                    "action": f"Review {pos.get('symbol')} position (${pos.get('unrealized_pl', 0):.2f} loss)",
                    "reason": f"Position down {pos.get('unrealized_pl_pct', 0):.2f}%",
                }
            )

    # CTO Recommendations
    automation = tech_data.get("automation", {})
    if not automation.get("github_actions_enabled"):
        recommendations.append(
            {
                "priority": "CRITICAL",
                "category": "CTO",
                "action": "Enable GitHub Actions automation",
                "reason": "No automated trading execution",
            }
        )

    if tech_data.get("health") == "stale":
        recommendations.append(
            {
                "priority": "HIGH",
                "category": "CTO",
                "action": "Investigate why system state is stale",
                "reason": "Data not updating - automation may be broken",
            }
        )

    # Display recommendations
    if recommendations:
        for _i, rec in enumerate(recommendations, 1):
            priority_emoji = (
                "🚨" if rec["priority"] == "CRITICAL" else "⚠️" if rec["priority"] == "HIGH" else "ℹ️"
            )
            print(f"\n{priority_emoji} [{rec['priority']}] {rec['category']}")
            print(f"   Action: {rec['action']}")
            print(f"   Reason: {rec['reason']}")
    else:
        print("\n✅ No critical issues - system operating normally")

    return recommendations


def main():
    """Main dashboard execution."""
    print("=" * 80)
    print("🎯 CTO/CFO EXECUTIVE DASHBOARD")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Daily summary
    get_today_summary()

    # Deep analysis
    perf_data = analyze_performance()
    tech_data = technical_analysis()

    # Recommendations
    recommendations = generate_recommendations(perf_data, tech_data)

    print("\n" + "=" * 80)
    print("✅ Dashboard Complete")
    print("=" * 80)

    return {
        "performance": perf_data,
        "technical": tech_data,
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    main()
