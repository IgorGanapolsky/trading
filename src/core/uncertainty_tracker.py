"""
Epistemic Uncertainty Tracker

Tracks and persists uncertainty metrics over time to:
1. Monitor model confidence calibration
2. Detect knowledge gaps that affect trading
3. Enable learning from past uncertainty assessments
4. Provide CEO with transparency on system limitations

Integrates with system_state.json for persistence.
"""

import json
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
UNCERTAINTY_FILE = DATA_DIR / "uncertainty_history.json"


@dataclass
class UncertaintySnapshot:
    """Single point-in-time uncertainty measurement."""

    timestamp: str
    symbol: str
    decision: str

    # Uncertainty metrics
    epistemic_score: float  # 0-100 (knowledge gaps)
    aleatoric_score: float  # 0-100 (market randomness)
    aggregate_confidence: float  # 0-1 (combined)

    # Self-consistency
    consistency_score: float  # Agreement across reasoning paths
    vote_breakdown: dict[str, int]

    # Outcome tracking (filled in later)
    trade_executed: bool = False
    actual_outcome: Optional[str] = None  # "WIN", "LOSS", "HOLD"
    outcome_pnl: Optional[float] = None

    # Introspection state
    introspection_state: str = "unknown"
    knowledge_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class UncertaintyMetrics:
    """Aggregate uncertainty metrics over time."""

    # Averages
    avg_epistemic: float = 50.0
    avg_aleatoric: float = 50.0
    avg_confidence: float = 0.5
    avg_consistency: float = 0.5

    # Calibration (how well confidence predicts outcomes)
    calibration_score: float = 0.0  # -1 to 1 (0 = perfectly calibrated)

    # Counts
    total_assessments: int = 0
    high_uncertainty_count: int = 0  # Epistemic > 60
    low_confidence_count: int = 0  # Confidence < 0.5

    # Outcome correlation
    high_conf_win_rate: float = 0.0
    low_conf_win_rate: float = 0.0
    uncertainty_outcome_correlation: float = 0.0

    # Knowledge gap analysis
    common_knowledge_gaps: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class UncertaintyTracker:
    """
    Tracks and analyzes uncertainty over time.

    Key Features:
    1. Persists all uncertainty assessments
    2. Calculates rolling metrics
    3. Correlates uncertainty with outcomes
    4. Identifies common knowledge gaps
    5. Monitors calibration quality
    """

    MAX_HISTORY = 1000  # Keep last 1000 assessments

    def __init__(self, persist: bool = True):
        """
        Initialize the tracker.

        Args:
            persist: Whether to persist to disk
        """
        self.persist = persist
        self.history: deque[UncertaintySnapshot] = deque(maxlen=self.MAX_HISTORY)
        self.metrics = UncertaintyMetrics()

        # Load existing history
        self._load_history()

    def record(
        self,
        symbol: str,
        decision: str,
        epistemic_score: float,
        aleatoric_score: float,
        aggregate_confidence: float,
        consistency_score: float,
        vote_breakdown: dict[str, int],
        introspection_state: str = "unknown",
        knowledge_gaps: Optional[list[str]] = None,
        trade_executed: bool = False,
    ) -> UncertaintySnapshot:
        """
        Record a new uncertainty assessment.

        Args:
            symbol: Ticker symbol
            decision: BUY/SELL/HOLD/SKIP
            epistemic_score: Epistemic uncertainty (0-100)
            aleatoric_score: Aleatoric uncertainty (0-100)
            aggregate_confidence: Combined confidence (0-1)
            consistency_score: Self-consistency score (0-1)
            vote_breakdown: Vote counts from self-consistency
            introspection_state: IntrospectionState value
            knowledge_gaps: List of identified knowledge gaps
            trade_executed: Whether trade was executed

        Returns:
            UncertaintySnapshot that was recorded
        """
        snapshot = UncertaintySnapshot(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            decision=decision,
            epistemic_score=epistemic_score,
            aleatoric_score=aleatoric_score,
            aggregate_confidence=aggregate_confidence,
            consistency_score=consistency_score,
            vote_breakdown=vote_breakdown,
            introspection_state=introspection_state,
            knowledge_gaps=knowledge_gaps or [],
            trade_executed=trade_executed,
        )

        self.history.append(snapshot)
        self._update_metrics()

        if self.persist:
            self._save_history()

        logger.info(
            f"Recorded uncertainty for {symbol}: "
            f"epistemic={epistemic_score:.1f}, "
            f"aleatoric={aleatoric_score:.1f}, "
            f"confidence={aggregate_confidence:.2f}"
        )

        return snapshot

    def record_outcome(
        self,
        symbol: str,
        timestamp: str,
        outcome: str,
        pnl: float,
    ) -> bool:
        """
        Record the outcome of a trade to enable calibration analysis.

        Args:
            symbol: Ticker symbol
            timestamp: Original assessment timestamp
            outcome: "WIN", "LOSS", or "HOLD"
            pnl: Realized P/L

        Returns:
            True if outcome was recorded
        """
        for snapshot in self.history:
            if snapshot.symbol == symbol and snapshot.timestamp == timestamp:
                snapshot.actual_outcome = outcome
                snapshot.outcome_pnl = pnl
                self._update_metrics()
                if self.persist:
                    self._save_history()
                return True

        logger.warning(f"Could not find assessment for {symbol} at {timestamp}")
        return False

    def get_metrics(self) -> UncertaintyMetrics:
        """Get current aggregate metrics."""
        return self.metrics

    def get_recent_history(self, n: int = 10) -> list[UncertaintySnapshot]:
        """Get n most recent assessments."""
        return list(self.history)[-n:]

    def get_symbol_history(self, symbol: str) -> list[UncertaintySnapshot]:
        """Get all assessments for a specific symbol."""
        return [s for s in self.history if s.symbol == symbol]

    def get_calibration_report(self) -> dict[str, Any]:
        """
        Generate a calibration report.

        Analyzes how well confidence predictions correlate with outcomes.
        """
        # Separate by confidence level
        high_conf = [
            s for s in self.history if s.aggregate_confidence > 0.7 and s.actual_outcome
        ]
        low_conf = [
            s for s in self.history if s.aggregate_confidence < 0.5 and s.actual_outcome
        ]
        all_with_outcomes = [s for s in self.history if s.actual_outcome]

        # Calculate win rates
        high_conf_wins = sum(1 for s in high_conf if s.actual_outcome == "WIN")
        low_conf_wins = sum(1 for s in low_conf if s.actual_outcome == "WIN")

        high_conf_win_rate = high_conf_wins / max(1, len(high_conf))
        low_conf_win_rate = low_conf_wins / max(1, len(low_conf))

        # Calibration score (good if high conf = high win rate)
        calibration_gap = high_conf_win_rate - low_conf_win_rate

        return {
            "total_assessments": len(self.history),
            "assessments_with_outcomes": len(all_with_outcomes),
            "high_confidence_trades": len(high_conf),
            "high_confidence_win_rate": high_conf_win_rate,
            "low_confidence_trades": len(low_conf),
            "low_confidence_win_rate": low_conf_win_rate,
            "calibration_gap": calibration_gap,  # Positive = well calibrated
            "is_well_calibrated": calibration_gap > 0.1,
            "recommendation": self._generate_calibration_recommendation(
                calibration_gap, high_conf_win_rate, low_conf_win_rate
            ),
        }

    def get_knowledge_gap_report(self) -> dict[str, Any]:
        """
        Analyze common knowledge gaps across assessments.

        Identifies recurring areas where the system lacks data.
        """
        gap_counts: dict[str, int] = {}

        for snapshot in self.history:
            for gap in snapshot.knowledge_gaps:
                gap_normalized = gap.lower().strip()
                gap_counts[gap_normalized] = gap_counts.get(gap_normalized, 0) + 1

        # Sort by frequency
        sorted_gaps = sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_unique_gaps": len(gap_counts),
            "top_10_gaps": sorted_gaps[:10],
            "high_epistemic_rate": (
                self.metrics.high_uncertainty_count
                / max(1, self.metrics.total_assessments)
            ),
            "recommendation": self._generate_gap_recommendation(sorted_gaps),
        }

    def _update_metrics(self) -> None:
        """Update aggregate metrics from history."""
        if not self.history:
            return

        # Calculate averages
        self.metrics.total_assessments = len(self.history)
        self.metrics.avg_epistemic = sum(s.epistemic_score for s in self.history) / len(
            self.history
        )
        self.metrics.avg_aleatoric = sum(s.aleatoric_score for s in self.history) / len(
            self.history
        )
        self.metrics.avg_confidence = sum(
            s.aggregate_confidence for s in self.history
        ) / len(self.history)
        self.metrics.avg_consistency = sum(
            s.consistency_score for s in self.history
        ) / len(self.history)

        # Count high uncertainty / low confidence
        self.metrics.high_uncertainty_count = sum(
            1 for s in self.history if s.epistemic_score > 60
        )
        self.metrics.low_confidence_count = sum(
            1 for s in self.history if s.aggregate_confidence < 0.5
        )

        # Knowledge gap aggregation
        gap_counts: dict[str, int] = {}
        for snapshot in self.history:
            for gap in snapshot.knowledge_gaps:
                gap_normalized = gap.lower().strip()
                gap_counts[gap_normalized] = gap_counts.get(gap_normalized, 0) + 1
        self.metrics.common_knowledge_gaps = dict(
            sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        # Win rate correlation (if outcomes available)
        with_outcomes = [s for s in self.history if s.actual_outcome]
        if with_outcomes:
            high_conf = [s for s in with_outcomes if s.aggregate_confidence > 0.7]
            low_conf = [s for s in with_outcomes if s.aggregate_confidence < 0.5]

            if high_conf:
                self.metrics.high_conf_win_rate = sum(
                    1 for s in high_conf if s.actual_outcome == "WIN"
                ) / len(high_conf)
            if low_conf:
                self.metrics.low_conf_win_rate = sum(
                    1 for s in low_conf if s.actual_outcome == "WIN"
                ) / len(low_conf)

            # Calibration score
            self.metrics.calibration_score = (
                self.metrics.high_conf_win_rate - self.metrics.low_conf_win_rate
            )

    def _generate_calibration_recommendation(
        self,
        gap: float,
        high_rate: float,
        low_rate: float,
    ) -> str:
        """Generate calibration recommendation."""
        if gap > 0.2:
            return "Excellent calibration: High confidence correlates with better outcomes"
        elif gap > 0.1:
            return "Good calibration: Confidence is reasonably predictive"
        elif gap > 0:
            return "Fair calibration: Confidence provides some signal"
        elif gap > -0.1:
            return "Poor calibration: Confidence does not predict outcomes well"
        else:
            return "Inverse calibration: Consider flipping confidence signals"

    def _generate_gap_recommendation(
        self,
        sorted_gaps: list[tuple[str, int]],
    ) -> str:
        """Generate knowledge gap recommendation."""
        if not sorted_gaps:
            return "No knowledge gaps identified"

        top_gap = sorted_gaps[0][0]
        return f"Most common gap: '{top_gap}' - consider adding data sources"

    def _load_history(self) -> None:
        """Load history from disk."""
        if UNCERTAINTY_FILE.exists():
            try:
                with open(UNCERTAINTY_FILE) as f:
                    data = json.load(f)

                for item in data.get("history", []):
                    snapshot = UncertaintySnapshot(**item)
                    self.history.append(snapshot)

                if data.get("metrics"):
                    self.metrics = UncertaintyMetrics(**data["metrics"])

                logger.info(
                    f"Loaded {len(self.history)} uncertainty assessments from disk"
                )
            except Exception as e:
                logger.warning(f"Failed to load uncertainty history: {e}")

    def _save_history(self) -> None:
        """Save history to disk."""
        try:
            DATA_DIR.mkdir(exist_ok=True)

            data = {
                "last_updated": datetime.now().isoformat(),
                "history": [s.to_dict() for s in self.history],
                "metrics": self.metrics.to_dict(),
            }

            with open(UNCERTAINTY_FILE, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save uncertainty history: {e}")

    def export_for_dashboard(self) -> dict[str, Any]:
        """Export data formatted for dashboard display."""
        recent = self.get_recent_history(20)

        return {
            "summary": {
                "total_assessments": self.metrics.total_assessments,
                "avg_epistemic_uncertainty": f"{self.metrics.avg_epistemic:.1f}%",
                "avg_aleatoric_uncertainty": f"{self.metrics.avg_aleatoric:.1f}%",
                "avg_confidence": f"{self.metrics.avg_confidence:.1%}",
                "calibration_status": (
                    "Good" if self.metrics.calibration_score > 0.1 else "Needs Improvement"
                ),
            },
            "recent_assessments": [
                {
                    "symbol": s.symbol,
                    "decision": s.decision,
                    "confidence": f"{s.aggregate_confidence:.1%}",
                    "epistemic": f"{s.epistemic_score:.0f}%",
                    "executed": s.trade_executed,
                    "outcome": s.actual_outcome or "pending",
                }
                for s in recent
            ],
            "calibration": self.get_calibration_report(),
            "knowledge_gaps": self.get_knowledge_gap_report(),
        }


# Singleton instance for global access
_tracker_instance: Optional[UncertaintyTracker] = None


def get_uncertainty_tracker() -> UncertaintyTracker:
    """Get the global uncertainty tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = UncertaintyTracker()
    return _tracker_instance
