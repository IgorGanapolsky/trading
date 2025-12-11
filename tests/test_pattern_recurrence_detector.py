"""Tests for Pattern Recurrence Detector.

Tests cover:
1. Pattern detection and grouping
2. Frequency calculation
3. Severity escalation
4. Trend analysis
5. RAG integration
6. Report generation
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.verification.pattern_recurrence_detector import (
    PatternRecurrenceDetector,
    RecurringPattern,
    run_daily_pattern_analysis,
)


@pytest.fixture
def temp_anomaly_log(tmp_path):
    """Create temporary anomaly log file."""
    log_path = tmp_path / "data" / "anomaly_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


@pytest.fixture
def sample_anomalies():
    """Generate sample anomalies for testing."""
    now = datetime.now(timezone.utc)
    anomalies = []

    # Create pattern 1: order_amount (recurring every 2 days, CRITICAL)
    for i in range(12):
        anomalies.append({
            "anomaly_id": f"ANO-{i:04d}-AMT",
            "type": "order_amount",
            "level": "warning",
            "message": f"Order amount exceeds threshold",
            "details": {"amount": 100.0},
            "detected_at": (now - timedelta(days=i*2)).isoformat(),
            "context": {"symbol": "SPY"},
        })

    # Create pattern 2: data_staleness (recurring every 3 days, MEDIUM)
    for i in range(5):
        anomalies.append({
            "anomaly_id": f"ANO-{i:04d}-STL",
            "type": "data_staleness",
            "level": "warning",
            "message": f"Data is stale",
            "details": {"age_hours": 48},
            "detected_at": (now - timedelta(days=i*3)).isoformat(),
            "context": {"source": "market_data"},
        })

    # Create pattern 3: symbol_unknown (only 2 occurrences, below threshold)
    for i in range(2):
        anomalies.append({
            "anomaly_id": f"ANO-{i:04d}-SYM",
            "type": "symbol_unknown",
            "level": "warning",
            "message": f"Unknown symbol",
            "details": {"symbol": "INVALID"},
            "detected_at": (now - timedelta(days=i*5)).isoformat(),
            "context": {},
        })

    # Create pattern 4: price_deviation (increasing trend)
    # First half: 2 occurrences over 7 days
    for i in range(2):
        anomalies.append({
            "anomaly_id": f"ANO-{i:04d}-PRC-1",
            "type": "price_deviation",
            "level": "warning",
            "message": "Price deviation",
            "details": {"deviation_pct": 5.5},
            "detected_at": (now - timedelta(days=14-i*3)).isoformat(),
            "context": {"symbol": "NVDA"},
        })

    # Second half: 4 occurrences over 7 days (increasing trend)
    for i in range(4):
        anomalies.append({
            "anomaly_id": f"ANO-{i:04d}-PRC-2",
            "type": "price_deviation",
            "level": "warning",
            "message": "Price deviation",
            "details": {"deviation_pct": 5.5},
            "detected_at": (now - timedelta(days=7-i*1.5)).isoformat(),
            "context": {"symbol": "NVDA"},
        })

    return anomalies


@pytest.fixture
def populated_anomaly_log(temp_anomaly_log, sample_anomalies):
    """Create anomaly log with sample data."""
    with open(temp_anomaly_log, "w") as f:
        json.dump({"anomalies": sample_anomalies}, f, indent=2)
    return temp_anomaly_log


class TestRecurringPattern:
    """Tests for RecurringPattern dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        pattern = RecurringPattern(
            pattern_type="order_amount",
            count=10,
            first_seen="2025-12-01T10:00:00+00:00",
            last_seen="2025-12-10T10:00:00+00:00",
            frequency_days=1.0,
            severity="CRITICAL",
            trend="increasing",
            prevention="Implement stricter validation",
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "order_amount"
        assert result["count"] == 10
        assert result["severity"] == "CRITICAL"
        assert result["trend"] == "increasing"
        assert result["frequency_days"] == 1.0

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "pattern_type": "data_staleness",
            "count": 5,
            "first_seen": "2025-12-01T10:00:00+00:00",
            "last_seen": "2025-12-05T10:00:00+00:00",
            "frequency_days": 1.0,
            "severity": "MEDIUM",
            "trend": "stable",
            "prevention": "Refresh data more frequently",
            "occurrences": [],
        }

        pattern = RecurringPattern.from_dict(data)

        assert pattern.pattern_type == "data_staleness"
        assert pattern.count == 5
        assert pattern.severity == "MEDIUM"


class TestPatternRecurrenceDetector:
    """Tests for PatternRecurrenceDetector."""

    def test_init_no_anomaly_log(self, tmp_path):
        """Test initialization when no anomaly log exists."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', tmp_path / "missing.json"):
            detector = PatternRecurrenceDetector()
            assert detector.anomalies == []

    def test_load_anomalies(self, populated_anomaly_log):
        """Test loading anomalies from log."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector()
            assert len(detector.anomalies) > 0
            assert detector.anomalies[0]["type"] == "order_amount"

    def test_filter_by_window(self, populated_anomaly_log):
        """Test filtering anomalies by time window."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=7)

            # All anomalies
            all_anomalies = detector.anomalies

            # Filtered
            filtered = detector._filter_by_window(all_anomalies)

            # Should have fewer than all
            assert len(filtered) < len(all_anomalies)

    def test_group_by_type(self, populated_anomaly_log):
        """Test grouping anomalies by type."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector()

            groups = detector._group_by_type(detector.anomalies)

            # Should have multiple groups
            assert len(groups) >= 3
            assert "order_amount" in groups
            assert "data_staleness" in groups
            assert "price_deviation" in groups

    def test_calculate_frequency(self, sample_anomalies):
        """Test frequency calculation."""
        detector = PatternRecurrenceDetector()

        # Get order_amount occurrences (every 2 days)
        order_amount_occs = [a for a in sample_anomalies if a["type"] == "order_amount"]

        frequency = detector._calculate_frequency(order_amount_occs)

        # Should be approximately 2 days
        assert 1.5 < frequency < 2.5

    def test_calculate_frequency_insufficient_data(self):
        """Test frequency calculation with < 2 occurrences."""
        detector = PatternRecurrenceDetector()

        # Single occurrence
        occurrences = [{
            "detected_at": datetime.now(timezone.utc).isoformat()
        }]

        frequency = detector._calculate_frequency(occurrences)
        assert frequency == 0.0

    def test_determine_severity(self):
        """Test severity determination based on count."""
        detector = PatternRecurrenceDetector()

        assert detector._determine_severity(2) == "LOW"
        assert detector._determine_severity(5) == "MEDIUM"
        assert detector._determine_severity(8) == "HIGH"
        assert detector._determine_severity(15) == "CRITICAL"

    def test_analyze_trend_increasing(self, sample_anomalies):
        """Test trend analysis for increasing pattern."""
        detector = PatternRecurrenceDetector()

        # Get price_deviation occurrences (designed to be increasing)
        price_dev_occs = [a for a in sample_anomalies if a["type"] == "price_deviation"]

        trend = detector._analyze_trend(price_dev_occs)

        # Should detect increasing trend
        assert trend == "increasing"

    def test_analyze_trend_stable(self, sample_anomalies):
        """Test trend analysis for stable pattern."""
        detector = PatternRecurrenceDetector()

        # Get order_amount occurrences (even distribution)
        order_amount_occs = [a for a in sample_anomalies if a["type"] == "order_amount"]

        trend = detector._analyze_trend(order_amount_occs)

        # Should be stable or decreasing (evenly distributed)
        assert trend in ["stable", "decreasing"]

    def test_analyze_trend_insufficient_data(self):
        """Test trend analysis with < 4 occurrences."""
        detector = PatternRecurrenceDetector()

        occurrences = [
            {"detected_at": datetime.now(timezone.utc).isoformat()},
            {"detected_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        ]

        trend = detector._analyze_trend(occurrences)
        assert trend == "stable"

    def test_get_prevention_suggestion_no_rag(self, tmp_path):
        """Test prevention suggestion when RAG not available."""
        with patch('src.verification.pattern_recurrence_detector.RAG_LESSONS_PATH', tmp_path / "missing.json"):
            detector = PatternRecurrenceDetector()
            suggestion = detector._get_prevention_suggestion("order_amount")
            assert suggestion is None

    def test_get_prevention_suggestion_with_rag(self, tmp_path):
        """Test prevention suggestion with RAG."""
        rag_path = tmp_path / "rag" / "lessons_learned.json"
        rag_path.parent.mkdir(parents=True, exist_ok=True)

        # Create sample RAG data
        rag_data = {
            "lessons": [
                {
                    "id": "lesson_001",
                    "category": "order_amount",
                    "title": "Order Amount Validation",
                    "prevention": "Implement stricter validation and circuit breakers",
                    "tags": ["order_amount", "validation"],
                }
            ]
        }

        with open(rag_path, "w") as f:
            json.dump(rag_data, f)

        with patch('src.verification.pattern_recurrence_detector.RAG_LESSONS_PATH', rag_path):
            detector = PatternRecurrenceDetector()
            suggestion = detector._get_prevention_suggestion("order_amount")
            assert "circuit breakers" in suggestion

    def test_analyze_patterns(self, populated_anomaly_log, tmp_path):
        """Test full pattern analysis."""
        report_path = tmp_path / "pattern_recurrence_report.json"

        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            with patch('src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH', report_path):
                detector = PatternRecurrenceDetector(
                    recurrence_threshold=3,
                    window_days=30,
                )

                report = detector.analyze_patterns()

                # Verify report structure
                assert "recurring_patterns" in report
                assert "total_anomalies" in report
                assert "unique_types" in report
                assert "critical_patterns" in report

                # Should detect multiple patterns
                assert len(report["recurring_patterns"]) >= 2

                # Should identify critical patterns
                critical = report["critical_patterns"]
                assert len(critical) > 0
                assert critical[0]["severity"] == "CRITICAL"

                # Should save report to disk
                assert report_path.exists()

    def test_analyze_patterns_respects_threshold(self, populated_anomaly_log):
        """Test that recurrence threshold is respected."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=10,  # High threshold
                window_days=30,
            )

            report = detector.analyze_patterns()

            # Should only detect patterns with >= 10 occurrences
            for pattern in report["recurring_patterns"]:
                assert pattern["count"] >= 10

    def test_get_recurring_patterns(self, populated_anomaly_log):
        """Test getting recurring patterns."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=30)

            patterns = detector.get_recurring_patterns()

            # Should return list of RecurringPattern objects
            assert len(patterns) > 0
            assert all(isinstance(p, RecurringPattern) for p in patterns)

            # Should be sorted by severity then count
            severities = [p.severity for p in patterns]
            assert severities[0] in ["CRITICAL", "HIGH"]

    def test_escalate_pattern(self, populated_anomaly_log, tmp_path):
        """Test pattern escalation."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            with patch('src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH', tmp_path / "report.json"):
                detector = PatternRecurrenceDetector(window_days=30)
                detector.analyze_patterns()

                # Find a LOW or MEDIUM pattern
                target_pattern = None
                for pattern in detector.patterns:
                    if pattern.severity in ["LOW", "MEDIUM"]:
                        target_pattern = pattern
                        break

                if target_pattern:
                    original_severity = target_pattern.severity
                    detector.escalate_pattern(target_pattern.pattern_type)

                    # Verify escalation
                    for pattern in detector.patterns:
                        if pattern.pattern_type == target_pattern.pattern_type:
                            if original_severity == "LOW":
                                assert pattern.severity == "MEDIUM"
                            elif original_severity == "MEDIUM":
                                assert pattern.severity == "HIGH"

    def test_escalate_pattern_not_found(self, populated_anomaly_log):
        """Test escalating non-existent pattern."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector()
            detector.analyze_patterns()

            # Should not raise exception
            detector.escalate_pattern("nonexistent_pattern")

    @patch('subprocess.run')
    def test_create_github_issue_success(self, mock_run, populated_anomaly_log):
        """Test GitHub issue creation for critical pattern."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=30)
            detector.analyze_patterns()

            # Find critical pattern
            critical_pattern = None
            for pattern in detector.patterns:
                if pattern.severity == "CRITICAL":
                    critical_pattern = pattern
                    break

            if critical_pattern:
                # Mock successful issue creation
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="https://github.com/IgorGanapolsky/trading/issues/123\n"
                )

                url = detector.create_github_issue(critical_pattern)

                assert url == "https://github.com/IgorGanapolsky/trading/issues/123"
                assert mock_run.called

    def test_create_github_issue_not_critical(self, populated_anomaly_log):
        """Test that GitHub issue is not created for non-critical patterns."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=30)
            detector.analyze_patterns()

            # Find non-critical pattern
            for pattern in detector.patterns:
                if pattern.severity != "CRITICAL":
                    url = detector.create_github_issue(pattern)
                    assert url is None
                    break

    @patch('subprocess.run')
    def test_create_github_issue_gh_cli_not_available(self, mock_run, populated_anomaly_log):
        """Test GitHub issue creation when gh CLI not available."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=30)
            detector.analyze_patterns()

            # Find critical pattern
            for pattern in detector.patterns:
                if pattern.severity == "CRITICAL":
                    # Mock gh CLI not found
                    mock_run.side_effect = FileNotFoundError()

                    url = detector.create_github_issue(pattern)
                    assert url is None
                    break


class TestConvenienceFunction:
    """Tests for run_daily_pattern_analysis convenience function."""

    def test_run_daily_pattern_analysis(self, populated_anomaly_log, tmp_path):
        """Test daily pattern analysis run."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            with patch('src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH', tmp_path / "report.json"):
                report = run_daily_pattern_analysis(
                    recurrence_threshold=3,
                    window_days=30,
                    auto_create_issues=False,
                )

                # Verify report
                assert "recurring_patterns" in report
                assert "total_anomalies" in report
                assert len(report["recurring_patterns"]) > 0

    @patch('subprocess.run')
    def test_run_daily_pattern_analysis_with_auto_issues(self, mock_run, populated_anomaly_log, tmp_path):
        """Test daily analysis with auto issue creation."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            with patch('src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH', tmp_path / "report.json"):
                # Mock successful issue creation
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="https://github.com/IgorGanapolsky/trading/issues/123\n"
                )

                report = run_daily_pattern_analysis(
                    recurrence_threshold=3,
                    window_days=30,
                    auto_create_issues=True,
                )

                # Should create issues for critical patterns
                if len(report["critical_patterns"]) > 0:
                    assert mock_run.called


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_anomaly_log(self, tmp_path):
        """Test handling of empty anomaly log."""
        log_path = tmp_path / "empty.json"
        with open(log_path, "w") as f:
            json.dump({"anomalies": []}, f)

        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', log_path):
            detector = PatternRecurrenceDetector()
            report = detector.analyze_patterns()

            assert report["total_anomalies"] == 0
            assert len(report["recurring_patterns"]) == 0

    def test_malformed_anomaly_log(self, tmp_path):
        """Test handling of malformed JSON."""
        log_path = tmp_path / "malformed.json"
        with open(log_path, "w") as f:
            f.write("{invalid json")

        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', log_path):
            detector = PatternRecurrenceDetector()
            assert detector.anomalies == []

    def test_anomalies_missing_timestamps(self, tmp_path):
        """Test handling of anomalies with missing timestamps."""
        log_path = tmp_path / "missing_ts.json"
        anomalies = [
            {"type": "order_amount", "message": "Test"},  # Missing detected_at
            {"type": "order_amount", "message": "Test", "detected_at": "invalid"},
        ]

        with open(log_path, "w") as f:
            json.dump({"anomalies": anomalies}, f)

        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', log_path):
            detector = PatternRecurrenceDetector()
            report = detector.analyze_patterns()

            # Should handle gracefully
            assert "recurring_patterns" in report

    def test_window_days_zero(self, populated_anomaly_log):
        """Test with zero window days."""
        with patch('src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH', populated_anomaly_log):
            detector = PatternRecurrenceDetector(window_days=0)
            report = detector.analyze_patterns()

            # Should return no patterns (zero window)
            assert report["total_anomalies"] == 0


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
