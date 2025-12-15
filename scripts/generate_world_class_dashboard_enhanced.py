#!/usr/bin/env python3
"""
Generate World-Class Trading Dashboard (Enhanced Version)

Implements ALL missing features from the critique:
✅ Risk Metrics (Max drawdown, Sharpe, Sortino, VaR, Conditional VaR, Kelly fraction)
✅ Performance Attribution (by symbol, strategy, time-of-day)
✅ Visualizations (equity curve, drawdown, P/L charts)
✅ Real-Time Insights (AI-generated commentary)
✅ Predictive Analytics (Monte Carlo, risk-of-ruin)
✅ Execution Metrics (slippage, fill quality, latency)
✅ Data Completeness Metrics
✅ Benchmark Comparisons (vs S&P 500)
✅ AI Interpretation Layer
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.ai_insights_generator import AIInsightsGenerator
from scripts.dashboard_charts import generate_all_charts
from scripts.enhanced_dashboard_metrics import EnhancedMetricsCalculator, load_json_file

try:
    from src.utils.tax_optimization import TaxOptimizer
except ImportError:
    TaxOptimizer = None

DATA_DIR = Path("data")


def calculate_basic_metrics():
    """Calculate basic metrics for dashboard header."""
    challenge_file = DATA_DIR / "challenge_start.json"
    if challenge_file.exists():
        challenge_data = load_json_file(challenge_file)
        start_date = datetime.fromisoformat(challenge_data["start_date"]).date()
        today = date.today()
        days_elapsed = (today - start_date).days + 1
        starting_balance = challenge_data.get("starting_balance", 100000.0)
    else:
        system_state = load_json_file(DATA_DIR / "system_state.json")
        challenge = system_state.get("challenge", {})
        start_date_str = challenge.get("start_date", "2025-10-29")
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            today = date.today()
            days_elapsed = max((today - start_date).days + 1, 1)
        except Exception:
            days_elapsed = max(system_state.get("challenge", {}).get("current_day", 1), 1)
        starting_balance = 100000.0

    system_state = load_json_file(DATA_DIR / "system_state.json")
    account = system_state.get("account", {})
    current_equity = account.get("current_equity", starting_balance)
    total_pl = account.get("total_pl", 0.0)
    total_pl_pct = account.get("total_pl_pct", 0.0)

    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if isinstance(perf_log, list) and perf_log:
        latest_perf = perf_log[-1]
        current_equity = latest_perf.get("equity", current_equity)
        total_pl = latest_perf.get("pl", total_pl)
        total_pl_pct = latest_perf.get("pl_pct", total_pl_pct) * 100

    trading_days = len(perf_log) if isinstance(perf_log, list) and perf_log else days_elapsed
    trading_days = max(trading_days, 1)

    avg_daily_profit = total_pl / trading_days if trading_days > 0 else 0.0
    north_star_target = 100.0
    progress_pct = (avg_daily_profit / north_star_target * 100) if north_star_target > 0 else 0.0

    if total_pl > 0 and progress_pct < 0.01:
        progress_pct = max(0.01, (total_pl / north_star_target) * 100)

    performance = system_state.get("performance", {})
    win_rate = performance.get("win_rate", 0.0) * 100
    total_trades = performance.get("total_trades", 0)

    challenge = system_state.get("challenge", {})
    current_day = challenge.get("current_day", days_elapsed)
    total_days = challenge.get("total_days", 90)
    phase = challenge.get("phase", "R&D Phase - Month 1 (Days 1-30)")

    automation = system_state.get("automation", {})
    automation_status = automation.get("workflow_status", "UNKNOWN")

    today_trades_file = DATA_DIR / f"trades_{date.today().isoformat()}.json"
    today_trades = load_json_file(today_trades_file)
    today_trade_count = len(today_trades) if isinstance(today_trades, list) else 0

    # Calculate today's performance metrics
    today_str = date.today().isoformat()
    today_perf = None
    today_equity = current_equity
    today_pl = 0.0
    today_pl_pct = 0.0

    if isinstance(perf_log, list) and perf_log:
        # Find today's entry in performance log
        for entry in reversed(perf_log):
            if entry.get("date") == today_str:
                today_perf = entry
                today_equity = entry.get("equity", current_equity)
                today_pl = entry.get("pl", 0.0)
                today_pl_pct = entry.get("pl_pct", 0.0) * 100  # Convert to percentage
                break

        # If no entry for today, calculate from yesterday
        if today_perf is None and len(perf_log) > 0:
            yesterday_perf = perf_log[-1]
            yesterday_equity = yesterday_perf.get("equity", starting_balance)
            today_equity = current_equity
            today_pl = current_equity - yesterday_equity
            today_pl_pct = ((today_pl / yesterday_equity) * 100) if yesterday_equity > 0 else 0.0

    days_remaining = total_days - current_day
    progress_pct_challenge = (current_day / total_days * 100) if total_days > 0 else 0.0

    return {
        "days_elapsed": days_elapsed,
        "current_day": current_day,
        "total_days": total_days,
        "days_remaining": days_remaining,
        "progress_pct_challenge": progress_pct_challenge,
        "phase": phase,
        "starting_balance": starting_balance,
        "current_equity": current_equity,
        "total_pl": total_pl,
        "total_pl_pct": total_pl_pct,
        "avg_daily_profit": avg_daily_profit,
        "north_star_target": north_star_target,
        "progress_pct": progress_pct,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "automation_status": automation_status,
        "today_trade_count": today_trade_count,
        "today_equity": today_equity,
        "today_pl": today_pl,
        "today_pl_pct": today_pl_pct,
        "today_perf_available": today_perf is not None,
    }


def get_recent_trades(days: int = 7) -> list[dict]:
    """Get trades from the last N days."""
    from datetime import timedelta

    recent_trades = []
    today = date.today()

    for i in range(days):
        trade_date = today - timedelta(days=i)
        trades_file = DATA_DIR / f"trades_{trade_date.isoformat()}.json"
        if trades_file.exists():
            day_trades = load_json_file(trades_file)
            if isinstance(day_trades, list):
                for trade in day_trades:
                    trade["trade_date"] = trade_date.isoformat()
                    recent_trades.append(trade)

    # Sort by timestamp descending (most recent first)
    recent_trades.sort(key=lambda x: x.get("timestamp", x.get("trade_date", "")), reverse=True)
    return recent_trades


def generate_world_class_dashboard() -> str:
    """Generate complete world-class dashboard."""
    # Calculate all metrics
    basic_metrics = calculate_basic_metrics()
    calculator = EnhancedMetricsCalculator(DATA_DIR)
    all_metrics = calculator.calculate_all_metrics()

    # Load profit target data (best-effort, graceful fallback)
    profit_target_data = {}
    profit_target_file = Path("reports/profit_target_report.json")
    if profit_target_file.exists():
        try:
            profit_target_data = load_json_file(profit_target_file)
        except Exception:
            pass  # Fall back to empty dict if file can't be loaded

    # Load data for charts and insights
    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if not isinstance(perf_log, list):
        perf_log = []

    all_trades = calculator._load_all_trades()

    # Count orders from today's trades file (not telemetry)
    order_count = 0
    stop_count = 0
    today_trades_for_funnel = load_json_file(DATA_DIR / f"trades_{date.today().isoformat()}.json")
    if isinstance(today_trades_for_funnel, list):
        for trade in today_trades_for_funnel:
            # Count all orders (BUY/SELL)
            order_count += 1
            # Count stop orders if they have stop_price or are stop type
            if trade.get("stop_price") or trade.get("order_type", "").lower() == "stop":
                stop_count += 1

    # Calculate tax optimization metrics
    tax_metrics = {}
    tax_recommendations = []
    pdt_status = {}
    system_state = load_json_file(DATA_DIR / "system_state.json")
    current_equity = basic_metrics.get("current_equity", 100000.0)

    if TaxOptimizer and all_trades:
        try:
            tax_optimizer = TaxOptimizer()

            # Process trades for tax tracking
            from datetime import datetime as dt

            for trade in all_trades:
                if (
                    trade.get("entry_date")
                    and trade.get("exit_date")
                    and trade.get("pl") is not None
                ):
                    try:
                        entry_date = dt.fromisoformat(trade["entry_date"].replace("Z", "+00:00"))
                        exit_date = dt.fromisoformat(trade["exit_date"].replace("Z", "+00:00"))
                        entry_price = trade.get("entry_price", 0.0)
                        exit_price = trade.get("exit_price", 0.0)
                        quantity = trade.get("quantity", 0.0)
                        trade_id = trade.get(
                            "trade_id",
                            f"{trade.get('symbol', 'UNKNOWN')}_{entry_date.isoformat()}",
                        )

                        # Record entry
                        tax_optimizer.record_trade_entry(
                            trade.get("symbol", "UNKNOWN"),
                            quantity,
                            entry_price,
                            entry_date,
                            trade_id,
                        )

                        # Record exit
                        tax_optimizer.record_trade_exit(
                            trade.get("symbol", "UNKNOWN"),
                            quantity,
                            exit_price,
                            exit_date,
                            trade_id,
                        )
                    except Exception:
                        pass  # Skip trades that can't be processed

            # Get tax summary
            tax_metrics = tax_optimizer.get_tax_summary()

            # Check PDT status
            pdt_status = tax_optimizer.check_pdt_status(current_equity)

            # Get recommendations
            open_positions = system_state.get("performance", {}).get("open_positions", [])
            tax_recommendations = tax_optimizer.get_tax_optimization_recommendations(
                current_equity, open_positions
            )
        except Exception:
            tax_metrics = {
                "total_trades": 0,
                "estimated_tax": 0.0,
                "after_tax_return": 0.0,
                "day_trade_count": 0,
            }
            pdt_status = {"status": "⚠️ Unable to calculate", "warnings": []}
    else:
        tax_metrics = {
            "total_trades": 0,
            "estimated_tax": 0.0,
            "after_tax_return": basic_metrics.get("total_pl", 0.0),
            "day_trade_count": 0,
        }
        pdt_status = {"status": "⚠️ No closed trades yet", "warnings": []}

    # Generate charts
    chart_paths = generate_all_charts(perf_log)

    # Generate AI insights
    insights_generator = AIInsightsGenerator()
    ai_insights = insights_generator.generate_daily_insights(
        perf_log,
        all_trades,
        all_metrics.get("risk_metrics", {}),
        all_metrics.get("performance_metrics", {}),
        all_metrics.get("performance_attribution", {}),
    )

    # Extract metrics
    risk = all_metrics.get("risk_metrics", {})
    all_metrics.get("performance_metrics", {})
    enhanced_risk = all_metrics.get("enhanced_risk_metrics", {})
    attribution = all_metrics.get("performance_attribution", {})
    execution = all_metrics.get("execution_metrics", {})
    data_completeness = all_metrics.get("data_completeness", {})
    predictive = all_metrics.get("predictive_analytics", {})
    benchmark = all_metrics.get("benchmark_comparison", {})
    time_analysis = all_metrics.get("time_of_day_analysis", {})
    regime = all_metrics.get("market_regime_classification", {})

    now = datetime.now()

    # Progress bars
    progress_bars = int(basic_metrics["progress_pct_challenge"] / 5)
    progress_bar = "█" * progress_bars + "░" * (20 - progress_bars)

    if basic_metrics["total_pl"] > 0 and basic_metrics["progress_pct"] < 5.0:
        north_star_bars = 1
    else:
        north_star_bars = min(int(basic_metrics["progress_pct"] / 5), 20)
    north_star_bar = "█" * north_star_bars + "░" * (20 - north_star_bars)

    display_progress_pct = (
        max(basic_metrics["progress_pct"], 0.01)
        if basic_metrics["total_pl"] > 0
        else basic_metrics["progress_pct"]
    )

    status_emoji = "✅" if basic_metrics["total_pl"] > 0 else "⚠️"

    # Get today's date string for display
    today_display = date.today().strftime("%Y-%m-%d (%A)")

    # Generate recent trades section
    recent_trades = get_recent_trades(days=7)
    if recent_trades:
        recent_trades_rows = []
        for trade in recent_trades[:15]:  # Limit to 15 most recent
            trade_date = trade.get("trade_date", "")
            symbol = trade.get("symbol", "UNKNOWN")
            side = trade.get("side", trade.get("action", "BUY")).upper()
            qty = trade.get("qty", trade.get("quantity", trade.get("notional", 0)))
            price = trade.get("filled_avg_price", trade.get("price", 0))
            status = trade.get("status", "FILLED").upper()

            # Format quantity (could be shares or notional)
            if isinstance(qty, (int, float)) and qty < 1:
                qty_display = f"{qty:.6f}"
            elif isinstance(qty, (int, float)):
                qty_display = f"${qty:,.2f}" if trade.get("notional") else f"{qty}"
            else:
                qty_display = str(qty)

            # Format price
            if isinstance(price, (int, float)) and price > 0:
                price_display = f"${price:,.2f}"
            else:
                price_display = "Market"

            status_icon = (
                "✅"
                if status in ["FILLED", "COMPLETED", "SUCCESS"]
                else "⏳"
                if status == "PENDING"
                else "❌"
            )
            recent_trades_rows.append(
                f"| {trade_date} | **{symbol}** | {side} | {qty_display} | {price_display} | {status_icon} {status} |"
            )

        recent_trades_section = """| Date | Symbol | Action | Qty/Amount | Price | Status |
|------|--------|--------|------------|-------|--------|
""" + "\n".join(recent_trades_rows)
    else:
        recent_trades_section = "*No trades in the last 7 days*"

    # Build dashboard
    dashboard = f"""# 📊 World-Class Trading Dashboard

**Last Updated**: {now.strftime("%Y-%m-%d %I:%M %p ET")}
**Auto-Updated**: Daily via GitHub Actions
**Dashboard Version**: Enhanced World-Class (v2.0)

---

## 📅 Today's Performance

**Date**: {today_display}

| Metric | Value |
|--------|-------|
| **Equity** | ${basic_metrics.get("today_equity", basic_metrics["current_equity"]):,.2f} |
| **P/L** | ${basic_metrics.get("today_pl", 0):+,.2f} ({basic_metrics.get("today_pl_pct", 0):+.2f}%) |
| **Trades Today** | {basic_metrics.get("today_trade_count", 0)} |
| **Status** | {"✅ Active" if basic_metrics.get("today_trade_count", 0) > 0 or abs(basic_metrics.get("today_pl", 0)) > 0.01 else "⏸️ No activity yet"} |

**Funnel Activity**: {order_count} orders, {stop_count} stops

---

## 📈 Recent Trades (Last 7 Days)

{recent_trades_section}

---

## 🎯 North Star Goal

**Target**: **$100+/day profit**

| Metric | Current | Target | Progress |
|--------|---------|--------|----------|
| **Average Daily Profit** | ${basic_metrics["avg_daily_profit"]:.2f}/day | $100.00/day | {display_progress_pct:.2f}% |
| **Total P/L** | ${basic_metrics["total_pl"]:+,.2f} ({basic_metrics["total_pl_pct"]:+.2f}%) | TBD | {status_emoji} |
| **Win Rate** | {basic_metrics["win_rate"]:.1f}% | >55% | {"✅" if basic_metrics["win_rate"] >= 55 else "⚠️"} |

**Progress Bar**: `{north_star_bar}` ({display_progress_pct:.2f}%)

**Assessment**: {"✅ **ON TRACK**" if basic_metrics["total_pl"] > 0 and basic_metrics["win_rate"] >= 55 else "⚠️ **R&D PHASE** - Learning, not earning yet"}

---

## 💡 $100/Day Progress & Capital Scaling Plan

"""

    # Add profit target section if data is available
    if profit_target_data:
        current_profit = profit_target_data.get("current_daily_profit", 0.0)
        projected_profit = profit_target_data.get("projected_daily_profit", 0.0)
        target_profit = profit_target_data.get("target_daily_profit", 100.0)
        target_gap = profit_target_data.get("target_gap", 0.0)
        current_budget = profit_target_data.get("current_daily_budget", 0.0)
        recommended_budget = profit_target_data.get("recommended_daily_budget")
        scaling_factor = profit_target_data.get("scaling_factor")
        avg_return_pct = profit_target_data.get("avg_return_pct", 0.0)
        actions = profit_target_data.get("actions", [])
        allocations = profit_target_data.get("recommended_allocations", {})

        # Calculate progress percentage
        progress_to_target = (projected_profit / target_profit * 100) if target_profit > 0 else 0.0

        # Progress bar for $100/day target
        progress_bars_100 = max(0, min(int(progress_to_target / 5), 20))
        progress_bar_100 = "█" * progress_bars_100 + "░" * (20 - progress_bars_100)

        dashboard += f"""
| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **Actual Daily Profit** | ${current_profit:+.2f}/day | ${target_profit:.2f}/day | {"✅" if current_profit >= target_profit else "⚠️"} |
| **Projected Daily Profit** | ${projected_profit:+.2f}/day | ${target_profit:.2f}/day | {"✅" if projected_profit >= target_profit else "⚠️"} |
| **Target Gap** | ${target_gap:+.2f}/day | $0.00/day | {"✅" if target_gap <= 0 else "⚠️"} |
| **Current Daily Budget** | ${current_budget:.2f}/day | Variable | - |
| **Avg Return %** | {avg_return_pct:+.2f}% | >0% | {"✅" if avg_return_pct > 0 else "⚠️"} |

**Progress to $100/Day**: `{progress_bar_100}` ({progress_to_target:.1f}%)

### Capital Scaling Recommendations

"""

        if recommended_budget is not None:
            dashboard += f"""
| Metric | Value |
|--------|-------|
| **Recommended Daily Budget** | ${recommended_budget:,.2f}/day |
| **Scaling Factor** | {scaling_factor:.2f}x |
| **Budget Increase Needed** | ${recommended_budget - current_budget:+,.2f}/day |

"""
            # Show recommended allocations
            if allocations:
                dashboard += """
**Recommended Strategy Allocations**:

| Strategy | Allocation |
|----------|------------|
"""
                for strategy, amount in allocations.items():
                    dashboard += f"| {strategy} | ${amount:.2f}/day |\n"
                dashboard += "\n"
        else:
            dashboard += """
*Recommended budget cannot be calculated yet. Need positive average return % first.*

"""

        # Add actionable recommendations
        dashboard += """
### Actionable Recommendations

"""
        if actions:
            for action in actions:
                dashboard += f"- {action}\n"
        else:
            dashboard += "- ✅ Stay the course - current strategy is on track.\n"

        dashboard += "\n"
    else:
        # Fallback when profit target report is not available
        dashboard += """
*Profit target analysis not available. Run `python scripts/generate_profit_target_report.py` to generate detailed capital scaling recommendations.*

"""

    dashboard += """---

## 🛡️ Comprehensive Risk Metrics

### Core Risk Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Max Drawdown** | {risk.get("max_drawdown_pct", 0):.2f}% | <10% | {"✅" if risk.get("max_drawdown_pct", 0) < 10 else "⚠️"} |
| **Current Drawdown** | {risk.get("current_drawdown_pct", 0):.2f}% | <5% | {"✅" if risk.get("current_drawdown_pct", 0) < 5 else "⚠️"} |
| **Ulcer Index** | {risk.get("ulcer_index", 0):.2f} | <5.0 | {"✅" if risk.get("ulcer_index", 0) < 5.0 else "⚠️"} |
| **Sharpe Ratio** | {risk.get("sharpe_ratio", 0):.2f} | >1.0 | {"✅" if risk.get("sharpe_ratio", 0) >= 1.0 else "⚠️"} |
| **Sortino Ratio** | {risk.get("sortino_ratio", 0):.2f} | >1.5 | {"✅" if risk.get("sortino_ratio", 0) >= 1.5 else "⚠️"} |
| **Calmar Ratio** | {risk.get("calmar_ratio", 0):.2f} | >1.0 | {"✅" if risk.get("calmar_ratio", 0) >= 1.0 else "⚠️"} |
| **Volatility (Annualized)** | {risk.get("volatility_annualized", 0):.2f}% | <20% | {"✅" if risk.get("volatility_annualized", 0) < 20 else "⚠️"} |
| **VaR (95%)** | {abs(risk.get("var_95", 0)):.2f}% | <3% | {"✅" if abs(risk.get("var_95", 0)) < 3 else "⚠️"} |
| **VaR (99%)** | {abs(risk.get("var_99", 0)):.2f}% | <5% | {"✅" if abs(risk.get("var_99", 0)) < 5 else "⚠️"} |
| **CVaR (95%)** | {risk.get("cvar_95", enhanced_risk.get("conditional_var_95", 0)):.2f}% | <5% | {"✅" if risk.get("cvar_95", enhanced_risk.get("conditional_var_95", 0)) < 5 else "⚠️"} |
| **Kelly Fraction** | {enhanced_risk.get("kelly_fraction", 0):.2f}% | 5-10% | {"✅" if 5 <= enhanced_risk.get("kelly_fraction", 0) <= 10 else "⚠️"} |
| **Margin Usage** | {enhanced_risk.get("margin_usage_pct", 0):.2f}% | <50% | {"✅" if enhanced_risk.get("margin_usage_pct", 0) < 50 else "⚠️"} |
| **Leverage** | {enhanced_risk.get("leverage", 1.0):.2f}x | <2.0x | {"✅" if enhanced_risk.get("leverage", 1.0) < 2.0 else "⚠️"} |

### Risk Exposure by Symbol

| Symbol | Exposure % | P/L | Trades | Win Rate |
|--------|------------|-----|--------|----------|
"""

    # Add symbol attribution
    by_symbol = attribution.get("by_symbol", {})
    if by_symbol:
        for symbol, data in sorted(
            by_symbol.items(), key=lambda x: x[1].get("total_pl", 0), reverse=True
        )[:10]:
            dashboard += f"| {symbol} | {data.get('total_pl', 0) / basic_metrics['current_equity'] * 100:.2f}% | ${data.get('total_pl', 0):+.2f} | {data.get('trades', 0)} | {data.get('win_rate', 0):.1f}% |\n"
    else:
        dashboard += "| *No symbol data available* | - | - | - | - |\n"

    dashboard += """
---

## 📊 Performance Attribution

### By Strategy/Tier

| Strategy | P/L | Trades | Avg P/L per Trade |
|----------|-----|--------|------------------|
"""

    by_strategy = attribution.get("by_strategy", {})
    if by_strategy:
        for strategy, data in sorted(
            by_strategy.items(), key=lambda x: x[1].get("total_pl", 0), reverse=True
        ):
            dashboard += f"| {strategy} | ${data.get('total_pl', 0):+.2f} | {data.get('trades', 0)} | ${data.get('avg_pl_per_trade', 0):+.2f} |\n"
    else:
        dashboard += "| *No strategy data available* | - | - | - |\n"

    dashboard += """
### By Time of Day

| Time Period | P/L | Trades | Avg P/L per Trade |
|-------------|-----|--------|------------------|
"""

    by_time = attribution.get("by_time_of_day", {})
    if by_time:
        for time_period, data in by_time.items():
            dashboard += f"| {time_period.capitalize()} | ${data.get('total_pl', 0):+.2f} | {data.get('trades', 0)} | ${data.get('avg_pl_per_trade', 0):+.2f} |\n"
    else:
        dashboard += "| *No time-of-day data available* | - | - | - |\n"

    dashboard += f"""
**Best Trading Time**: {time_analysis.get("best_time", "N/A")}
**Worst Trading Time**: {time_analysis.get("worst_time", "N/A")}

---

## 📈 Visualizations

"""

    # Add chart images
    charts_generated = any(chart_paths.values())
    if charts_generated:
        if chart_paths.get("equity_curve"):
            dashboard += f"### Equity Curve\n\n![Equity Curve]({chart_paths['equity_curve']})\n\n"
        if chart_paths.get("drawdown"):
            dashboard += f"### Drawdown Chart\n\n![Drawdown]({chart_paths['drawdown']})\n\n"
        if chart_paths.get("daily_pl"):
            dashboard += (
                f"### Daily P/L Distribution\n\n![Daily P/L]({chart_paths['daily_pl']})\n\n"
            )
        if chart_paths.get("rolling_sharpe_7d"):
            dashboard += f"### Rolling Sharpe Ratio (7-Day)\n\n![Rolling Sharpe]({chart_paths['rolling_sharpe_7d']})\n\n"
    else:
        # Show helpful message when charts can't be generated
        perf_log_count = len(perf_log) if isinstance(perf_log, list) else 0
        dashboard += "### Equity Curve Visualization\n\n"
        if perf_log_count < 2:
            dashboard += f"*Insufficient data for chart (need at least 2 data points, have {perf_log_count})*\n\n"
        else:
            dashboard += f"*Charts will be generated when matplotlib is available in the environment. Data available: {perf_log_count} data points.*\n\n"

    dashboard += f"""
---

## ⚡ Execution Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Avg Slippage** | {execution.get("avg_slippage", 0):.3f}% | <0.5% | {"✅" if execution.get("avg_slippage", 0) < 0.5 else "⚠️"} |
| **Fill Quality** | {execution.get("fill_quality", 0):.1f}/100 | >90 | {"✅" if execution.get("fill_quality", 0) > 90 else "⚠️"} |
| **Order Success Rate** | {execution.get("order_success_rate", 0):.1f}% | >95% | {"✅" if execution.get("order_success_rate", 0) > 95 else "⚠️"} |
| **Order Reject Rate** | {execution.get("order_reject_rate", 0):.1f}% | <5% | {"✅" if execution.get("order_reject_rate", 0) < 5 else "⚠️"} |
| **Avg Fill Time** | {execution.get("avg_fill_time_ms", 0):.0f} ms | <200ms | {"✅" if execution.get("avg_fill_time_ms", 0) < 200 else "⚠️"} |
| **Broker Latency** | {execution.get("broker_latency_ms", 0):.0f} ms | <100ms | {"✅" if execution.get("broker_latency_ms", 0) < 100 else "⚠️"} |

---

## 📊 Data Completeness & Quality

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Performance Log Completeness** | {data_completeness.get("performance_log_completeness", 0):.1f}% | >95% | {"✅" if data_completeness.get("performance_log_completeness", 0) > 95 else "⚠️"} |
| **Missing Dates** | {data_completeness.get("missing_dates_count", 0)} | 0 | {"✅" if data_completeness.get("missing_dates_count", 0) == 0 else "⚠️"} |
| **Data Freshness** | {data_completeness.get("data_freshness_days", 999)} days old | <1 day | {"✅" if data_completeness.get("data_freshness_days", 999) < 1 else "⚠️"} |
| **Missing Candle %** | {data_completeness.get("missing_candle_pct", 0):.2f}% | <1% | {"✅" if data_completeness.get("missing_candle_pct", 0) < 1 else "⚠️"} |
| **Data Sources** | {", ".join(data_completeness.get("data_sources_used", []))} | Multiple | {"✅" if len(data_completeness.get("data_sources_used", [])) > 1 else "⚠️"} |
| **Model Version** | {data_completeness.get("model_version", "1.0")} | Latest | ✅ |

---

## 🔮 Predictive Analytics

### Monte Carlo Forecast (30-Day)

| Metric | Value |
|--------|-------|
| **Expected P/L (30d)** | ${predictive.get("expected_pl_30d", 0):+.2f} |
| **Forecast Mean** | ${predictive.get("monte_carlo_forecast", {}).get("mean_30d", 0):,.2f} |
| **Forecast Std Dev** | ${predictive.get("monte_carlo_forecast", {}).get("std_30d", 0):,.2f} |
| **5th Percentile** | ${predictive.get("monte_carlo_forecast", {}).get("percentile_5", 0):,.2f} |
| **95th Percentile** | ${predictive.get("monte_carlo_forecast", {}).get("percentile_95", 0):,.2f} |
| **Risk of Ruin** | {predictive.get("risk_of_ruin", 0):.2f}% | {"✅" if predictive.get("risk_of_ruin", 0) < 5 else "⚠️"} |
| **Forecasted Drawdown** | {predictive.get("forecasted_drawdown", 0):.2f}% |
| **Strategy Decay Detected** | {"⚠️ YES" if predictive.get("strategy_decay_detected", False) else "✅ NO"} |

---

## 📊 Benchmark Comparison (vs S&P 500)

| Metric | Portfolio | Benchmark | Difference | Status |
|--------|-----------|-----------|------------|--------|
| **Total Return** | {benchmark.get("portfolio_return", 0):+.2f}% | {benchmark.get("benchmark_return", 0):+.2f}% | {benchmark.get("alpha", 0):+.2f}% | {"✅ Outperforming" if benchmark.get("alpha", 0) > 0 else "⚠️ Underperforming"} |
| **Alpha** | {benchmark.get("alpha", 0):+.2f}% | - | - | {"✅ Positive Alpha" if benchmark.get("alpha", 0) > 0 else "⚠️ Negative Alpha"} |
| **Beta** | {benchmark.get("beta", 1.0):.2f} | 1.0 | {benchmark.get("beta", 1.0) - 1.0:+.2f} | {"Higher Risk" if benchmark.get("beta", 1.0) > 1.0 else "Lower Risk"} |
| **Data Available** | {"✅ Yes" if benchmark.get("data_available", False) else "⚠️ Limited"} | - | - | - |

---

## 🤖 AI-Generated Insights

### Daily Summary

{ai_insights.get("summary", "No summary available.")}

### Strategy Health Score

**{ai_insights.get("strategy_health", {}).get("emoji", "❓")} {ai_insights.get("strategy_health", {}).get("status", "UNKNOWN")}** ({ai_insights.get("strategy_health", {}).get("score", 0):.0f}/100)

"""

    # Add health factors
    health_factors = ai_insights.get("strategy_health", {}).get("factors", [])
    if health_factors:
        dashboard += "\n**Health Factors:**\n"
        for factor in health_factors:
            dashboard += f"- {factor}\n"

    dashboard += """
### Trade Analysis

"""

    trade_analysis = ai_insights.get("trade_analysis", [])
    if trade_analysis:
        for analysis in trade_analysis:
            dashboard += f"{analysis}\n\n"
    else:
        dashboard += "No trade analysis available.\n\n"

    dashboard += """
### Anomalies Detected

"""

    anomalies = ai_insights.get("anomalies", [])
    if anomalies:
        for anomaly in anomalies:
            dashboard += f"{anomaly}\n\n"
    else:
        dashboard += "✅ No anomalies detected.\n\n"

    regime_shift = ai_insights.get("regime_shift")
    if regime_shift:
        dashboard += f"### Market Regime Shift\n\n{regime_shift}\n\n"

    dashboard += """
### Recommendations

"""

    recommendations = ai_insights.get("recommendations", [])
    if recommendations:
        for rec in recommendations:
            dashboard += f"{rec}\n\n"
    else:
        dashboard += "✅ No recommendations at this time.\n\n"

    dashboard += f"""
---

## 📈 Market Regime Classification

| Metric | Value |
|--------|-------|
| **Current Regime** | {regime.get("regime", "UNKNOWN")} |
| **Regime Type** | {regime.get("regime_type", "UNKNOWN")} |
| **Confidence** | {regime.get("confidence", 0):.1f}/1.0 |
| **Trend Strength** | {regime.get("trend_strength", 0):.2f} |
| **Volatility Regime** | {regime.get("volatility_regime", "NORMAL")} |
| **Avg Daily Return** | {regime.get("avg_daily_return", 0):+.2f}% |
| **Volatility** | {regime.get("volatility", 0):.2f}% |

---

## 💰 Financial Performance Summary

| Metric | Value |
|--------|-------|
| **Starting Balance** | ${basic_metrics["starting_balance"]:,.2f} |
| **Current Equity** | ${basic_metrics["current_equity"]:,.2f} |
| **Total P/L** | ${basic_metrics["total_pl"]:+,.2f} ({basic_metrics["total_pl_pct"]:+.2f}%) |
| **Average Daily Profit** | ${basic_metrics["avg_daily_profit"]:+.2f} |
| **Total Trades** | {basic_metrics["total_trades"]} |
| **Win Rate** | {basic_metrics["win_rate"]:.1f}% |
| **Trades Today** | {basic_metrics["today_trade_count"]} |

---

## 📈 90-Day R&D Challenge Progress

**Current**: Day {basic_metrics["current_day"]} of {basic_metrics["total_days"]} ({basic_metrics["progress_pct_challenge"]:.1f}% complete)
**Phase**: {basic_metrics["phase"]}
**Days Remaining**: {basic_metrics["days_remaining"]}

**Progress Bar**: `{progress_bar}` ({basic_metrics["progress_pct_challenge"]:.1f}%)

---

## 🚨 Risk Guardrails & Safety

| Guardrail | Current | Limit | Status |
|-----------|---------|-------|--------|
| **Max Drawdown** | {risk.get("max_drawdown_pct", 0):.2f}% | <10% | {"✅" if risk.get("max_drawdown_pct", 0) < 10 else "⚠️"} |
| **Sharpe Ratio** | {risk.get("sharpe_ratio", 0):.2f} | >1.0 | {"✅" if risk.get("sharpe_ratio", 0) >= 1.0 else "⚠️"} |
| **Volatility** | {risk.get("volatility_annualized", 0):.2f}% | <20% | {"✅" if risk.get("volatility_annualized", 0) < 20 else "⚠️"} |

---

## 📝 Notes

**Dashboard Features**:
- ✅ Comprehensive risk metrics (Sharpe, Sortino, VaR, Conditional VaR, Kelly fraction)
- ✅ Performance attribution by symbol, strategy, and time-of-day
- ✅ Visualizations (equity curve, drawdown, P/L charts)
- ✅ AI-generated insights and recommendations
- ✅ Predictive analytics (Monte Carlo forecasting, risk-of-ruin)
- ✅ Execution metrics (slippage, fill quality, latency)
- ✅ Data completeness tracking
- ✅ Benchmark comparison vs S&P 500
- ✅ Market regime classification

"""

    # Load today's trades for mode detection
    today_trades_file = DATA_DIR / f"trades_{date.today().isoformat()}.json"
    today_trades = load_json_file(today_trades_file)

    # Determine active strategy
    is_crypto_mode = False

    # Check today's trades for crypto
    today_crypto_trades_count = 0
    today_crypto_invested = 0.0

    if today_trades and isinstance(today_trades, list):
        for trade in today_trades:
            if trade.get("symbol", "").endswith("USD") or trade.get("strategy") == "CryptoStrategy":
                is_crypto_mode = True
                today_crypto_trades_count += 1
                today_crypto_invested += float(trade.get("amount", 0.0))

    if not is_crypto_mode:
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            log_files = [
                Path("logs/trading_system.log"),
                Path("logs/launchd_stdout.log"),
                Path("logs/launchd_stderr.log"),
            ]

            for log_file in log_files:
                if log_file.exists():
                    # Check last 1000 lines for today's execution mode
                    with open(log_file) as f:
                        try:
                            lines = f.readlines()[-1000:]
                            for line in lines:
                                if (
                                    today_str in line
                                    and "CRYPTO STRATEGY - Daily Execution" in line
                                ):
                                    is_crypto_mode = True
                                    break
                        except Exception:
                            continue
                if is_crypto_mode:
                    break
        except Exception:
            pass

    dashboard += """
**Current Strategy**:
"""
    # Get crypto strategy info from system state
    strategies = system_state.get("strategies", {})
    tier5 = strategies.get("tier5", {})

    # Use system state cumulative values, OR today's values if system state lags
    crypto_trades_total = tier5.get("trades_executed", 0)
    crypto_invested_total = tier5.get("total_invested", 0.0)

    # If today has trades but state doesn't reflect them (common during day), add them
    # This is a heuristic: if state total < today's total, assume state is stale
    if crypto_trades_total < today_crypto_trades_count:
        crypto_trades_total += today_crypto_trades_count
        crypto_invested_total += today_crypto_invested

    crypto_last_execution = tier5.get("last_execution")
    if is_crypto_mode and not crypto_last_execution:
        crypto_last_execution = date.today().isoformat()

    if is_crypto_mode:
        dashboard += "- **MODE**: 🌐 CRYPTO (Weekend/Holiday)\n"
        dashboard += "- **Strategy**: Tier 5 - Cryptocurrency 24/7 (BTC/ETH)\n"
        dashboard += "- **Allocation**: $10/day fixed (Crypto only)\n"
        dashboard += "- **Status**: ✅ Active (Executed Today)\n"
        dashboard += f"- **Crypto Trades Executed**: {crypto_trades_total}\n"
        dashboard += f"- **Total Crypto Invested**: ${crypto_invested_total:.2f}\n"
        if crypto_last_execution:
            dashboard += f"- **Last Crypto Execution**: {crypto_last_execution}\n"
    else:
        dashboard += "- **MODE**: 📈 STANDARD (Weekday)\n"
        dashboard += "- **Strategy**: Momentum (MACD + RSI + Volume)\n"
        dashboard += "- **Allocation**: 70% Core ETFs (SPY/QQQ/VOO), 30% Growth (NVDA/GOOGL/AMZN)\n"
        dashboard += "- **Daily Investment**: $10/day fixed\n"
        dashboard += f"- **Crypto Trades (Weekend)**: {crypto_trades_total} executed, ${crypto_invested_total:.2f} invested\n"

    dashboard += """
---

## 💰 Options Income (Yield Generation)

"""
    # Check for options activity in logs
    options_activity = []
    try:
        log_files = [Path("logs/trading_system.log")]
        for log_file in log_files:
            if log_file.exists():
                with open(log_file) as f:
                    lines = f.readlines()[-2000:]  # Check last 2000 lines
                    for line in lines:
                        if "EXECUTING OPTIONS STRATEGY" in line:
                            options_activity = []  # Reset on new execution start
                        if "Proposed: Sell" in line:
                            parts = line.split("Proposed: Sell ")[1].strip()
                            options_activity.append(f"- 🎯 **Opportunity**: Sell {parts}")
                        if "Options Strategy: No opportunities found" in line:
                            options_activity = [
                                "- ℹ️ No covered call opportunities found today (need 100+ shares)"
                            ]
    except Exception:
        pass

    if options_activity:
        for activity in options_activity[-5:]:  # Show last 5
            dashboard += f"{activity}\n"
    else:
        dashboard += "- ℹ️ Strategy active (Monitoring for 100+ share positions)\n"

    dashboard += """
---

## 🤖 AI & ML System Status


### RL Training Status
"""

    # Add RL training status
    training_status_file = DATA_DIR / "training_status.json"
    if training_status_file.exists():
        try:
            training_status = load_json_file(training_status_file)
            cloud_jobs = training_status.get("cloud_jobs", {})
            last_training = training_status.get("last_training", {})

            active_jobs = sum(
                1
                for j in cloud_jobs.values()
                if j.get("status") in ["submitted", "running", "in_progress"]
            )
            completed_jobs = sum(
                1 for j in cloud_jobs.values() if j.get("status") in ["completed", "success"]
            )

            dashboard += f"| **Cloud RL Jobs** | {len(cloud_jobs)} total ({active_jobs} active, {completed_jobs} completed) |\n"
            dashboard += f"| **Last Training** | {len(last_training)} symbols trained |\n"

            # Show recent training times
            if last_training:
                recent_symbols = list(last_training.items())[:5]
                dashboard += (
                    f"| **Recent Training** | {', '.join([f'{s}' for s, _ in recent_symbols])} |\n"
                )

            # Add Vertex AI console link
            dashboard += "| **Vertex AI Console** | [View Jobs →](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404) |\n"
        except Exception as e:
            dashboard += f"| **Status** | ⚠️ Unable to load training status ({str(e)[:50]}) |\n"
    else:
        dashboard += "| **Status** | ⚠️ No training data available |\n"
        dashboard += "| **Vertex AI Console** | [View Jobs →](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404) |\n"

    dashboard += """
### LangSmith Monitoring
"""

    # LangSmith Project ID
    project_id = "04fa554e-f155-4039-bb7f-e866f082103b"
    project_url = f"https://smith.langchain.com/o/default/projects/p/{project_id}"

    # Check LangSmith status
    try:
        sys.path.insert(
            0,
            str(
                Path(__file__).parent.parent
                / ".claude"
                / "skills"
                / "langsmith_monitor"
                / "scripts"
            ),
        )
        from langsmith_monitor import LangSmithMonitor

        monitor = LangSmithMonitor()
        health = monitor.monitor_health()

        if health.get("success"):
            stats = monitor.get_project_stats("trading-rl-training", days=7)
            if stats.get("success"):
                dashboard += "| **Status** | ✅ Healthy |\n"
                dashboard += f"| **Total Runs** (7d) | {stats.get('total_runs', 0)} |\n"
                dashboard += f"| **Success Rate** | {stats.get('success_rate', 0):.1f}% |\n"
                dashboard += (
                    f"| **Avg Duration** | {stats.get('average_duration_seconds', 0):.1f}s |\n"
                )
                dashboard += f"| **Project Dashboard** | [trading-rl-training →]({project_url}) |\n"
            else:
                dashboard += "| **Status** | ✅ Healthy (no stats available) |\n"
                dashboard += f"| **Project Dashboard** | [trading-rl-training →]({project_url}) |\n"
        else:
            dashboard += f"| **Status** | ⚠️ {health.get('error', 'Unknown error')} |\n"
            dashboard += f"| **Project Dashboard** | [trading-rl-training →]({project_url}) |\n"
    except Exception:
        dashboard += "| **Status** | ⚠️ LangSmith monitor unavailable |\n"
        dashboard += f"| **Project Dashboard** | [trading-rl-training →]({project_url}) |\n"

    dashboard += f"""
---

## 💰 Tax Optimization & Compliance

**⚠️ CRITICAL FOR LIVE TRADING**: Tax implications can significantly impact net returns. This section tracks capital gains, day trading rules, and tax optimization opportunities.

### Pattern Day Trader (PDT) Rule Status

{pdt_status.get("status", "⚠️ Unable to calculate")}

| Metric | Value | Status |
|--------|-------|--------|
| **Day Trades (Last 5 Days)** | {pdt_status.get("day_trades_count", 0)} | {"🚨" if pdt_status.get("is_pdt", False) and not pdt_status.get("meets_equity_requirement", False) else "⚠️" if pdt_status.get("day_trades_count", 0) >= 2 else "✅"} |
| **PDT Threshold** | 4+ day trades in 5 days | {"🚨 VIOLATION RISK" if pdt_status.get("is_pdt", False) and not pdt_status.get("meets_equity_requirement", False) else "⚠️ APPROACHING" if pdt_status.get("day_trades_count", 0) >= 2 else "✅ SAFE"} |
| **Minimum Equity Required** | $25,000 | {"🚨" if pdt_status.get("is_pdt", False) and not pdt_status.get("meets_equity_requirement", False) else "✅"} |
| **Current Equity** | ${{current_equity:,.2f}} | {"🚨" if pdt_status.get("is_pdt", False) and current_equity < 25000 else "✅"} |

**PDT Rule Explanation**: If you make 4+ day trades (same-day entry/exit) in 5 business days, you must maintain $25,000 minimum equity. Violations can result in account restrictions.

### Tax Impact Analysis

| Metric | Value |
|--------|-------|
| **Total Closed Trades** | {tax_metrics.get("total_trades", 0)} |
| **Day Trades** | {tax_metrics.get("day_trade_count", 0)} |
| **Short-Term Trades** | {tax_metrics.get("short_term_count", 0)} |
| **Long-Term Trades** | {tax_metrics.get("long_term_count", 0)} |
| **Wash Sales** | {tax_metrics.get("wash_sale_count", 0)} |
| **Gross Return** | ${tax_metrics.get("net_gain_loss", basic_metrics.get("total_pl", 0)):+,.2f} |
| **Estimated Tax Liability** | ${tax_metrics.get("estimated_tax", 0.0):+,.2f} |
| **After-Tax Return** | ${tax_metrics.get("after_tax_return", basic_metrics.get("total_pl", 0)):+,.2f} |
| **Tax Efficiency** | {tax_metrics.get("tax_efficiency", 1.0) * 100:.1f}% |

**Tax Rates**:
- **Short-Term Capital Gains** (< 1 year): {tax_metrics.get("short_term_tax_rate", 0.37) * 100:.0f}% (taxed as ordinary income)
- **Long-Term Capital Gains** (≥ 1 year): {tax_metrics.get("long_term_tax_rate", 0.20) * 100:.0f}% (preferred rate)

**Key Tax Strategies**:
1. **Hold positions >1 year** for long-term capital gains rate (20% vs 37%)
2. **Avoid wash sales**: Don't repurchase same security within 30 days of selling at a loss
3. **Tax-loss harvesting**: Realize losses to offset gains before year-end
4. **Mark-to-Market Election (Section 475(f))**: Consider for active traders (treats trading as business income, exempts wash sale rule)

### Tax Optimization Recommendations

"""

    if tax_recommendations:
        for rec in tax_recommendations[:5]:
            dashboard += f"{rec}\n\n"
    else:
        dashboard += "✅ **No immediate tax optimization recommendations**\n\n"

    dashboard += """
**Important Notes**:
- **Paper Trading**: Tax calculations are estimates. Actual tax liability depends on your tax bracket and state.
- **Wash Sale Rule**: Losses cannot be deducted if you repurchase the same security within 30 days before or after the sale.
- **Capital Loss Deduction**: Maximum $3,000 capital loss deduction per year (excess carries forward).
- **Day Trading**: Frequent day trading may trigger Pattern Day Trader (PDT) rules requiring $25k minimum equity.
- **Consult Tax Professional**: This is not tax advice. Consult a qualified tax professional before live trading.

**Integration with RL Pipeline**: Tax-aware reward function penalizes short-term gains and rewards long-term holdings to optimize after-tax returns.

---

## 🔍 Crypto Trade Verification & Trust Metrics

**Purpose**: Verify that crypto trades executed correctly and state tracking is accurate. This prevents the "lying" problem where trades execute but aren't tracked.

### Verification Status

"""

    # Get crypto strategy info
    strategies = system_state.get("strategies", {})
    tier5 = strategies.get("tier5", {})
    crypto_trades = tier5.get("trades_executed", 0)
    crypto_invested = tier5.get("total_invested", 0.0)
    crypto_last_execution = tier5.get("last_execution")

    # Run crypto verification tests and capture results
    verification_status = "⚠️ Not Run"
    verification_details = []
    try:
        from tests.test_crypto_trade_verification import CryptoTradeVerificationTests

        tester = CryptoTradeVerificationTests()
        results = tester.run_all_tests()

        passed = results["passed"]
        total = len(results["details"])

        if passed == total:
            verification_status = f"✅ All Passed ({passed}/{total})"
        elif passed > 0:
            verification_status = f"⚠️ Partial ({passed}/{total} passed)"
        else:
            verification_status = f"❌ Failed ({passed}/{total})"

        # Extract critical verification details
        for detail in results["details"]:
            if detail["test"] == "Positions match state":
                if "MISMATCH" in detail["message"]:
                    verification_status = "🚨 CRITICAL MISMATCH DETECTED"
                    verification_details.append(f"**CRITICAL**: {detail['message']}")
                elif detail["status"] == "✅":
                    verification_details.append("✅ Positions match state tracking")
            elif detail["test"] == "Crypto strategy tracked":
                verification_details.append(
                    f"✅ Crypto strategy tracked: {tier5.get('name', 'Unknown')}"
                )
            elif detail["test"] == "State file valid JSON":
                verification_details.append("✅ State file is valid")

    except ImportError:
        verification_status = "⚠️ Verification module not available"
        verification_details.append("Verification tests require alpaca-py (available in CI)")
    except Exception as e:
        verification_status = f"❌ Verification failed: {str(e)[:50]}"
        verification_details.append(f"Error running verification: {str(e)}")

    dashboard += f"""
| Metric | Status |
|--------|--------|
| **Verification Status** | {verification_status} |
| **Crypto Trades Tracked** | {crypto_trades} |
| **Crypto Invested (Tracked)** | ${crypto_invested:.2f} |
| **Last Execution** | {crypto_last_execution if crypto_last_execution else "Never"} |

### Verification Details

"""

    if verification_details:
        for detail in verification_details:
            dashboard += f"{detail}\n\n"
    else:
        dashboard += "Run verification tests to see detailed results.\n\n"

    dashboard += """
**How Verification Works**:
1. ✅ Checks `system_state.json` exists and is valid
2. ✅ Verifies crypto strategy (tier5) is tracked
3. ✅ Connects to Alpaca API to get actual positions (GROUND TRUTH)
4. ✅ Compares Alpaca positions with our state tracking
5. ✅ Detects mismatches (trades executed but not tracked)

**Critical Test**: If positions exist in Alpaca but state shows 0 trades, this indicates a state tracking bug (like the one we fixed).

**Verification runs automatically** after each crypto trading execution via GitHub Actions.

**Manual Verification**: Run `bash scripts/verify_crypto_trade.sh` anytime to verify independently.

---

"""

    dashboard += r"""
## 🌐 External Dashboards & Monitoring

### LangSmith Observability
- **[LangSmith Dashboard](https://smith.langchain.com)** - Main dashboard
"""
    dashboard += (
        f"- **[Trading RL Training Project]({project_url})** - RL training runs and traces\n"
    )
    dashboard += f"  *Project ID: `{project_id}`*\n"
    dashboard += r"""- **[All Projects](https://smith.langchain.com/o/default/projects)** - View all LangSmith projects


### Vertex AI Cloud RL
- **[Vertex AI Console](https://console.cloud.google.com/vertex-ai?project=email-outreach-ai-460404)** - Main Vertex AI dashboard
- **[Training Jobs](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404)** - View RL training jobs
- **[Models](https://console.cloud.google.com/vertex-ai/models?project=email-outreach-ai-460404)** - Trained models
- **[Experiments](https://console.cloud.google.com/vertex-ai/experiments?project=email-outreach-ai-460404)** - Training experiments

**Project**: `email-outreach-ai-460404` | **Location**: `us-central1`

---

*This dashboard is automatically updated daily by GitHub Actions after trading execution.*
*World-class metrics powered by comprehensive risk & performance analytics.*
"""

    return dashboard


def main():
    """Generate and save enhanced dashboard."""
    dashboard = generate_world_class_dashboard()

    output_file = Path("wiki/Progress-Dashboard.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write(dashboard)

    print("✅ Enhanced world-class progress dashboard generated successfully!")
    print(f"📄 Saved to: {output_file}")
    print(
        "🎯 Features: Risk metrics, Attribution, Visualizations, AI Insights, Predictive Analytics"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
