"""
ML Report Generator - Produces daily ML signal reports.

This module collects gate signals during trading and generates actionable reports
that show what the ML models are actually doing.

Created: Jan 1, 2026 - Fix for ML not reporting anything useful
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports/ml_signals")


@dataclass
class GateSignal:
    """Single gate evaluation result."""

    gate_name: str
    passed: bool
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class TradeSignalRecord:
    """Complete signal record for a single trade evaluation."""

    symbol: str
    trade_id: str
    gate_1_momentum: GateSignal | None = None
    gate_2_rl: GateSignal | None = None
    gate_3_sentiment: GateSignal | None = None
    gate_4_risk: GateSignal | None = None
    overall_decision: str = "unknown"  # "execute", "reject", "hold"
    rejection_reason: str = ""
    timestamp: str = ""

    # Performance tracking (Jan 5, 2026 - Performance Attribution)
    actual_pnl: float | None = None  # Actual P&L if trade was executed
    hypothetical_pnl: float | None = None  # What would have happened if we ignored RL

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class DailyMLReport:
    """Aggregated daily ML performance report."""

    date: str
    total_evaluations: int = 0
    passed_all_gates: int = 0
    rejected: int = 0

    # Gate-level stats
    gate_1_pass_rate: float = 0.0
    gate_2_pass_rate: float = 0.0
    gate_3_pass_rate: float = 0.0
    gate_4_pass_rate: float = 0.0

    # RL-specific metrics
    avg_rl_confidence: float = 0.0
    rl_mode_distribution: dict[str, int] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)

    # Performance Attribution (Jan 5, 2026)
    # Did the RL filter actually help us make money?
    actual_total_pnl: float = 0.0  # Actual P&L with RL filtering
    hypothetical_pnl_no_rl: float = 0.0  # What we would have made ignoring RL
    rl_contribution: float = 0.0  # RL value add (can be negative if RL hurt us)
    rl_saved_from_losses: float = 0.0  # Losses avoided by RL rejections
    rl_missed_profits: float = 0.0  # Profits we missed by RL rejections

    # Top signals
    top_opportunities: list[dict] = field(default_factory=list)
    top_rejections: list[dict] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class MLReportGenerator:
    """
    Collects ML gate signals and generates daily reports.

    Usage:
        generator = MLReportGenerator()

        # Record each trade evaluation
        generator.record_signal(trade_record)

        # At end of day, generate report
        report = generator.generate_daily_report()
    """

    def __init__(self, reports_dir: Path | None = None):
        self.reports_dir = reports_dir or REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._daily_signals: list[TradeSignalRecord] = []
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"MLReportGenerator initialized: {self.reports_dir}")

    def record_signal(self, record: TradeSignalRecord) -> None:
        """Record a trade signal evaluation."""
        self._daily_signals.append(record)
        logger.debug(f"Recorded signal for {record.symbol}: {record.overall_decision}")

    def record_gate_results(
        self,
        symbol: str,
        trade_id: str,
        gate_1: dict | None = None,
        gate_2: dict | None = None,
        gate_3: dict | None = None,
        gate_4: dict | None = None,
        decision: str = "unknown",
        rejection_reason: str = "",
    ) -> TradeSignalRecord:
        """
        Convenience method to record gate results from raw dicts.

        Args:
            symbol: Stock symbol
            trade_id: Unique trade identifier
            gate_1: Momentum gate results
            gate_2: RL gate results
            gate_3: Sentiment gate results
            gate_4: Risk gate results
            decision: Overall decision (execute/reject/hold)
            rejection_reason: Why rejected (if applicable)

        Returns:
            The recorded TradeSignalRecord
        """
        record = TradeSignalRecord(
            symbol=symbol,
            trade_id=trade_id,
            gate_1_momentum=(self._dict_to_gate_signal("momentum", gate_1) if gate_1 else None),
            gate_2_rl=self._dict_to_gate_signal("rl", gate_2) if gate_2 else None,
            gate_3_sentiment=(self._dict_to_gate_signal("sentiment", gate_3) if gate_3 else None),
            gate_4_risk=self._dict_to_gate_signal("risk", gate_4) if gate_4 else None,
            overall_decision=decision,
            rejection_reason=rejection_reason,
        )
        self.record_signal(record)
        return record

    def _dict_to_gate_signal(self, gate_name: str, data: dict) -> GateSignal:
        """Convert raw dict to GateSignal."""
        return GateSignal(
            gate_name=gate_name,
            passed=data.get("passed", data.get("pass", False)),
            confidence=data.get("confidence", data.get("score", 0.0)),
            details=data,
        )

    def generate_daily_report(self, save: bool = True) -> DailyMLReport:
        """
        Generate aggregated daily report from collected signals.

        Args:
            save: Whether to save report to disk

        Returns:
            DailyMLReport with all aggregated stats
        """
        if not self._daily_signals:
            logger.warning("No signals recorded - generating empty report")
            return DailyMLReport(date=self._current_date)

        total = len(self._daily_signals)

        # Calculate pass rates
        gate_1_passed = sum(
            1 for s in self._daily_signals if s.gate_1_momentum and s.gate_1_momentum.passed
        )
        gate_2_passed = sum(1 for s in self._daily_signals if s.gate_2_rl and s.gate_2_rl.passed)
        gate_3_passed = sum(
            1 for s in self._daily_signals if s.gate_3_sentiment and s.gate_3_sentiment.passed
        )
        gate_4_passed = sum(
            1 for s in self._daily_signals if s.gate_4_risk and s.gate_4_risk.passed
        )

        passed_all = sum(1 for s in self._daily_signals if s.overall_decision == "execute")
        rejected = sum(1 for s in self._daily_signals if s.overall_decision == "reject")

        # RL confidence stats
        rl_confidences = [
            s.gate_2_rl.confidence
            for s in self._daily_signals
            if s.gate_2_rl and s.gate_2_rl.confidence > 0
        ]
        avg_rl_conf = sum(rl_confidences) / len(rl_confidences) if rl_confidences else 0.0

        # RL mode distribution
        mode_dist: dict[str, int] = {}
        for s in self._daily_signals:
            if s.gate_2_rl and s.gate_2_rl.details:
                mode = s.gate_2_rl.details.get("mode", "unknown")
                mode_dist[mode] = mode_dist.get(mode, 0) + 1

        # Feature importance (aggregate from RL details)
        feature_sums: dict[str, float] = {}
        feature_counts: dict[str, int] = {}
        for s in self._daily_signals:
            if s.gate_2_rl and s.gate_2_rl.details:
                importance = s.gate_2_rl.details.get("feature_importance", {})
                for feat, val in importance.items():
                    if isinstance(val, (int, float)):
                        feature_sums[feat] = feature_sums.get(feat, 0.0) + val
                        feature_counts[feat] = feature_counts.get(feat, 0) + 1

        avg_importance = {
            feat: feature_sums[feat] / feature_counts[feat]
            for feat in feature_sums
            if feature_counts.get(feat, 0) > 0
        }

        # Top opportunities (highest confidence executions)
        executed = [s for s in self._daily_signals if s.overall_decision == "execute"]
        executed.sort(key=lambda x: x.gate_2_rl.confidence if x.gate_2_rl else 0, reverse=True)
        top_opps = [
            {
                "symbol": s.symbol,
                "confidence": s.gate_2_rl.confidence if s.gate_2_rl else 0,
                "momentum": s.gate_1_momentum.confidence if s.gate_1_momentum else 0,
            }
            for s in executed[:5]
        ]

        # Top rejections (why trades were blocked)
        rejections = [s for s in self._daily_signals if s.overall_decision == "reject"]
        rejection_reasons: dict[str, int] = {}
        for s in rejections:
            reason = s.rejection_reason or "unknown"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        top_rejections = [
            {"reason": r, "count": c}
            for r, c in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Performance Attribution (Jan 5, 2026)
        # Calculate RL contribution to profitability
        actual_pnl = sum(s.actual_pnl for s in self._daily_signals if s.actual_pnl is not None)
        hypothetical_pnl = sum(
            s.hypothetical_pnl for s in self._daily_signals if s.hypothetical_pnl is not None
        )

        # RL rejections that would have been losses (RL saved us)
        rl_saved = sum(
            s.hypothetical_pnl
            for s in self._daily_signals
            if s.overall_decision == "reject"
            and s.gate_1_momentum
            and s.gate_1_momentum.passed  # Gate 1 passed but RL rejected
            and s.hypothetical_pnl is not None
            and s.hypothetical_pnl < 0  # Would have been a loss
        )

        # RL rejections that would have been profits (RL cost us)
        rl_missed = sum(
            s.hypothetical_pnl
            for s in self._daily_signals
            if s.overall_decision == "reject"
            and s.gate_1_momentum
            and s.gate_1_momentum.passed  # Gate 1 passed but RL rejected
            and s.hypothetical_pnl is not None
            and s.hypothetical_pnl > 0  # Would have been a profit
        )

        rl_contribution = actual_pnl - hypothetical_pnl

        # Generate recommendations
        recommendations = self._generate_recommendations(
            gate_1_rate=gate_1_passed / total if total > 0 else 0,
            gate_2_rate=gate_2_passed / total if total > 0 else 0,
            avg_rl_conf=avg_rl_conf,
            rejection_reasons=rejection_reasons,
            rl_contribution=rl_contribution,
        )

        report = DailyMLReport(
            date=self._current_date,
            total_evaluations=total,
            passed_all_gates=passed_all,
            rejected=rejected,
            gate_1_pass_rate=gate_1_passed / total if total > 0 else 0,
            gate_2_pass_rate=gate_2_passed / total if total > 0 else 0,
            gate_3_pass_rate=gate_3_passed / total if total > 0 else 0,
            gate_4_pass_rate=gate_4_passed / total if total > 0 else 0,
            avg_rl_confidence=avg_rl_conf,
            rl_mode_distribution=mode_dist,
            feature_importance=avg_importance,
            # Performance attribution
            actual_total_pnl=actual_pnl,
            hypothetical_pnl_no_rl=hypothetical_pnl,
            rl_contribution=rl_contribution,
            rl_saved_from_losses=abs(rl_saved),  # Positive number = amount saved
            rl_missed_profits=rl_missed,  # Positive number = profits we missed
            # Signals
            top_opportunities=top_opps,
            top_rejections=top_rejections,
            recommendations=recommendations,
        )

        if save:
            self._save_report(report)

        logger.info(
            f"ML Report generated: {total} evaluations, "
            f"{passed_all} executed, {rejected} rejected, "
            f"avg RL confidence: {avg_rl_conf:.2%}"
        )

        return report

    def _generate_recommendations(
        self,
        gate_1_rate: float,
        gate_2_rate: float,
        avg_rl_conf: float,
        rejection_reasons: dict[str, int],
        rl_contribution: float = 0.0,
    ) -> list[str]:
        """Generate actionable recommendations based on stats and performance attribution."""
        recs = []

        # CRITICAL: Performance Attribution (Jan 5, 2026)
        if rl_contribution < -50:  # RL cost us $50+ in profits
            recs.append(
                f"🚨 RL HURTING PERFORMANCE: Cost us ${abs(rl_contribution):.2f} today - consider disabling"
            )
        elif rl_contribution > 50:  # RL saved us $50+
            recs.append(
                f"✅ RL ADDING VALUE: Contributed +${rl_contribution:.2f} today - keep enabled"
            )
        elif -50 <= rl_contribution <= 50 and abs(rl_contribution) > 0:
            recs.append(f"⚠️ RL MARGINAL: Contributed ${rl_contribution:+.2f} - monitor closely")

        if gate_1_rate < 0.3:
            recs.append("Gate 1 (Momentum) pass rate low - consider relaxing technical filters")

        if gate_2_rate < 0.5:
            recs.append("Gate 2 (RL) pass rate low - RL model may need retraining")

        if avg_rl_conf < 0.5:
            recs.append("Average RL confidence low - check feature engineering")

        if avg_rl_conf > 0.85:
            recs.append("RL confidence very high - may be overfitting, validate with backtest")

        # Check top rejection reason
        if rejection_reasons:
            top_reason = max(rejection_reasons.items(), key=lambda x: x[1])
            if top_reason[1] > 5:
                recs.append(
                    f"Frequent rejection: '{top_reason[0]}' ({top_reason[1]}x) - investigate"
                )

        if not recs:
            recs.append("System operating normally - no immediate action needed")

        return recs

    def _save_report(self, report: DailyMLReport) -> Path:
        """Save report to JSON file."""
        filepath = self.reports_dir / f"ml_report_{report.date}.json"

        # Convert dataclasses to dicts
        data = asdict(report)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"ML report saved: {filepath}")
        return filepath

    def load_report(self, date: str) -> DailyMLReport | None:
        """Load a saved report by date."""
        filepath = self.reports_dir / f"ml_report_{date}.json"
        if not filepath.exists():
            return None

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        return DailyMLReport(**data)

    def get_recent_reports(self, days: int = 7) -> list[DailyMLReport]:
        """Get reports from the last N days."""
        reports = []
        for filepath in sorted(self.reports_dir.glob("ml_report_*.json"), reverse=True)[:days]:
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                reports.append(DailyMLReport(**data))
            except Exception as e:
                logger.warning(f"Failed to load report {filepath}: {e}")
        return reports

    def reset_daily(self) -> None:
        """Reset for a new trading day."""
        self._daily_signals = []
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"MLReportGenerator reset for {self._current_date}")


# Singleton instance
_generator: MLReportGenerator | None = None


def get_ml_report_generator() -> MLReportGenerator:
    """Get or create singleton MLReportGenerator instance."""
    global _generator
    if _generator is None:
        _generator = MLReportGenerator()
    return _generator


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    gen = get_ml_report_generator()

    # Simulate some trade evaluations
    gen.record_gate_results(
        symbol="SPY",
        trade_id="SPY-001",
        gate_1={"passed": True, "confidence": 0.72, "strength": 0.65},
        gate_2={
            "passed": True,
            "confidence": 0.68,
            "mode": "transformer",
            "feature_importance": {"strength": 0.35, "momentum": 0.28},
        },
        gate_3={"passed": True, "confidence": 0.55},
        gate_4={"passed": True, "confidence": 0.9},
        decision="execute",
    )

    gen.record_gate_results(
        symbol="TSLA",
        trade_id="TSLA-001",
        gate_1={"passed": True, "confidence": 0.58},
        gate_2={"passed": False, "confidence": 0.32, "mode": "heuristic"},
        decision="reject",
        rejection_reason="RL confidence below threshold",
    )

    gen.record_gate_results(
        symbol="NVDA",
        trade_id="NVDA-001",
        gate_1={"passed": False, "confidence": 0.25},
        decision="reject",
        rejection_reason="Momentum too weak",
    )

    # Generate report
    report = gen.generate_daily_report()

    print("\n=== ML DAILY REPORT ===")
    print(f"Date: {report.date}")
    print(f"Total Evaluations: {report.total_evaluations}")
    print(f"Executed: {report.passed_all_gates}")
    print(f"Rejected: {report.rejected}")
    print("\nGate Pass Rates:")
    print(f"  Gate 1 (Momentum): {report.gate_1_pass_rate:.1%}")
    print(f"  Gate 2 (RL): {report.gate_2_pass_rate:.1%}")
    print(f"  Gate 3 (Sentiment): {report.gate_3_pass_rate:.1%}")
    print(f"  Gate 4 (Risk): {report.gate_4_pass_rate:.1%}")
    print(f"\nAvg RL Confidence: {report.avg_rl_confidence:.1%}")
    print(f"RL Mode Distribution: {report.rl_mode_distribution}")
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")
