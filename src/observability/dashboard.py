"""
Observability Dashboard for Deep Agent Monitoring.

Provides real-time and historical metrics visualization for the trading system.
Can generate text reports or export data for external dashboards (Grafana, etc.)

Usage:
    from src.observability.dashboard import ObservabilityDashboard

    dashboard = ObservabilityDashboard()
    report = dashboard.generate_report()
    print(report)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.observability.langsmith_tracer import LangSmithTracer, TraceType, get_tracer
from src.observability.trade_evaluator import TradeEvaluator

logger = logging.getLogger(__name__)


@dataclass
class DailyMetrics:
    """Metrics for a single day."""

    date: str
    trace_count: int
    total_cost_usd: float
    avg_latency_ms: float
    error_rate: float
    decisions_made: int
    trades_executed: int
    win_rate: float


class ObservabilityDashboard:
    """
    Dashboard for monitoring Deep Agent behavior and performance.

    Aggregates data from:
    - LangSmith traces (latency, costs, errors)
    - Trade evaluator (decisions, outcomes, quality)
    - System metrics (memory, API calls)
    """

    def __init__(
        self,
        tracer: Optional[LangSmithTracer] = None,
        evaluator: Optional[TradeEvaluator] = None,
    ):
        self.tracer = tracer or get_tracer()
        self.evaluator = evaluator or TradeEvaluator()

    def get_daily_metrics(self, days: int = 7) -> List[DailyMetrics]:
        """Get metrics for each of the past N days."""
        trace_summary = self.tracer.get_trace_summary(days=days)
        eval_metrics = self.evaluator.get_metrics(days=days)

        metrics = []
        for i in range(days):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            day_data = trace_summary.get("by_day", {}).get(date, {})

            metrics.append(
                DailyMetrics(
                    date=date,
                    trace_count=day_data.get("count", 0),
                    total_cost_usd=day_data.get("cost_usd", 0.0),
                    avg_latency_ms=trace_summary.get("avg_duration_ms", 0.0),
                    error_rate=trace_summary.get("error_rate", 0.0),
                    decisions_made=eval_metrics.total_decisions // days if days > 0 else 0,
                    trades_executed=eval_metrics.profitable_count + eval_metrics.loss_count,
                    win_rate=eval_metrics.win_rate,
                )
            )

        return metrics

    def get_cost_breakdown(self, days: int = 30) -> Dict[str, Any]:
        """Get cost breakdown by trace type and model."""
        trace_summary = self.tracer.get_trace_summary(days=days)

        return {
            "total_cost_usd": trace_summary.get("total_cost_usd", 0.0),
            "total_tokens": trace_summary.get("total_tokens", 0),
            "by_type": trace_summary.get("by_type", {}),
            "daily_average": trace_summary.get("total_cost_usd", 0.0) / days if days > 0 else 0.0,
            "budget_remaining": 100.0 - trace_summary.get("total_cost_usd", 0.0),  # $100/mo budget
        }

    def get_decision_quality_breakdown(self) -> Dict[str, Any]:
        """Get breakdown of decision quality."""
        metrics = self.evaluator.get_metrics(days=30)

        total_quality = (
            metrics.excellent_count +
            metrics.good_count +
            metrics.lucky_count +
            metrics.unlucky_count +
            metrics.poor_count
        )

        if total_quality == 0:
            return {
                "excellent_pct": 0,
                "good_pct": 0,
                "lucky_pct": 0,
                "unlucky_pct": 0,
                "poor_pct": 0,
            }

        return {
            "excellent_pct": metrics.excellent_count / total_quality * 100,
            "good_pct": metrics.good_count / total_quality * 100,
            "lucky_pct": metrics.lucky_count / total_quality * 100,
            "unlucky_pct": metrics.unlucky_count / total_quality * 100,
            "poor_pct": metrics.poor_count / total_quality * 100,
            "calibration_error": metrics.calibration_error,
        }

    def get_strategy_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare performance across strategies."""
        metrics = self.evaluator.get_metrics(days=30)

        comparison = {}
        for strategy, data in metrics.by_strategy.items():
            count = data.get("count", 0)
            if count > 0:
                comparison[strategy] = {
                    "count": count,
                    "win_rate": data.get("wins", 0) / count,
                    "avg_profit_pct": data.get("total_profit", 0) / count,
                }

        return comparison

    def get_model_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare performance across LLM models."""
        metrics = self.evaluator.get_metrics(days=30)

        comparison = {}
        for model, data in metrics.by_model.items():
            count = data.get("count", 0)
            if count > 0:
                comparison[model] = {
                    "count": count,
                    "win_rate": data.get("wins", 0) / count,
                    "avg_profit_pct": data.get("total_profit", 0) / count,
                }

        return comparison

    def generate_report(self, days: int = 7) -> str:
        """Generate a text report of observability metrics."""
        trace_summary = self.tracer.get_trace_summary(days=days)
        eval_metrics = self.evaluator.get_metrics(days=days)
        cost_breakdown = self.get_cost_breakdown(days=days)
        quality_breakdown = self.get_decision_quality_breakdown()

        lines = [
            "=" * 60,
            "DEEP AGENT OBSERVABILITY REPORT",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Period: Last {days} days",
            "=" * 60,
            "",
            "TRACE SUMMARY",
            "-" * 40,
            f"  Total Traces: {trace_summary.get('total_traces', 0)}",
            f"  Total Tokens: {trace_summary.get('total_tokens', 0):,}",
            f"  Avg Latency:  {trace_summary.get('avg_duration_ms', 0):.0f}ms",
            f"  Error Rate:   {trace_summary.get('error_rate', 0):.1%}",
            "",
            "COST ANALYSIS",
            "-" * 40,
            f"  Total Cost:      ${cost_breakdown.get('total_cost_usd', 0):.4f}",
            f"  Daily Average:   ${cost_breakdown.get('daily_average', 0):.4f}",
            f"  Budget Remaining: ${cost_breakdown.get('budget_remaining', 100):.2f}",
            "",
            "DECISION METRICS",
            "-" * 40,
            f"  Total Decisions: {eval_metrics.total_decisions}",
            f"  Resolved:        {eval_metrics.resolved_decisions}",
            f"  Win Rate:        {eval_metrics.win_rate:.1%}",
            f"  Avg Profit:      {eval_metrics.avg_profit_pct:+.2f}%",
            f"  Calibration Error: {eval_metrics.calibration_error:.2f}",
            "",
            "DECISION QUALITY",
            "-" * 40,
            f"  Excellent: {quality_breakdown.get('excellent_pct', 0):.1f}%",
            f"  Good:      {quality_breakdown.get('good_pct', 0):.1f}%",
            f"  Lucky:     {quality_breakdown.get('lucky_pct', 0):.1f}%",
            f"  Unlucky:   {quality_breakdown.get('unlucky_pct', 0):.1f}%",
            f"  Poor:      {quality_breakdown.get('poor_pct', 0):.1f}%",
            "",
            "OUTCOMES",
            "-" * 40,
            f"  Profitable:   {eval_metrics.profitable_count}",
            f"  Breakeven:    {eval_metrics.breakeven_count}",
            f"  Loss:         {eval_metrics.loss_count}",
            f"  Avoided Loss: {eval_metrics.avoided_loss_count}",
            f"  Missed Gain:  {eval_metrics.missed_gain_count}",
            "",
        ]

        # Add trace type breakdown
        by_type = trace_summary.get("by_type", {})
        if by_type:
            lines.extend([
                "TRACES BY TYPE",
                "-" * 40,
            ])
            for trace_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
                lines.append(f"  {trace_type:15} {count:5}")
            lines.append("")

        # Add strategy comparison
        strategy_comp = self.get_strategy_comparison()
        if strategy_comp:
            lines.extend([
                "STRATEGY COMPARISON",
                "-" * 40,
            ])
            for strategy, data in strategy_comp.items():
                lines.append(
                    f"  {strategy:10} | "
                    f"N={data['count']:3} | "
                    f"Win={data['win_rate']:.1%} | "
                    f"Avg={data['avg_profit_pct']:+.2f}%"
                )
            lines.append("")

        # Add model comparison
        model_comp = self.get_model_comparison()
        if model_comp:
            lines.extend([
                "MODEL COMPARISON",
                "-" * 40,
            ])
            for model, data in model_comp.items():
                lines.append(
                    f"  {model:20} | "
                    f"N={data['count']:3} | "
                    f"Win={data['win_rate']:.1%}"
                )
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format for Grafana."""
        trace_summary = self.tracer.get_trace_summary(days=1)
        eval_metrics = self.evaluator.get_metrics(days=1)

        lines = [
            "# HELP trading_agent_traces_total Total number of traces",
            "# TYPE trading_agent_traces_total counter",
            f"trading_agent_traces_total {trace_summary.get('total_traces', 0)}",
            "",
            "# HELP trading_agent_cost_usd Total cost in USD",
            "# TYPE trading_agent_cost_usd gauge",
            f"trading_agent_cost_usd {trace_summary.get('total_cost_usd', 0):.6f}",
            "",
            "# HELP trading_agent_latency_ms Average latency in milliseconds",
            "# TYPE trading_agent_latency_ms gauge",
            f"trading_agent_latency_ms {trace_summary.get('avg_duration_ms', 0):.2f}",
            "",
            "# HELP trading_agent_error_rate Error rate",
            "# TYPE trading_agent_error_rate gauge",
            f"trading_agent_error_rate {trace_summary.get('error_rate', 0):.4f}",
            "",
            "# HELP trading_agent_win_rate Trading win rate",
            "# TYPE trading_agent_win_rate gauge",
            f"trading_agent_win_rate {eval_metrics.win_rate:.4f}",
            "",
            "# HELP trading_agent_decisions_total Total decisions made",
            "# TYPE trading_agent_decisions_total counter",
            f"trading_agent_decisions_total {eval_metrics.total_decisions}",
            "",
            "# HELP trading_agent_calibration_error Calibration error",
            "# TYPE trading_agent_calibration_error gauge",
            f"trading_agent_calibration_error {eval_metrics.calibration_error:.4f}",
        ]

        return "\n".join(lines)

    def save_report(self, output_path: Optional[Path] = None):
        """Save report to file."""
        output_path = output_path or Path("reports") / f"observability_{datetime.now().strftime('%Y-%m-%d')}.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = self.generate_report()
        output_path.write_text(report)

        logger.info(f"Observability report saved to {output_path}")
        return output_path
