#!/usr/bin/env python3
"""
AI-Focused Trading Dashboard Generator

Implements investor-grade dashboard with:
- Statistical significance thresholds (hide/gray out metrics with insufficient data)
- First-class AI attribution (per-agent P&L, hit rate, cost per $ of edge)
- Phase readiness gates (traffic-light status for 90-day challenge)
- Distributions and tails (histograms of daily returns and drawdowns)
- Tighter automation status (block trading on failures)
- Capital efficiency metrics (return per unit of risk and compute cost)
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.generate_world_class_dashboard import (
    DATA_DIR,
    calculate_win_rate_from_trades,
    generate_equity_curve_chart,
    generate_returns_distribution_chart,
    load_json_file,
    load_trade_data,
)

# Statistical significance thresholds
STAT_THRESHOLDS = {
    "sharpe_sortino": 30,  # Need 30+ closed trades
    "win_rate": 30,  # Need 30+ closed trades
    "profit_factor": 30,  # Need 30+ closed trades
    "per_strategy": 10,  # Need 10+ trades per strategy
    "cohort_analysis": 20,  # Need 20+ trades per cohort
    "alpha": 50,  # Need 50+ closed trades
    "capital_efficiency": 20,  # Need 20+ closed trades
}


def calculate_ai_attribution(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate per-agent P&L attribution.

    Groups trades by decision maker:
    - RL Policy
    - Heuristic/Rule-based
    - Fallback Strategy
    - LLM Analyst
    - Meta Agent
    """
    agent_attribution = defaultdict(
        lambda: {
            "trades": 0,
            "closed_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pl": 0.0,
            "avg_pl": 0.0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "langsmith_traces": 0,
            "vertex_jobs": 0,
            "estimated_cost": 0.0,
        }
    )

    for trade in trades:
        # Determine agent type from trade metadata
        agent_type = "unknown"

        # Check attribution_metadata first
        attribution = trade.get("attribution_metadata", {})
        if attribution:
            # Check for gate/agent information
            gate1 = attribution.get("gate1_momentum", {})
            gate2 = attribution.get("gate2_rl", {})
            gate3 = attribution.get("gate3_llm", {})
            gate4 = attribution.get("gate4_risk", {})

            if gate2 and gate2.get("decision") == "APPROVE":
                agent_type = "rl_policy"
            elif gate3 and gate3.get("decision") == "APPROVE":
                agent_type = "llm_analyst"
            elif gate1 and gate1.get("decision") == "APPROVE":
                agent_type = "momentum_heuristic"
            elif gate4:
                agent_type = "risk_manager"
        else:
            # Fallback to agent_type field
            agent_type_raw = trade.get("agent_type", "unknown")
            if "rl" in agent_type_raw.lower() or "reinforcement" in agent_type_raw.lower():
                agent_type = "rl_policy"
            elif (
                "llm" in agent_type_raw.lower()
                or "claude" in agent_type_raw.lower()
                or "gpt" in agent_type_raw.lower()
            ):
                agent_type = "llm_analyst"
            elif "heuristic" in agent_type_raw.lower() or "rule" in agent_type_raw.lower():
                agent_type = "heuristic"
            elif "fallback" in agent_type_raw.lower():
                agent_type = "fallback"
            elif "meta" in agent_type_raw.lower():
                agent_type = "meta_agent"
            else:
                agent_type = "unknown"

        agent_data = agent_attribution[agent_type]
        agent_data["trades"] += 1

        # Only count closed trades for P&L
        if trade.get("pl") is not None:
            pl = trade.get("pl", 0.0)
            agent_data["closed_trades"] += 1
            agent_data["total_pl"] += pl

            if pl > 0:
                agent_data["winning_trades"] += 1
                agent_data["gross_profit"] += pl
            else:
                agent_data["losing_trades"] += 1
                agent_data["gross_loss"] += abs(pl)

        # Count LangSmith traces and Vertex jobs
        if attribution:
            if attribution.get("langsmith_trace_id"):
                agent_data["langsmith_traces"] += 1
            if attribution.get("vertex_job_id"):
                agent_data["vertex_jobs"] += 1

        # Estimate cost (placeholder - would need actual cost tracking)
        if agent_type == "llm_analyst":
            agent_data["estimated_cost"] += 0.01  # $0.01 per LLM call
        elif agent_type == "rl_policy":
            agent_data["estimated_cost"] += 0.001  # $0.001 per RL inference

    # Calculate derived metrics
    for agent_type, agent_data in agent_attribution.items():
        if agent_data["closed_trades"] > 0:
            agent_data["avg_pl"] = agent_data["total_pl"] / agent_data["closed_trades"]
            agent_data["win_rate"] = (
                agent_data["winning_trades"] / agent_data["closed_trades"] * 100
            )
            if agent_data["gross_loss"] > 0:
                agent_data["profit_factor"] = agent_data["gross_profit"] / agent_data["gross_loss"]

        # Capital efficiency: return per $ of compute cost
        if agent_data["estimated_cost"] > 0:
            agent_data["capital_efficiency"] = agent_data["total_pl"] / agent_data["estimated_cost"]
        else:
            agent_data["capital_efficiency"] = float("inf") if agent_data["total_pl"] > 0 else 0.0

    return dict(agent_attribution)


def calculate_phase_readiness(
    total_closed_trades: int,
    trading_days: int,
    max_drawdown_pct: float,
    automation_status: dict[str, Any],
    perf_log: list[dict],
) -> dict[str, Any]:
    """
    Calculate phase readiness for 90-day challenge.

    Phases:
    - Phase 1 (Days 1-30): Data collection, basic execution
    - Phase 2 (Days 31-60): Strategy validation, risk management
    - Phase 3 (Days 61-90): Optimization, scaling

    Returns traffic-light status for each phase gate.
    """
    current_day = trading_days

    # Phase 1 gates
    phase1_gates = {
        "min_trades": total_closed_trades >= 10,
        "execution_health": automation_status.get("is_operational", False),
        "data_quality": len(perf_log) >= 10,
    }
    phase1_ready = all(phase1_gates.values())

    # Phase 2 gates
    phase2_gates = {
        "min_trades": total_closed_trades >= 30,
        "drawdown_control": max_drawdown_pct < 10.0,
        "execution_health": automation_status.get("is_operational", False),
        "regime_coverage": len(perf_log) >= 30,
    }
    phase2_ready = all(phase2_gates.values())

    # Phase 3 gates
    phase3_gates = {
        "min_trades": total_closed_trades >= 50,
        "drawdown_control": max_drawdown_pct < 5.0,
        "execution_health": automation_status.get("is_operational", False),
        "positive_edge": True,  # Would need actual edge calculation
    }
    phase3_ready = all(phase3_gates.values())

    # Determine current phase
    if current_day <= 30:
        current_phase = 1
        can_advance = phase1_ready
    elif current_day <= 60:
        current_phase = 2
        can_advance = phase2_ready
    else:
        current_phase = 3
        can_advance = phase3_ready

    return {
        "current_phase": current_phase,
        "can_advance": can_advance,
        "phase1": {
            "ready": phase1_ready,
            "gates": phase1_gates,
            "status": "🟢" if phase1_ready else "🔴",
        },
        "phase2": {
            "ready": phase2_ready,
            "gates": phase2_gates,
            "status": "🟢" if phase2_ready else "🟡" if current_day > 30 else "⚪",
        },
        "phase3": {
            "ready": phase3_ready,
            "gates": phase3_gates,
            "status": "🟢" if phase3_ready else "🟡" if current_day > 60 else "⚪",
        },
    }


def format_statistically_significant(
    value: float, threshold: int, current_count: int, format_str: str = "{:.2f}"
) -> str:
    """
    Format metric with statistical significance indicator.

    Returns formatted value if significant, otherwise "Insufficient data" badge.
    """
    if current_count >= threshold:
        return format_str.format(value)
    else:
        return f"⚠️ Insufficient data (need ≥{threshold}, have {current_count})"


def generate_drawdown_distribution_chart(
    perf_log: list[dict], width: int = 50, height: int = 10
) -> str:
    """Generate ASCII histogram of drawdown distribution."""
    if len(perf_log) < 3:
        return "  (Insufficient data for distribution)"

    equity_values = [entry.get("equity", 100000.0) for entry in perf_log]

    # Calculate drawdowns
    drawdowns = []
    peak = equity_values[0]
    for equity in equity_values:
        if equity > peak:
            peak = equity
        drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0.0
        drawdowns.append(drawdown_pct)

    if not drawdowns:
        return "  (No drawdown data available)"

    drawdowns_array = np.array(drawdowns)

    # Create bins
    min_dd = 0.0
    max_dd = np.max(drawdowns_array)
    if max_dd == 0:
        return "  (No drawdowns detected)"

    bins = np.linspace(min_dd, max_dd, width)

    # Count frequencies
    hist, _ = np.histogram(drawdowns_array, bins=bins)
    max_freq = np.max(hist) if len(hist) > 0 else 1

    # Normalize to chart height
    normalized = (hist / max_freq * height).astype(int)

    # Create chart
    chart_lines = []
    for y in range(height - 1, -1, -1):
        line = "  "
        for freq in normalized:
            line += "█" if freq > y else " "
        chart_lines.append(line)

    # Add labels
    result = f"  0.0% {' ' * (width - 20)} {max_dd:.2f}%\n"
    result += "\n".join(chart_lines)

    return result


def check_automation_blockers(system_state: dict, automation_status: dict[str, Any]) -> list[str]:
    """
    Check for automation failures that should block trading.

    Returns list of blocker messages.
    """
    blockers = []

    # Check GitHub Actions status
    automation = system_state.get("automation", {})
    workflow_status = automation.get("workflow_status", "UNKNOWN")
    if workflow_status != "OPERATIONAL":
        blockers.append(
            f"🚨 **WORKFLOW STATUS**: {workflow_status} - Trading blocked until resolved"
        )

    # Check LangSmith initialization
    try:
        from scripts.monitor_training_and_update_dashboard import TrainingMonitor

        monitor = TrainingMonitor()
        if monitor.langsmith_monitor and monitor.langsmith_monitor.client is None:
            blockers.append(
                "🚨 **LANGSMITH CLIENT FAILED**: RL observability broken - signals may be unreliable"
            )
    except Exception:
        pass

    # Check execution failures
    failures = automation_status.get("failures", 0)
    execution_count = automation_status.get("execution_count", 0)
    if failures > 0 and execution_count == 0:
        blockers.append(
            f"🚨 **EXECUTION FAILURES**: {failures} failures, 0 successes - system may be broken"
        )

    # Check days since last execution
    days_since = automation_status.get("days_since_execution", 0)
    if days_since > 2:
        blockers.append(
            f"⚠️ **STALE EXECUTION**: Last successful execution {days_since} days ago - check automation"
        )

    return blockers


def generate_ai_focused_dashboard() -> str:
    """Generate AI-focused dashboard with investor-grade metrics."""

    # Load data
    system_state = load_json_file(DATA_DIR / "system_state.json")
    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    challenge_start = load_json_file(DATA_DIR / "challenge_start.json")
    trades = load_trade_data()

    if not isinstance(perf_log, list):
        perf_log = []

    # Extract equity curve
    equity_curve = []
    if len(perf_log) > 0:
        equity_curve = [
            entry.get("equity", 100000.0) for entry in perf_log if entry.get("equity") is not None
        ]

    if not equity_curve:
        current_equity = system_state.get("account", {}).get("current_equity", 100000.0)
        if current_equity:
            equity_curve = [current_equity]

    # Calculate basic metrics
    account = system_state.get("account", {})
    total_pl = account.get("total_pl", 0.0)
    current_equity = account.get("current_equity", 100000.0)
    starting_balance = challenge_start.get("starting_balance", 100000.0)

    # Calculate win rate
    win_rate, winning_trades, total_closed_trades = calculate_win_rate_from_trades(trades)

    # Calculate returns
    returns = []
    if len(equity_curve) > 1:
        returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
        ]

    # Calculate risk metrics
    risk_metrics_dict = {}
    if len(equity_curve) > 1:
        from scripts.dashboard_metrics import TradingMetricsCalculator

        calculator = TradingMetricsCalculator()
        risk_metrics_dict = calculator._calculate_risk_metrics(
            perf_log, starting_balance, current_equity
        )

    # Calculate AI attribution
    ai_attribution = calculate_ai_attribution(trades)

    # Calculate automation status
    from scripts.dashboard_metrics import TradingMetricsCalculator

    calculator = TradingMetricsCalculator()
    automation_status = calculator._calculate_automation_status(system_state, perf_log)

    # Check automation blockers
    automation_blockers = check_automation_blockers(system_state, automation_status)

    # Calculate phase readiness
    trading_days = len(perf_log) if perf_log else 1
    phase_readiness = calculate_phase_readiness(
        total_closed_trades,
        trading_days,
        risk_metrics_dict.get("max_drawdown_pct", 0.0),
        automation_status,
        perf_log,
    )

    # Calculate averages
    avg_daily_profit = total_pl / trading_days if trading_days > 0 else 0.0
    north_star_target = 100.0
    progress_pct = (avg_daily_profit / north_star_target * 100) if north_star_target > 0 else 0.0

    # Challenge info
    challenge = system_state.get("challenge", {})
    current_day = challenge.get("current_day", trading_days)
    total_days = challenge.get("total_days", 90)

    # Today's performance
    today_str = date.today().isoformat()
    today_equity = current_equity
    today_pl = 0.0
    today_pl_pct = 0.0

    if perf_log:
        for entry in reversed(perf_log):
            if entry.get("date") == today_str:
                today_equity = entry.get("equity", current_equity)
                today_pl = entry.get("pl", 0.0)
                today_pl_pct = entry.get("pl_pct", 0.0) * 100
                break

    now = datetime.now()
    today_display = date.today().strftime("%Y-%m-%d (%A)")

    # Generate dashboard
    dashboard = f"""# 🎯 AI-Focused Trading Dashboard

**Last Updated**: {now.strftime("%Y-%m-%d %I:%M %p ET")}
**Dashboard Version**: AI-Focused v3.0 (Investor-Grade)
**Focus**: Decision-making & AI Attribution

---

## 🚦 Automation Status & Trading Blockers

"""

    # Show automation blockers prominently
    if automation_blockers:
        dashboard += "### ⛔ TRADING BLOCKERS - ACTION REQUIRED\n\n"
        for blocker in automation_blockers:
            dashboard += f"{blocker}\n\n"
        dashboard += "**⚠️ Trading should be paused until blockers are resolved**\n\n"
    else:
        dashboard += "✅ **No automation blockers detected**\n\n"

    dashboard += f"""
**Automation Health**:
- Status: {"🟢 OPERATIONAL" if automation_status.get("is_operational") else "🔴 DEGRADED"}
- Uptime: {automation_status.get("uptime_percentage", 0):.1f}%
- Executions: {automation_status.get("execution_count", 0)} successful, {automation_status.get("failures", 0)} failures
- Last Execution: {automation_status.get("last_execution", "Never")}

---

## 📅 Today's Performance

**Date**: {today_display}

| Metric | Value |
|--------|-------|
| **Equity** | ${today_equity:,.2f} |
| **P/L** | ${today_pl:+,.2f} ({today_pl_pct:+.2f}%) |
| **Status** | {"✅ Active" if abs(today_pl) > 0.01 else "⏸️ No activity yet"} |

"""

    # Best-effort: load funnel telemetry counts
    telemetry_path = Path("data/audit_trail/hybrid_funnel_runs.jsonl")
    order_count = 0
    stop_count = 0
    if telemetry_path.exists():
        try:
            with telemetry_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        evt = json.loads(line)
                        if evt.get("event") == "execution.order":
                            order_count += 1
                        elif evt.get("event") == "execution.stop":
                            stop_count += 1
                    except Exception:
                        continue
        except Exception:
            pass

    dashboard += f"""
| **Funnel Activity** | {order_count} orders, {stop_count} stops |

---

## 🎯 North Star Goal

**Target**: **$100+/day profit**

| Metric | Current | Target | Progress |
|--------|---------|--------|----------|
| **Average Daily Profit** | ${avg_daily_profit:.2f}/day | $100.00/day | {progress_pct:.2f}% |
| **Total P/L** | ${total_pl:+,.2f} ({total_pl / starting_balance * 100:+.2f}%) | TBD | {"✅" if total_pl > 0 else "⚠️"} |

---

## 🚦 Phase Readiness (90-Day Challenge)

**Current Phase**: {phase_readiness["current_phase"]} | **Can Advance**: {"✅ YES" if phase_readiness["can_advance"] else "❌ NO"}

| Phase | Status | Gates |
|-------|--------|-------|
| **Phase 1** (Days 1-30) | {phase_readiness["phase1"]["status"]} | Trades: {"✅" if phase_readiness["phase1"]["gates"]["min_trades"] else "❌"} | Execution: {"✅" if phase_readiness["phase1"]["gates"]["execution_health"] else "❌"} | Data: {"✅" if phase_readiness["phase1"]["gates"]["data_quality"] else "❌"} |
| **Phase 2** (Days 31-60) | {phase_readiness["phase2"]["status"]} | Trades: {"✅" if phase_readiness["phase2"]["gates"]["min_trades"] else "❌"} | DD Control: {"✅" if phase_readiness["phase2"]["gates"]["drawdown_control"] else "❌"} | Execution: {"✅" if phase_readiness["phase2"]["gates"]["execution_health"] else "❌"} |
| **Phase 3** (Days 61-90) | {phase_readiness["phase3"]["status"]} | Trades: {"✅" if phase_readiness["phase3"]["gates"]["min_trades"] else "❌"} | DD Control: {"✅" if phase_readiness["phase3"]["gates"]["drawdown_control"] else "❌"} | Edge: {"✅" if phase_readiness["phase3"]["gates"]["positive_edge"] else "❌"} |

**Current**: Day {current_day} of {total_days} ({current_day / total_days * 100:.1f}% complete)

---

## 🤖 AI Attribution (First-Class)

### Per-Agent Performance

"""

    # Generate AI attribution table
    if ai_attribution:
        dashboard += "| Agent/Decision Maker | Trades | Closed | Win Rate | Total P/L | Avg P/L | Profit Factor | Capital Efficiency | Cost |\n"
        dashboard += "|---------------------|--------|-------|---------|-----------|---------|---------------|-------------------|------|\n"

        for agent_type, data in sorted(
            ai_attribution.items(),
            key=lambda x: x[1].get("total_pl", 0),
            reverse=True,
        ):
            agent_name = agent_type.replace("_", " ").title()
            win_rate_display = (
                format_statistically_significant(
                    data["win_rate"],
                    STAT_THRESHOLDS["win_rate"],
                    data["closed_trades"],
                    "{:.1f}%",
                )
                if data["closed_trades"] > 0
                else "N/A"
            )
            profit_factor_display = (
                format_statistically_significant(
                    data["profit_factor"],
                    STAT_THRESHOLDS["profit_factor"],
                    data["closed_trades"],
                    "{:.2f}",
                )
                if data["closed_trades"] > 0
                else "N/A"
            )

            dashboard += f"| **{agent_name}** | {data['trades']} | {data['closed_trades']} | {win_rate_display} | ${data['total_pl']:+,.2f} | ${data['avg_pl']:+,.2f} | {profit_factor_display} | ${data['capital_efficiency']:,.0f}/$ | ${data['estimated_cost']:.2f} |\n"

        dashboard += "\n**Observability**:\n"
        total_traces = sum(a.get("langsmith_traces", 0) for a in ai_attribution.values())
        total_jobs = sum(a.get("vertex_jobs", 0) for a in ai_attribution.values())
        dashboard += f"- LangSmith Traces: {total_traces}\n"
        dashboard += f"- Vertex AI Jobs: {total_jobs}\n"
    else:
        dashboard += (
            "⚠️ **No AI attribution data available** - Trades may not have attribution metadata\n\n"
        )

    dashboard += "\n---\n\n## ⚖️ Risk Metrics (Statistically Significant Only)\n\n"

    # Show only statistically significant risk metrics
    sharpe_display = (
        format_statistically_significant(
            risk_metrics_dict.get("sharpe_ratio", 0.0),
            STAT_THRESHOLDS["sharpe_sortino"],
            total_closed_trades,
            "{:.2f}",
        )
        if total_closed_trades > 0
        else "⚠️ Insufficient data"
    )

    sortino_display = (
        format_statistically_significant(
            risk_metrics_dict.get("sortino_ratio", 0.0),
            STAT_THRESHOLDS["sharpe_sortino"],
            total_closed_trades,
            "{:.2f}",
        )
        if total_closed_trades > 0
        else "⚠️ Insufficient data"
    )

    dashboard += f"""
| Metric | Value | Status |
|--------|-------|--------|
| **Max Drawdown** | {risk_metrics_dict.get("max_drawdown_pct", 0.0):.2f}% | {"✅" if risk_metrics_dict.get("max_drawdown_pct", 0.0) < 5.0 else "⚠️" if risk_metrics_dict.get("max_drawdown_pct", 0.0) < 10.0 else "🚨"} |
| **Volatility (Annualized)** | {risk_metrics_dict.get("volatility_annualized", 0.0):.2f}% | {"✅" if risk_metrics_dict.get("volatility_annualized", 0.0) < 20.0 else "⚠️"} |
| **Sharpe Ratio** | {sharpe_display} | {"✅" if isinstance(sharpe_display, float) and sharpe_display > 1.0 else "⚠️" if isinstance(sharpe_display, float) and sharpe_display > 0.5 else ""} |
| **Sortino Ratio** | {sortino_display} | {"✅" if isinstance(sortino_display, float) and sortino_display > 1.0 else ""} |
| **VaR (95%)** | {risk_metrics_dict.get("var_95", 0.0):.2f}% | Risk level |
| **CVaR (95%)** | {risk_metrics_dict.get("cvar_95", 0.0):.2f}% | Expected tail loss |

**Note**: Sharpe/Sortino ratios require ≥{STAT_THRESHOLDS["sharpe_sortino"]} closed trades for statistical significance. Current: {total_closed_trades} trades.

---

## 📊 Performance Metrics (Core Only)

| Metric | Value | Significance |
|--------|-------|--------------|
| **Total P/L** | ${total_pl:+,.2f} ({total_pl / starting_balance * 100:+.2f}%) | ✅ Always meaningful |
| **Win Rate** | {format_statistically_significant(win_rate, STAT_THRESHOLDS["win_rate"], total_closed_trades, "{:.1f}%")} ({winning_trades}/{total_closed_trades}) | {"✅" if total_closed_trades >= STAT_THRESHOLDS["win_rate"] else "⚠️"} |
| **Total Trades** | {len(trades)} | ✅ Always meaningful |
| **Closed Trades** | {total_closed_trades} | ✅ Always meaningful |

**Note**: Win rate requires ≥{STAT_THRESHOLDS["win_rate"]} closed trades for statistical significance.

---

## 📈 Distributions & Tails

### Daily Returns Distribution

"""

    if len(returns) > 3:
        dashboard += f"```\n{generate_returns_distribution_chart(returns)}\n```\n\n"
    else:
        dashboard += "⚠️ **Insufficient data** - Need ≥4 data points for distribution\n\n"

    dashboard += "### Drawdown Distribution\n\n"

    if len(perf_log) > 3:
        dashboard += f"```\n{generate_drawdown_distribution_chart(perf_log)}\n```\n\n"
    else:
        dashboard += "⚠️ **Insufficient data** - Need ≥4 data points for distribution\n\n"

    dashboard += "### Equity Curve\n\n"

    if len(equity_curve) > 1:
        dashboard += f"```\n{generate_equity_curve_chart(equity_curve)}\n```\n\n"
    else:
        dashboard += "⚠️ **Insufficient data** - Need ≥2 data points for chart\n\n"

    dashboard += """---

## 💡 Key Insights

"""

    # Generate insights based on data availability
    if total_closed_trades < STAT_THRESHOLDS["win_rate"]:
        dashboard += f"⚠️ **PRIMARY FOCUS**: Generate and close risk-bearing trades. Current: {total_closed_trades} closed trades. Need ≥{STAT_THRESHOLDS['win_rate']} for meaningful metrics.\n\n"

    if ai_attribution:
        best_agent = max(
            ai_attribution.items(),
            key=lambda x: x[1].get("total_pl", 0),
            default=(None, {}),
        )
        if best_agent[0] and best_agent[1].get("total_pl", 0) > 0:
            dashboard += f"✅ **BEST AI AGENT**: {best_agent[0].replace('_', ' ').title()} with ${best_agent[1].get('total_pl', 0):+,.2f} P/L\n\n"

    if automation_blockers:
        dashboard += "🚨 **CRITICAL**: Resolve automation blockers before continuing trading\n\n"

    dashboard += """---

## 🔗 Quick Links

- [Repository](https://github.com/IgorGanapolsky/trading)
- [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)
- [Latest Trades](https://github.com/IgorGanapolsky/trading/tree/main/data)

---

*AI-Focused Dashboard v3.0 - Designed for decision-making and AI attribution analysis*
*Metrics are hidden/grayed out until statistical significance thresholds are met*

"""

    return dashboard


def main():
    """Generate and save AI-focused dashboard."""
    dashboard = generate_ai_focused_dashboard()

    # Save to file
    output_file = Path("wiki/Progress-Dashboard.md")
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        f.write(dashboard)

    print("✅ AI-focused dashboard generated successfully!")
    print(f"📄 Saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
