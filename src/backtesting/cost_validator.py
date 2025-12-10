"""
Cost Validator - Forward Test Validation

Compares backtest execution cost predictions against live Alpaca fills
to validate that our slippage model matches reality.

Weekly Validation Process:
1. Load live fills from ExecutionCostTracker (last 7 days)
2. Run backtest simulation over same period with same trades
3. Compare average slippage/costs
4. Alert if divergence > 2 bps
5. Recommend model recalibration if divergence persists

This ensures our backtests remain realistic and don't overestimate
profitability due to optimistic cost assumptions.

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Validation results storage
VALIDATION_RESULTS_PATH = Path("data/cost_validation_history.json")


@dataclass
class ValidationReport:
    """Results from cost validation comparison."""

    validation_date: str
    period_start: str
    period_end: str

    # Live execution metrics
    live_trade_count: int
    live_avg_slippage_bps: float
    live_total_slippage_cost: float

    # Backtest metrics (using same trades)
    backtest_avg_slippage_bps: float
    backtest_total_slippage_cost: float

    # Comparison
    divergence_bps: float  # live - backtest (positive = live worse than expected)
    divergence_pct: float  # divergence as % of backtest prediction
    model_accurate: bool  # True if divergence < threshold

    # Recommendations
    status: str  # "EXCELLENT", "GOOD", "ACCEPTABLE", "NEEDS_RECALIBRATION"
    recommendation: str
    action_required: bool

    # Symbol breakdown
    symbol_divergences: dict[str, float]  # Per-symbol divergence

    # Historical context
    rolling_7day_divergence: Optional[float] = None
    divergence_trend: Optional[str] = None  # "improving", "stable", "worsening"


@dataclass
class CostComparison:
    """Comparison of a single trade's costs."""

    symbol: str
    trade_date: str
    side: str
    notional: float

    # Live fill data
    live_slippage_bps: float

    # Backtest prediction
    backtest_slippage_bps: float

    # Divergence
    divergence_bps: float


class CostValidator:
    """
    Validates backtest cost assumptions against live execution data.

    The key insight is that our backtest slippage model makes assumptions
    about execution costs. If those assumptions are wrong, our backtest
    results will be misleading. This validator catches model drift.

    Example:
        validator = CostValidator()

        # Run weekly validation
        report = validator.validate_weekly()

        if report.action_required:
            print(f"WARNING: {report.recommendation}")
            recalibrate_slippage_model(report)
    """

    # Divergence thresholds
    EXCELLENT_THRESHOLD = 1.0  # bps
    GOOD_THRESHOLD = 2.0  # bps
    ACCEPTABLE_THRESHOLD = 5.0  # bps

    def __init__(
        self,
        cost_tracker_path: Optional[Path] = None,
        results_path: Optional[Path] = None,
    ):
        """
        Initialize the cost validator.

        Args:
            cost_tracker_path: Path to execution costs JSON
            results_path: Path to store validation results
        """
        self.cost_tracker_path = cost_tracker_path or Path("data/execution_costs.json")
        self.results_path = results_path or VALIDATION_RESULTS_PATH
        self.validation_history: list[ValidationReport] = []
        self._load_history()

        logger.info("CostValidator initialized")

    def _load_history(self) -> None:
        """Load historical validation results."""
        if self.results_path.exists():
            try:
                with open(self.results_path) as f:
                    data = json.load(f)
                self.validation_history = [
                    ValidationReport(**r) for r in data.get("validations", [])
                ]
                logger.info(f"Loaded {len(self.validation_history)} validation records")
            except Exception as e:
                logger.warning(f"Failed to load validation history: {e}")
                self.validation_history = []

    def _save_history(self) -> None:
        """Persist validation history."""
        self.results_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "validations": [asdict(v) for v in self.validation_history],
            "last_updated": datetime.now().isoformat(),
        }

        with open(self.results_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_live_fills(self, days: int = 7) -> list[dict]:
        """
        Load live fills from the ExecutionCostTracker.

        Args:
            days: Number of days to look back

        Returns:
            List of fill records
        """
        if not self.cost_tracker_path.exists():
            logger.warning(f"No execution costs file at {self.cost_tracker_path}")
            return []

        try:
            with open(self.cost_tracker_path) as f:
                data = json.load(f)

            fills = data.get("fills", [])

            # Filter to last N days
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            recent_fills = [f for f in fills if f["timestamp"] >= cutoff]

            logger.info(f"Loaded {len(recent_fills)} fills from last {days} days")
            return recent_fills

        except Exception as e:
            logger.error(f"Failed to load live fills: {e}")
            return []

    def _get_backtest_slippage(
        self,
        symbol: str,
        price: float,
        quantity: float,
        side: str,
    ) -> float:
        """
        Calculate what the backtest slippage model would predict.

        Args:
            symbol: Ticker symbol
            price: Base price
            quantity: Trade quantity
            side: "buy" or "sell"

        Returns:
            Predicted slippage in basis points
        """
        try:
            from src.risk.slippage_model import SlippageModel, SlippageModelType

            model = SlippageModel(
                model_type=SlippageModelType.COMPREHENSIVE,
                base_spread_bps=5.0,
                market_impact_bps=10.0,
                latency_ms=100.0,
            )

            result = model.calculate_slippage(
                price=price,
                quantity=quantity,
                side=side,
                symbol=symbol,
            )

            return result.slippage_bps

        except Exception as e:
            logger.warning(f"Failed to get backtest slippage: {e}")
            return 5.0  # Default assumption

    def compare_trade(self, fill: dict) -> CostComparison:
        """
        Compare a single fill against backtest prediction.

        Args:
            fill: Fill record from ExecutionCostTracker

        Returns:
            CostComparison with divergence analysis
        """
        symbol = fill["symbol"]
        side = fill["side"]
        quantity = fill["quantity"]
        expected_price = fill["expected_price"]
        live_slippage_bps = fill["slippage_bps"]

        # Get what backtest would have predicted
        backtest_slippage_bps = self._get_backtest_slippage(
            symbol=symbol,
            price=expected_price,
            quantity=quantity,
            side=side,
        )

        divergence_bps = live_slippage_bps - backtest_slippage_bps

        return CostComparison(
            symbol=symbol,
            trade_date=fill["timestamp"][:10],  # Just the date part
            side=side,
            notional=fill["notional"],
            live_slippage_bps=live_slippage_bps,
            backtest_slippage_bps=backtest_slippage_bps,
            divergence_bps=divergence_bps,
        )

    def validate_weekly(self, days: int = 7) -> ValidationReport:
        """
        Run weekly validation comparing live vs backtest costs.

        Args:
            days: Number of days to analyze

        Returns:
            ValidationReport with detailed comparison
        """
        logger.info(f"Running weekly cost validation for last {days} days")

        # Load live fills
        fills = self._load_live_fills(days=days)

        if not fills:
            return ValidationReport(
                validation_date=datetime.now().isoformat(),
                period_start=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
                period_end=datetime.now().strftime("%Y-%m-%d"),
                live_trade_count=0,
                live_avg_slippage_bps=0.0,
                live_total_slippage_cost=0.0,
                backtest_avg_slippage_bps=0.0,
                backtest_total_slippage_cost=0.0,
                divergence_bps=0.0,
                divergence_pct=0.0,
                model_accurate=True,
                status="NO_DATA",
                recommendation="No live fills in period. Continue paper trading to gather data.",
                action_required=False,
                symbol_divergences={},
            )

        # Compare each fill
        comparisons = [self.compare_trade(fill) for fill in fills]

        # Calculate aggregates
        live_avg_slippage = sum(c.live_slippage_bps for c in comparisons) / len(comparisons)
        backtest_avg_slippage = sum(c.backtest_slippage_bps for c in comparisons) / len(comparisons)
        avg_divergence = sum(c.divergence_bps for c in comparisons) / len(comparisons)

        # Total costs
        live_total_cost = sum(fill["slippage_cost"] for fill in fills)

        # Estimate backtest total cost (scale by ratio)
        if live_avg_slippage > 0:
            backtest_total_cost = live_total_cost * (backtest_avg_slippage / live_avg_slippage)
        else:
            backtest_total_cost = 0.0

        # Per-symbol breakdown
        symbol_divergences: dict[str, list[float]] = {}
        for c in comparisons:
            if c.symbol not in symbol_divergences:
                symbol_divergences[c.symbol] = []
            symbol_divergences[c.symbol].append(c.divergence_bps)

        symbol_avg_divergences = {
            sym: sum(divs) / len(divs) for sym, divs in symbol_divergences.items()
        }

        # Determine status
        abs_divergence = abs(avg_divergence)
        if abs_divergence <= self.EXCELLENT_THRESHOLD:
            status = "EXCELLENT"
            model_accurate = True
        elif abs_divergence <= self.GOOD_THRESHOLD:
            status = "GOOD"
            model_accurate = True
        elif abs_divergence <= self.ACCEPTABLE_THRESHOLD:
            status = "ACCEPTABLE"
            model_accurate = True
        else:
            status = "NEEDS_RECALIBRATION"
            model_accurate = False

        # Generate recommendation
        recommendation = self._generate_recommendation(
            avg_divergence=avg_divergence,
            status=status,
            symbol_divergences=symbol_avg_divergences,
        )

        # Calculate divergence percentage
        divergence_pct = (
            (abs_divergence / backtest_avg_slippage * 100)
            if backtest_avg_slippage > 0
            else 0.0
        )

        # Calculate trend from history
        rolling_divergence, trend = self._calculate_trend(avg_divergence)

        report = ValidationReport(
            validation_date=datetime.now().isoformat(),
            period_start=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
            period_end=datetime.now().strftime("%Y-%m-%d"),
            live_trade_count=len(fills),
            live_avg_slippage_bps=round(live_avg_slippage, 2),
            live_total_slippage_cost=round(live_total_cost, 2),
            backtest_avg_slippage_bps=round(backtest_avg_slippage, 2),
            backtest_total_slippage_cost=round(backtest_total_cost, 2),
            divergence_bps=round(avg_divergence, 2),
            divergence_pct=round(divergence_pct, 1),
            model_accurate=model_accurate,
            status=status,
            recommendation=recommendation,
            action_required=not model_accurate,
            symbol_divergences={s: round(d, 2) for s, d in symbol_avg_divergences.items()},
            rolling_7day_divergence=rolling_divergence,
            divergence_trend=trend,
        )

        # Save to history
        self.validation_history.append(report)
        self._save_history()

        # Log results
        logger.info(f"Cost Validation Complete: {status}")
        logger.info(
            f"  Live avg: {live_avg_slippage:.2f} bps, "
            f"Backtest avg: {backtest_avg_slippage:.2f} bps, "
            f"Divergence: {avg_divergence:.2f} bps"
        )

        if not model_accurate:
            logger.warning(f"MODEL RECALIBRATION NEEDED: {recommendation}")

        return report

    def _generate_recommendation(
        self,
        avg_divergence: float,
        status: str,
        symbol_divergences: dict[str, float],
    ) -> str:
        """Generate actionable recommendation based on validation results."""
        if status == "EXCELLENT":
            return "Slippage model matches live execution excellently. No action needed."

        if status == "GOOD":
            return "Slippage model is performing well. Continue monitoring."

        if status == "ACCEPTABLE":
            # Identify worst symbols
            worst_symbols = sorted(
                symbol_divergences.items(), key=lambda x: abs(x[1]), reverse=True
            )[:3]
            worst_str = ", ".join(f"{s}: {d:+.1f}bps" for s, d in worst_symbols)
            return f"Model acceptable but drifting. Worst symbols: {worst_str}"

        # NEEDS_RECALIBRATION
        if avg_divergence > 0:
            return (
                f"Model UNDERESTIMATES slippage by {avg_divergence:.1f} bps. "
                "INCREASE base_spread_bps in SlippageModel to match reality. "
                "Backtests may be too optimistic."
            )
        else:
            return (
                f"Model OVERESTIMATES slippage by {abs(avg_divergence):.1f} bps. "
                "Model is conservative (safe). Consider DECREASING base_spread_bps "
                "for tighter backtest estimates."
            )

    def _calculate_trend(
        self, current_divergence: float
    ) -> tuple[Optional[float], Optional[str]]:
        """Calculate rolling divergence and trend from history."""
        if len(self.validation_history) < 2:
            return None, None

        # Get last 4 validations (approximately 1 month of weekly validations)
        recent = self.validation_history[-4:]
        rolling_avg = sum(v.divergence_bps for v in recent) / len(recent)

        # Compare current to rolling average
        if len(self.validation_history) >= 4:
            older = self.validation_history[-8:-4] if len(self.validation_history) >= 8 else self.validation_history[:4]
            older_avg = sum(v.divergence_bps for v in older) / len(older)

            diff = rolling_avg - older_avg
            if diff < -0.5:
                trend = "improving"
            elif diff > 0.5:
                trend = "worsening"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return round(rolling_avg, 2), trend

    def get_calibration_suggestion(self) -> dict[str, Any]:
        """
        Get suggested slippage model parameters based on live data.

        Returns:
            Dict with suggested parameters and confidence
        """
        fills = self._load_live_fills(days=30)  # Use 30 days for calibration

        if len(fills) < 10:
            return {
                "error": f"Insufficient data ({len(fills)} fills). Need at least 10.",
                "confidence": 0.0,
            }

        # Group by symbol and calculate average slippage
        symbol_slippages: dict[str, list[float]] = {}
        for fill in fills:
            symbol = fill["symbol"]
            if symbol not in symbol_slippages:
                symbol_slippages[symbol] = []
            symbol_slippages[symbol].append(fill["slippage_bps"])

        # Calculate overall average
        all_slippages = [fill["slippage_bps"] for fill in fills]
        avg_slippage = sum(all_slippages) / len(all_slippages)

        # Calculate 75th percentile for conservative estimate
        sorted_slippages = sorted(all_slippages)
        p75_index = int(len(sorted_slippages) * 0.75)
        p75_slippage = sorted_slippages[p75_index]

        # Confidence based on sample size
        confidence = min(1.0, len(fills) / 50)  # Max confidence at 50+ fills

        return {
            "suggested_base_spread_bps": round(avg_slippage, 1),
            "conservative_base_spread_bps": round(p75_slippage, 1),
            "sample_size": len(fills),
            "confidence": round(confidence, 2),
            "symbol_breakdown": {
                sym: round(sum(slips) / len(slips), 1)
                for sym, slips in symbol_slippages.items()
            },
            "recommendation": (
                f"Based on {len(fills)} live fills, suggest base_spread_bps = "
                f"{p75_slippage:.1f} (conservative) or {avg_slippage:.1f} (average)."
            ),
        }

    def generate_weekly_report(self) -> str:
        """Generate a formatted weekly validation report."""
        report = self.validate_weekly()

        lines = [
            "=" * 70,
            "WEEKLY COST VALIDATION REPORT",
            f"Period: {report.period_start} to {report.period_end}",
            f"Generated: {report.validation_date}",
            "=" * 70,
            "",
            f"Status: {report.status}",
            f"Model Accurate: {'YES' if report.model_accurate else 'NO'}",
            "",
            "EXECUTION COSTS COMPARISON",
            "-" * 40,
            f"  Live Trades:           {report.live_trade_count}",
            f"  Live Avg Slippage:     {report.live_avg_slippage_bps:.2f} bps",
            f"  Backtest Avg Slippage: {report.backtest_avg_slippage_bps:.2f} bps",
            f"  Divergence:            {report.divergence_bps:+.2f} bps ({report.divergence_pct:.1f}%)",
            "",
            f"  Live Total Cost:       ${report.live_total_slippage_cost:.2f}",
            f"  Backtest Est. Cost:    ${report.backtest_total_slippage_cost:.2f}",
            "",
        ]

        if report.symbol_divergences:
            lines.append("PER-SYMBOL BREAKDOWN")
            lines.append("-" * 40)
            for symbol, div in sorted(
                report.symbol_divergences.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            ):
                status_icon = "⚠️" if abs(div) > 3 else "✓"
                lines.append(f"  {symbol}: {div:+.2f} bps {status_icon}")
            lines.append("")

        if report.divergence_trend:
            lines.append("TREND ANALYSIS")
            lines.append("-" * 40)
            lines.append(f"  Rolling 7-day divergence: {report.rolling_7day_divergence:.2f} bps")
            lines.append(f"  Trend: {report.divergence_trend.upper()}")
            lines.append("")

        lines.append("RECOMMENDATION")
        lines.append("-" * 40)
        lines.append(f"  {report.recommendation}")
        lines.append("")

        if report.action_required:
            lines.append("⚠️  ACTION REQUIRED: Model recalibration recommended")
        else:
            lines.append("✓ No action required")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


# Convenience function
def get_cost_validator() -> CostValidator:
    """Get a cost validator instance."""
    return CostValidator()


def run_weekly_validation() -> ValidationReport:
    """Run weekly validation and return report."""
    validator = get_cost_validator()
    return validator.validate_weekly()


# CLI entry point
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    validator = CostValidator()
    print(validator.generate_weekly_report())
