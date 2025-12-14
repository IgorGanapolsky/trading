"""Cross-Incident Pattern Recurrence Detector.

Detects when the same type of mistake is happening repeatedly (recurring patterns).
Analyzes anomaly frequency, temporal clustering, and escalating severity.

Key Features:
1. Temporal clustering detection (patterns recurring every 2-5 days)
2. Severity escalation (LOW → MEDIUM → HIGH → CRITICAL)
3. RAG integration for prevention suggestions
4. GitHub issue auto-creation for critical patterns
5. Trend analysis (increasing/decreasing frequency)

Usage:
    detector = PatternRecurrenceDetector(recurrence_threshold=3, window_days=7)

    # Analyze patterns
    report = detector.analyze_patterns()
    print(f"Found {len(report['recurring_patterns'])} recurring patterns")

    # Get only recurring patterns
    patterns = detector.get_recurring_patterns()

    # Escalate a specific pattern
    detector.escalate_pattern("order_amount")

Author: Trading System
Created: 2025-12-11
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Constants
ANOMALY_LOG_PATH = Path("data/anomaly_log.json")
PATTERN_REPORT_PATH = Path("data/pattern_recurrence_report.json")
RAG_LESSONS_PATH = Path("data/rag/lessons_learned.json")


@dataclass
class RecurringPattern:
    """A detected recurring pattern."""

    pattern_type: str  # Anomaly type (e.g., "order_amount", "data_staleness")
    count: int  # Total occurrences
    first_seen: str  # ISO timestamp
    last_seen: str  # ISO timestamp
    frequency_days: float  # Average days between occurrences
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    trend: str  # "increasing", "stable", "decreasing"
    prevention: Optional[str] = None  # RAG-sourced prevention suggestion
    occurrences: list[dict[str, Any]] = None  # Individual occurrences

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_type": self.pattern_type,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "frequency_days": round(self.frequency_days, 2),
            "severity": self.severity,
            "trend": self.trend,
            "prevention": self.prevention,
            "occurrences": self.occurrences or [],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecurringPattern:
        """Create from dictionary."""
        return cls(
            pattern_type=data["pattern_type"],
            count=data["count"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            frequency_days=data["frequency_days"],
            severity=data["severity"],
            trend=data["trend"],
            prevention=data.get("prevention"),
            occurrences=data.get("occurrences", []),
        )


class PatternRecurrenceDetector:
    """
    Detects recurring patterns in anomaly logs.

    Analyzes:
    - Frequency: How often does this pattern occur?
    - Temporal clustering: Are occurrences clustered (every 2-5 days)?
    - Trend: Is the pattern increasing, stable, or decreasing?
    - Severity: How critical is this pattern based on recurrence?

    Severity Levels:
    - LOW: 2-3 occurrences in window
    - MEDIUM: 4-6 occurrences in window
    - HIGH: 7-10 occurrences in window
    - CRITICAL: >10 occurrences in window
    """

    def __init__(
        self,
        recurrence_threshold: int = 3,
        window_days: int = 7,
        clustering_threshold_days: int = 5,
    ):
        """
        Initialize the pattern recurrence detector.

        Args:
            recurrence_threshold: Minimum occurrences to consider a pattern
            window_days: Look back window in days
            clustering_threshold_days: Flag patterns recurring every N days
        """
        self.recurrence_threshold = recurrence_threshold
        self.window_days = window_days
        self.clustering_threshold_days = clustering_threshold_days
        self.anomalies: list[dict] = []
        self.patterns: list[RecurringPattern] = []

        # Load anomalies
        self._load_anomalies()

    def _load_anomalies(self) -> None:
        """Load anomaly history from disk."""
        if not ANOMALY_LOG_PATH.exists():
            logger.warning(f"Anomaly log not found: {ANOMALY_LOG_PATH}")
            self.anomalies = []
            return

        try:
            with open(ANOMALY_LOG_PATH) as f:
                data = json.load(f)
                self.anomalies = data.get("anomalies", [])
                logger.info(f"Loaded {len(self.anomalies)} anomalies from log")
        except Exception as e:
            logger.error(f"Failed to load anomalies: {e}")
            self.anomalies = []

    def _filter_by_window(self, anomalies: list[dict]) -> list[dict]:
        """Filter anomalies to only those within the time window."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        filtered = []
        for anomaly in anomalies:
            try:
                detected_at = datetime.fromisoformat(anomaly["detected_at"].replace("Z", "+00:00"))
                if detected_at >= cutoff:
                    filtered.append(anomaly)
            except Exception as e:
                logger.warning(f"Invalid timestamp in anomaly: {e}")
                continue

        return filtered

    def _group_by_type(self, anomalies: list[dict]) -> dict[str, list[dict]]:
        """Group anomalies by type."""
        groups = defaultdict(list)
        for anomaly in anomalies:
            anomaly_type = anomaly.get("type", "unknown")
            groups[anomaly_type].append(anomaly)
        return dict(groups)

    def _calculate_frequency(self, occurrences: list[dict]) -> float:
        """Calculate average days between occurrences."""
        if len(occurrences) < 2:
            return 0.0

        timestamps = []
        for occ in occurrences:
            try:
                ts = datetime.fromisoformat(occ["detected_at"].replace("Z", "+00:00"))
                timestamps.append(ts)
            except Exception:
                continue

        if len(timestamps) < 2:
            return 0.0

        # Sort timestamps
        timestamps.sort()

        # Calculate time deltas
        deltas = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds() / 86400  # days
            deltas.append(delta)

        # Return average
        return np.mean(deltas) if deltas else 0.0

    def _determine_severity(self, count: int) -> str:
        """Determine severity based on recurrence count."""
        if count <= 3:
            return "LOW"
        elif count <= 6:
            return "MEDIUM"
        elif count <= 10:
            return "HIGH"
        else:
            return "CRITICAL"

    def _analyze_trend(self, occurrences: list[dict]) -> str:
        """
        Analyze if pattern is increasing, stable, or decreasing.

        Compares first half vs second half of the window.
        """
        if len(occurrences) < 4:
            return "stable"

        # Sort by timestamp
        sorted_occs = sorted(
            occurrences,
            key=lambda x: datetime.fromisoformat(x["detected_at"].replace("Z", "+00:00")),
        )

        # Split in half
        midpoint = len(sorted_occs) // 2
        first_half_count = midpoint
        second_half_count = len(sorted_occs) - midpoint

        # Calculate rate per day for each half
        first_ts = datetime.fromisoformat(sorted_occs[0]["detected_at"].replace("Z", "+00:00"))
        mid_ts = datetime.fromisoformat(sorted_occs[midpoint]["detected_at"].replace("Z", "+00:00"))
        last_ts = datetime.fromisoformat(sorted_occs[-1]["detected_at"].replace("Z", "+00:00"))

        first_half_days = max((mid_ts - first_ts).total_seconds() / 86400, 1)
        second_half_days = max((last_ts - mid_ts).total_seconds() / 86400, 1)

        first_half_rate = first_half_count / first_half_days
        second_half_rate = second_half_count / second_half_days

        # Determine trend
        if second_half_rate > first_half_rate * 1.5:
            return "increasing"
        elif second_half_rate < first_half_rate * 0.67:
            return "decreasing"
        else:
            return "stable"

    def _get_prevention_suggestion(self, pattern_type: str) -> Optional[str]:
        """
        Query RAG for prevention suggestions.

        Args:
            pattern_type: Anomaly type

        Returns:
            Prevention suggestion from RAG or None
        """
        # Try to load RAG lessons
        if not RAG_LESSONS_PATH.exists():
            logger.debug("RAG lessons not found, skipping prevention lookup")
            return None

        try:
            with open(RAG_LESSONS_PATH) as f:
                data = json.load(f)
                lessons = data.get("lessons", [])

            # Search for relevant lessons
            for lesson in lessons:
                # Match by category or tags
                category = lesson.get("category", "")
                tags = lesson.get("tags", [])

                if pattern_type in category or pattern_type in tags:
                    return lesson.get("prevention", "No prevention suggestion available")

            # Generic fallback
            return "Review anomaly log and implement targeted prevention measures"

        except Exception as e:
            logger.warning(f"Failed to query RAG: {e}")
            return None

    def analyze_patterns(self) -> dict[str, Any]:
        """
        Analyze all patterns and generate comprehensive report.

        Returns:
            Dictionary with:
            - recurring_patterns: List of RecurringPattern objects
            - total_anomalies: Total anomalies in window
            - unique_types: Number of unique anomaly types
            - critical_patterns: Patterns requiring immediate attention
            - generated_at: ISO timestamp
        """
        # Filter to window
        windowed = self._filter_by_window(self.anomalies)

        # Group by type
        groups = self._group_by_type(windowed)

        # Analyze each group
        self.patterns = []
        for pattern_type, occurrences in groups.items():
            count = len(occurrences)

            # Skip if below threshold
            if count < self.recurrence_threshold:
                continue

            # Calculate metrics
            frequency = self._calculate_frequency(occurrences)
            severity = self._determine_severity(count)
            trend = self._analyze_trend(occurrences)
            prevention = self._get_prevention_suggestion(pattern_type)

            # Get first and last timestamps
            timestamps = [
                datetime.fromisoformat(occ["detected_at"].replace("Z", "+00:00"))
                for occ in occurrences
            ]
            first_seen = min(timestamps).isoformat()
            last_seen = max(timestamps).isoformat()

            # Create pattern
            pattern = RecurringPattern(
                pattern_type=pattern_type,
                count=count,
                first_seen=first_seen,
                last_seen=last_seen,
                frequency_days=frequency,
                severity=severity,
                trend=trend,
                prevention=prevention,
                occurrences=occurrences,
            )

            self.patterns.append(pattern)

            # Flag clustering patterns
            if 0 < frequency <= self.clustering_threshold_days:
                logger.warning(
                    f"CLUSTERING DETECTED: {pattern_type} recurring every "
                    f"{frequency:.1f} days (threshold: {self.clustering_threshold_days})"
                )

        # Sort by severity then count
        severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        self.patterns.sort(key=lambda p: (severity_order.get(p.severity, 0), p.count), reverse=True)

        # Generate report
        report = {
            "recurring_patterns": [p.to_dict() for p in self.patterns],
            "total_anomalies": len(windowed),
            "unique_types": len(groups),
            "critical_patterns": [p.to_dict() for p in self.patterns if p.severity == "CRITICAL"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": self.window_days,
            "recurrence_threshold": self.recurrence_threshold,
        }

        # Save report
        self._save_report(report)

        return report

    def _save_report(self, report: dict[str, Any]) -> None:
        """Save report to disk."""
        PATTERN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(PATTERN_REPORT_PATH, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Saved pattern report to {PATTERN_REPORT_PATH}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def get_recurring_patterns(self) -> list[RecurringPattern]:
        """
        Get list of recurring patterns.

        Returns:
            List of RecurringPattern objects, sorted by severity
        """
        if not self.patterns:
            # Run analysis if not yet done
            self.analyze_patterns()

        return self.patterns

    def escalate_pattern(self, pattern_type: str) -> None:
        """
        Escalate a specific pattern's severity.

        Used when manual review determines a pattern is more serious
        than auto-detection suggests.

        Args:
            pattern_type: Type of anomaly to escalate
        """
        for pattern in self.patterns:
            if pattern.pattern_type == pattern_type:
                # Escalate severity
                current = pattern.severity
                if current == "LOW":
                    pattern.severity = "MEDIUM"
                elif current == "MEDIUM":
                    pattern.severity = "HIGH"
                elif current == "HIGH":
                    pattern.severity = "CRITICAL"

                logger.warning(f"ESCALATED: {pattern_type} from {current} to {pattern.severity}")

                # Re-save report with updated severity (don't re-analyze)
                # Re-sort patterns by severity
                severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
                self.patterns.sort(
                    key=lambda p: (severity_order.get(p.severity, 0), p.count), reverse=True
                )

                # Generate and save updated report
                windowed = self._filter_by_window(self.anomalies)
                groups = self._group_by_type(windowed)
                report = {
                    "recurring_patterns": [p.to_dict() for p in self.patterns],
                    "total_anomalies": len(windowed),
                    "unique_types": len(groups),
                    "critical_patterns": [
                        p.to_dict() for p in self.patterns if p.severity == "CRITICAL"
                    ],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "window_days": self.window_days,
                    "recurrence_threshold": self.recurrence_threshold,
                }
                self._save_report(report)
                return

        logger.warning(f"Pattern not found for escalation: {pattern_type}")

    def create_github_issue(
        self,
        pattern: RecurringPattern,
        repo: str = "IgorGanapolsky/trading",
    ) -> Optional[str]:
        """
        Create a GitHub issue for a critical pattern.

        Args:
            pattern: RecurringPattern to create issue for
            repo: GitHub repository (owner/repo)

        Returns:
            Issue URL if successful, None otherwise
        """
        if pattern.severity != "CRITICAL":
            logger.info(f"Skipping GitHub issue for {pattern.pattern_type} (not critical)")
            return None

        # Build issue title and body
        title = (
            f"[CRITICAL] Recurring Pattern: {pattern.pattern_type} ({pattern.count} occurrences)"
        )

        body = f"""## Critical Recurring Pattern Detected

**Pattern Type**: `{pattern.pattern_type}`
**Severity**: {pattern.severity}
**Occurrences**: {pattern.count} times in {self.window_days} days
**Frequency**: Every {pattern.frequency_days:.1f} days
**Trend**: {pattern.trend}

### Timeline
- **First Seen**: {pattern.first_seen}
- **Last Seen**: {pattern.last_seen}

### Prevention Suggestion
{pattern.prevention or "No automated prevention suggestion available"}

### Action Required
This pattern has been flagged as CRITICAL due to high recurrence rate.
Review the anomaly log and implement preventive measures immediately.

---
*Auto-generated by PatternRecurrenceDetector*
*Report: `data/pattern_recurrence_report.json`*
"""

        # Try to create issue using gh CLI
        import subprocess

        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    repo,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    "bug,critical,automated",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                issue_url = result.stdout.strip()
                logger.info(f"Created GitHub issue: {issue_url}")
                return issue_url
            else:
                logger.error(f"Failed to create issue: {result.stderr}")
                return None

        except FileNotFoundError:
            logger.warning("gh CLI not available, skipping GitHub issue creation")
            return None
        except Exception as e:
            logger.error(f"Error creating GitHub issue: {e}")
            return None


# Convenience function for daily cron job
def run_daily_pattern_analysis(
    recurrence_threshold: int = 3,
    window_days: int = 7,
    auto_create_issues: bool = False,
) -> dict[str, Any]:
    """
    Run pattern analysis as daily cron job.

    Usage in cron:
        0 8 * * * python3 -c "from src.verification.pattern_recurrence_detector import run_daily_pattern_analysis; run_daily_pattern_analysis()"

    Args:
        recurrence_threshold: Minimum occurrences to flag
        window_days: Analysis window
        auto_create_issues: Auto-create GitHub issues for critical patterns

    Returns:
        Analysis report
    """
    detector = PatternRecurrenceDetector(
        recurrence_threshold=recurrence_threshold,
        window_days=window_days,
    )

    report = detector.analyze_patterns()

    # Log summary
    logger.info("Pattern Analysis Summary:")
    logger.info(f"  Total Anomalies: {report['total_anomalies']}")
    logger.info(f"  Recurring Patterns: {len(report['recurring_patterns'])}")
    logger.info(f"  Critical Patterns: {len(report['critical_patterns'])}")

    # Auto-create issues for critical patterns
    if auto_create_issues:
        for pattern_data in report["critical_patterns"]:
            pattern = RecurringPattern.from_dict(pattern_data)
            detector.create_github_issue(pattern)

    return report
