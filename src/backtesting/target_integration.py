"""
Target Integration for Backtesting

This module integrates the $100/day target model with the backtest engine,
ensuring every backtest automatically evaluates progress toward the target.

Author: Trading System
Created: 2025-12-03
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.backtesting.backtest_results import BacktestResults

from src.targets.capital_model import CapitalModel, CapitalRequirements
from src.targets.daily_target import DailyTargetModel, TargetMetrics

logger = logging.getLogger(__name__)


@dataclass
class TargetBacktestReport:
    """Combined backtest + target analysis report."""

    # Core backtest metrics
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int

    # Target-specific metrics
    target_metrics: TargetMetrics
    capital_requirements: CapitalRequirements

    # Summary
    on_track_for_target: bool
    gap_to_target_daily: float
    estimated_capital_needed: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "backtest_metrics": {
                "total_return_pct": round(self.total_return_pct, 2),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "win_rate": round(self.win_rate, 2),
                "total_trades": self.total_trades,
            },
            "target_metrics": self.target_metrics.to_dict(),
            "capital_requirements": self.capital_requirements.to_dict(),
            "summary": {
                "on_track_for_target": self.on_track_for_target,
                "gap_to_target_daily": round(self.gap_to_target_daily, 2),
                "estimated_capital_needed": round(self.estimated_capital_needed, 2),
            },
        }

    def generate_report_section(self) -> str:
        """Generate a formatted section for inclusion in backtest reports."""
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("HOW CLOSE TO $100/DAY?")
        lines.append("=" * 60)
        lines.append("")

        tm = self.target_metrics

        # Progress bar
        progress = min(100, max(0, tm.progress_to_target_pct))
        bar_filled = int(progress / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        lines.append(f"Progress: [{bar}] {progress:.1f}%")
        lines.append("")

        # Key metrics
        lines.append(f"  Average Daily P&L:     ${tm.average_daily_pnl:>10.2f}")
        lines.append(f"  Target Daily P&L:      ${tm.target_daily_pnl:>10.2f}")
        lines.append(f"  Gap:                   ${self.gap_to_target_daily:>10.2f}")
        lines.append("")

        lines.append(
            f"  Days Above Target:     {tm.days_above_target:>10} / {tm.total_trading_days}"
        )
        lines.append(f"  Hit Rate:              {tm.pct_days_hit_target:>10.1f}%")
        lines.append("")

        # Risk check
        lines.append("Risk Assessment:")
        lines.append(f"  Worst 5-Day Drawdown:  ${tm.worst_5day_drawdown:>10.2f}")
        lines.append(f"  Worst 20-Day Drawdown: ${tm.worst_20day_drawdown:>10.2f}")
        lines.append(f"  Max Single Day Loss:   ${tm.max_single_day_loss:>10.2f}")
        lines.append("")

        # Capital analysis
        lines.append("Capital Requirements:")
        lines.append(
            f"  Current Capital:       ${self.capital_requirements.current_capital:>10.2f}"
        )
        lines.append(f"  Capital Needed (mod.): ${self.estimated_capital_needed:>10.2f}")
        cap_gap = self.estimated_capital_needed - self.capital_requirements.current_capital
        if cap_gap > 0:
            lines.append(f"  Capital Gap:           ${cap_gap:>10.2f}")
        else:
            lines.append(f"  Capital Surplus:       ${-cap_gap:>10.2f}")
        lines.append("")

        # Verdict
        if self.on_track_for_target:
            lines.append("✅ ON TRACK: Strategy can achieve $100/day target")
        else:
            lines.append("⚠️  OFF TRACK: Strategy needs improvement to hit target")
            if cap_gap > 0:
                lines.append(f"   - Need ${cap_gap:,.2f} more capital, OR")
            lines.append(f"   - Need to improve daily P&L by ${self.gap_to_target_daily:.2f}")
        lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)


def evaluate_backtest_with_target(
    results: BacktestResults,
    target_daily: float = 100.0,
) -> TargetBacktestReport:
    """
    Evaluate a backtest against the $100/day target.

    Args:
        results: BacktestResults from backtest engine
        target_daily: Daily profit target (default $100)

    Returns:
        TargetBacktestReport with full analysis
    """
    # Create target model from equity curve
    target_model = DailyTargetModel.from_backtest_results(
        equity_curve=results.equity_curve,
        initial_capital=results.initial_capital,
        target_daily_profit=target_daily,
    )
    target_metrics = target_model.calculate_metrics()

    # Create capital model
    capital_model = CapitalModel(
        daily_target=target_daily,
        current_capital=results.initial_capital,
    )
    capital_reqs = capital_model.calculate_requirements()

    # Calculate gap
    gap = target_daily - target_metrics.average_daily_pnl

    # Determine if on track
    on_track = (
        target_metrics.progress_to_target_pct >= 80  # Close to target
        or target_metrics.pct_days_hit_target >= 40  # Hitting target often
        or (
            target_metrics.trend_direction == "improving"
            and target_metrics.progress_to_target_pct >= 50
        )
    )

    return TargetBacktestReport(
        total_return_pct=results.total_return,
        sharpe_ratio=results.sharpe_ratio,
        max_drawdown_pct=results.max_drawdown,
        win_rate=results.win_rate,
        total_trades=results.total_trades,
        target_metrics=target_metrics,
        capital_requirements=capital_reqs,
        on_track_for_target=on_track,
        gap_to_target_daily=gap,
        estimated_capital_needed=capital_reqs.capital_at_0_50_pct_daily,
    )


def add_target_section_to_report(
    results: BacktestResults,
    original_report: str,
    target_daily: float = 100.0,
) -> str:
    """
    Add the $100/day target section to an existing backtest report.

    Args:
        results: BacktestResults from backtest engine
        original_report: The original report string
        target_daily: Daily profit target

    Returns:
        Enhanced report with target section
    """
    target_report = evaluate_backtest_with_target(results, target_daily)
    target_section = target_report.generate_report_section()

    # Insert before the closing line
    return original_report + "\n" + target_section


def save_target_evaluation(
    results: BacktestResults,
    filepath: str | Path = "data/backtest_target_eval.json",
    target_daily: float = 100.0,
) -> Path:
    """
    Save target evaluation to JSON for CI/dashboard use.

    Args:
        results: BacktestResults from backtest engine
        filepath: Output file path
        target_daily: Daily profit target

    Returns:
        Path to saved file
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    target_report = evaluate_backtest_with_target(results, target_daily)

    data = {
        "timestamp": datetime.now().isoformat(),
        "strategy": getattr(results, "strategy_name", "unknown"),
        "period": f"{results.start_date} to {results.end_date}",
        "evaluation": target_report.to_dict(),
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Saved target evaluation to {filepath}")
    return filepath


class BacktestTargetValidator:
    """
    Validator for CI pipelines that checks if backtests meet target criteria.

    Usage in CI:
        validator = BacktestTargetValidator()
        if not validator.validate(results):
            sys.exit(1)  # Fail the build
    """

    def __init__(
        self,
        target_daily: float = 100.0,
        min_sharpe: float = 0.5,
        max_drawdown_pct: float = 20.0,
        min_win_rate: float = 45.0,
        min_progress_pct: float = 50.0,  # At least 50% of target
    ):
        self.target_daily = target_daily
        self.min_sharpe = min_sharpe
        self.max_drawdown_pct = max_drawdown_pct
        self.min_win_rate = min_win_rate
        self.min_progress_pct = min_progress_pct

    def validate(self, results: BacktestResults) -> tuple[bool, list[str]]:
        """
        Validate backtest results against target criteria.

        Returns:
            Tuple of (passed, list_of_failures)
        """
        target_report = evaluate_backtest_with_target(results, self.target_daily)
        failures = []

        # Check Sharpe ratio
        if results.sharpe_ratio < self.min_sharpe:
            failures.append(f"Sharpe ratio {results.sharpe_ratio:.2f} < {self.min_sharpe:.2f}")

        # Check max drawdown
        if results.max_drawdown > self.max_drawdown_pct:
            failures.append(
                f"Max drawdown {results.max_drawdown:.1f}% > {self.max_drawdown_pct:.1f}%"
            )

        # Check win rate
        if results.win_rate < self.min_win_rate:
            failures.append(f"Win rate {results.win_rate:.1f}% < {self.min_win_rate:.1f}%")

        # Check progress toward target
        progress = target_report.target_metrics.progress_to_target_pct
        if progress < self.min_progress_pct:
            failures.append(f"Target progress {progress:.1f}% < {self.min_progress_pct:.1f}%")

        passed = len(failures) == 0

        if passed:
            logger.info("✅ Backtest validation PASSED")
        else:
            logger.warning(f"❌ Backtest validation FAILED: {', '.join(failures)}")

        return passed, failures

    def generate_ci_summary(self, results: BacktestResults) -> str:
        """Generate a summary suitable for CI output."""
        target_report = evaluate_backtest_with_target(results, self.target_daily)
        passed, failures = self.validate(results)

        lines = []
        lines.append("## Backtest Target Validation")
        lines.append("")

        if passed:
            lines.append("✅ **PASSED**")
        else:
            lines.append("❌ **FAILED**")
            lines.append("")
            lines.append("### Failures:")
            for f in failures:
                lines.append(f"- {f}")

        lines.append("")
        lines.append("### Metrics:")
        lines.append(f"- Sharpe Ratio: {results.sharpe_ratio:.2f}")
        lines.append(f"- Max Drawdown: {results.max_drawdown:.1f}%")
        lines.append(f"- Win Rate: {results.win_rate:.1f}%")
        lines.append(f"- Avg Daily P&L: ${target_report.target_metrics.average_daily_pnl:.2f}")
        lines.append(
            f"- Target Progress: {target_report.target_metrics.progress_to_target_pct:.1f}%"
        )

        return "\n".join(lines)
