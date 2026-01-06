#!/usr/bin/env python3
"""Weekly Budget Burn Report - Track API spending against $100/month target.

Implements:
1. Weekly budget burn rate analysis
2. Projected month-end spending
3. Cost-per-trade metrics for LLM operations
4. Recommendations for budget optimization

Part of operational security improvements (Jan 2026).
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
MONTHLY_BUDGET = 100.00
BUDGET_FILE = Path("data/budget_tracker.json")
PERFORMANCE_FILE = Path("data/performance_log.json")
SYSTEM_STATE_FILE = Path("data/system_state.json")


def load_budget_data() -> dict[str, Any]:
    """Load budget tracking data."""
    if not BUDGET_FILE.exists():
        return {
            "monthly_budget": MONTHLY_BUDGET,
            "spent_this_month": 0.0,
            "current_month": datetime.now().strftime("%Y-%m"),
            "api_calls": {},
            "daily_spending": {},
            "last_updated": datetime.now().isoformat(),
        }
    try:
        return json.loads(BUDGET_FILE.read_text())
    except json.JSONDecodeError:
        logger.warning("Could not parse budget file, using defaults")
        return {"spent_this_month": 0.0, "daily_spending": {}, "api_calls": {}}


def load_trade_count() -> int:
    """Count total trades executed (for cost-per-trade calculation)."""
    trade_count = 0
    trades_dir = Path("data")

    for trade_file in trades_dir.glob("trades_*.json"):
        try:
            trades = json.loads(trade_file.read_text())
            if isinstance(trades, list):
                trade_count += len(trades)
            else:
                trade_count += 1
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    return trade_count


def analyze_weekly_burn(budget_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze the last 7 days of spending."""
    daily_spending = budget_data.get("daily_spending", {})
    today = datetime.now().date()

    # Get last 7 days of spending
    weekly_spend = 0.0
    days_with_data = 0

    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if date_str in daily_spending:
            weekly_spend += daily_spending[date_str]
            days_with_data += 1

    # Calculate daily average (only from days with data)
    daily_avg = weekly_spend / max(days_with_data, 1)

    # Project to month end
    days_remaining = 32 - today.day  # Approximate days left
    projected_additional = daily_avg * days_remaining
    spent_so_far = budget_data.get("spent_this_month", 0.0)
    projected_total = spent_so_far + projected_additional

    return {
        "weekly_spend": weekly_spend,
        "daily_average": daily_avg,
        "days_with_data": days_with_data,
        "spent_this_month": spent_so_far,
        "projected_total": projected_total,
        "budget_remaining": MONTHLY_BUDGET - spent_so_far,
        "days_remaining": days_remaining,
        "on_track": projected_total <= MONTHLY_BUDGET,
        "overage": max(0, projected_total - MONTHLY_BUDGET),
    }


def analyze_api_costs(budget_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze cost breakdown by API."""
    api_calls = budget_data.get("api_calls", {})
    spent = budget_data.get("spent_this_month", 0.0)

    # API cost per call (from budget_tracker.py)
    api_costs = {
        "alpaca_trade": 0.00,
        "alpaca_data": 0.001,
        "openrouter_haiku": 0.0003,
        "openrouter_sonnet": 0.003,
        "openrouter_opus": 0.015,
        "gemini_research": 0.01,
        "polygon_data": 0.0001,
        "yfinance": 0.00,
        "news_api": 0.001,
    }

    # Calculate per-API spending
    api_breakdown = {}
    total_calls = 0

    for api_name, count in api_calls.items():
        cost_per = api_costs.get(api_name, 0.001)
        api_spent = count * cost_per
        api_breakdown[api_name] = {
            "calls": count,
            "cost_per_call": cost_per,
            "total_spent": api_spent,
        }
        total_calls += count

    # Sort by spend (highest first)
    sorted_apis = sorted(api_breakdown.items(), key=lambda x: x[1]["total_spent"], reverse=True)

    return {
        "total_calls": total_calls,
        "total_spent": spent,
        "api_breakdown": dict(sorted_apis),
        "top_spenders": [api for api, _ in sorted_apis[:3]],
    }


def calculate_cost_per_trade(budget_data: dict[str, Any], trade_count: int) -> dict[str, Any]:
    """Calculate LLM cost per trade."""
    spent = budget_data.get("spent_this_month", 0.0)
    api_calls = budget_data.get("api_calls", {})

    # LLM-specific costs
    llm_apis = ["openrouter_haiku", "openrouter_sonnet", "openrouter_opus", "gemini_research"]
    llm_costs = {
        "openrouter_haiku": 0.0003,
        "openrouter_sonnet": 0.003,
        "openrouter_opus": 0.015,
        "gemini_research": 0.01,
    }

    llm_spend = 0.0
    llm_calls = 0
    for api in llm_apis:
        count = api_calls.get(api, 0)
        llm_calls += count
        llm_spend += count * llm_costs.get(api, 0)

    cost_per_trade = llm_spend / max(trade_count, 1)
    calls_per_trade = llm_calls / max(trade_count, 1)

    return {
        "trade_count": trade_count,
        "llm_spend": llm_spend,
        "llm_calls": llm_calls,
        "cost_per_trade": cost_per_trade,
        "calls_per_trade": calls_per_trade,
        "is_efficient": cost_per_trade < 0.10,  # Target: <$0.10/trade
    }


def get_recommendations(burn_analysis: dict, api_analysis: dict, trade_analysis: dict) -> list[str]:
    """Generate optimization recommendations."""
    recommendations = []

    # Budget trajectory
    if not burn_analysis["on_track"]:
        overage = burn_analysis["overage"]
        recommendations.append(
            f"⚠️  BUDGET ALERT: Projected to exceed by ${overage:.2f}. "
            "Consider switching to Haiku model for non-critical operations."
        )

    # Check if spending too fast
    if burn_analysis["daily_average"] > (MONTHLY_BUDGET / 30):
        daily_target = MONTHLY_BUDGET / 30
        recommendations.append(
            f"Daily spending ${burn_analysis['daily_average']:.3f} exceeds "
            f"target ${daily_target:.3f}. Review high-frequency API calls."
        )

    # API-specific recommendations
    top_spenders = api_analysis.get("top_spenders", [])
    if "openrouter_opus" in top_spenders[:2]:
        recommendations.append(
            "Opus usage is high. Consider using Sonnet for medium-complexity tasks "
            "(saves 80% per call)."
        )

    # Cost per trade
    if not trade_analysis["is_efficient"]:
        cpt = trade_analysis["cost_per_trade"]
        recommendations.append(
            f"LLM cost per trade is ${cpt:.3f} (target: <$0.10). "
            "Review sentiment analysis frequency and model usage."
        )

    # If all good
    if not recommendations:
        recommendations.append("✅ Budget usage is healthy. No optimization needed.")

    return recommendations


def generate_report() -> dict[str, Any]:
    """Generate the full budget burn report."""
    budget_data = load_budget_data()
    trade_count = load_trade_count()

    burn_analysis = analyze_weekly_burn(budget_data)
    api_analysis = analyze_api_costs(budget_data)
    trade_analysis = calculate_cost_per_trade(budget_data, trade_count)
    recommendations = get_recommendations(burn_analysis, api_analysis, trade_analysis)

    return {
        "generated_at": datetime.now().isoformat(),
        "monthly_budget": MONTHLY_BUDGET,
        "burn_analysis": burn_analysis,
        "api_analysis": api_analysis,
        "trade_analysis": trade_analysis,
        "recommendations": recommendations,
        "health_status": "healthy" if burn_analysis["on_track"] else "at_risk",
    }


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted report to console."""
    print("=" * 70)
    print("📊 WEEKLY BUDGET BURN REPORT")
    print("=" * 70)
    print(f"Generated: {report['generated_at']}")
    print(f"Monthly Budget: ${report['monthly_budget']:.2f}")
    print()

    # Burn Analysis
    burn = report["burn_analysis"]
    print("📈 SPENDING ANALYSIS")
    print("-" * 70)
    print(f"  Weekly Spend:      ${burn['weekly_spend']:.4f}")
    print(f"  Daily Average:     ${burn['daily_average']:.4f}")
    print(f"  Month-to-Date:     ${burn['spent_this_month']:.4f}")
    print(f"  Remaining Budget:  ${burn['budget_remaining']:.2f}")
    print(f"  Days Remaining:    {burn['days_remaining']}")
    print(f"  Projected Total:   ${burn['projected_total']:.2f}")
    print(f"  Status:            {'✅ ON TRACK' if burn['on_track'] else '⚠️  OVER BUDGET'}")
    print()

    # Trade Analysis
    trade = report["trade_analysis"]
    print("💰 COST PER TRADE (LLM Only)")
    print("-" * 70)
    print(f"  Total Trades:      {trade['trade_count']}")
    print(f"  LLM Calls:         {trade['llm_calls']}")
    print(f"  LLM Spend:         ${trade['llm_spend']:.4f}")
    print(f"  Cost/Trade:        ${trade['cost_per_trade']:.4f}")
    print(f"  Calls/Trade:       {trade['calls_per_trade']:.1f}")
    print(f"  Efficiency:        {'✅ EFFICIENT' if trade['is_efficient'] else '⚠️  HIGH'}")
    print()

    # API Breakdown
    api = report["api_analysis"]
    print("🔌 API USAGE BREAKDOWN")
    print("-" * 70)
    for api_name, data in list(api["api_breakdown"].items())[:5]:
        if data["calls"] > 0:
            print(f"  {api_name:25} {data['calls']:5} calls  ${data['total_spent']:.4f}")
    print()

    # Recommendations
    print("💡 RECOMMENDATIONS")
    print("-" * 70)
    for rec in report["recommendations"]:
        print(f"  • {rec}")
    print()

    print("=" * 70)
    print(f"Health Status: {report['health_status'].upper()}")
    print("=" * 70)


def main():
    """Generate and display the budget burn report."""
    report = generate_report()
    print_report(report)

    # Save report to file
    report_file = Path("data/budget_burn_report.json")
    report_file.write_text(json.dumps(report, indent=2))
    logger.info(f"Report saved to {report_file}")

    # Return exit code based on health
    return 0 if report["health_status"] == "healthy" else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
