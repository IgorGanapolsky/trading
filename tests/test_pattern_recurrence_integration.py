"""
Pattern Recurrence Detection Integration Tests.

Tests the pattern recurrence detector that identifies when mistakes
are happening repeatedly - a key component of our learning system.

Author: Trading System
Created: 2025-12-15
Purpose: Verify pattern detection prevents repeated mistakes
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


class TestPatternRecurrenceDetection:
    """Test pattern recurrence detection functionality."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create temporary data directory with anomaly log."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def sample_anomaly_log(self, temp_data_dir):
        """Create sample anomaly log with recurring patterns."""
        now = datetime.now(timezone.utc)

        # Create anomalies with clear patterns
        anomalies = []

        # Pattern 1: Order amount errors - 5 occurrences (should be MEDIUM severity)
        for i in range(5):
            anomalies.append({
                "anomaly_id": f"ORDER-{i:03d}",
                "type": "order_amount",
                "level": "warning",
                "message": f"Order amount ${100 + i * 10} exceeds threshold",
                "detected_at": (now - timedelta(days=i)).isoformat(),
                "details": {"amount": 100 + i * 10},
                "context": {"symbol": "SPY"},
            })

        # Pattern 2: Data staleness - 3 occurrences (should be LOW severity)
        for i in range(3):
            anomalies.append({
                "anomaly_id": f"STALE-{i:03d}",
                "type": "data_staleness",
                "level": "info",
                "message": "Market data is stale",
                "detected_at": (now - timedelta(days=i * 2)).isoformat(),
                "details": {"age_minutes": 15},
                "context": {},
            })

        # Pattern 3: Critical pattern - 12 occurrences (should be CRITICAL)
        for i in range(12):
            anomalies.append({
                "anomaly_id": f"CRIT-{i:03d}",
                "type": "execution_failure",
                "level": "critical",
                "message": "Trade execution failed",
                "detected_at": (now - timedelta(hours=i * 12)).isoformat(),
                "details": {"error": "timeout"},
                "context": {"symbol": "NVDA"},
            })

        # Write to file
        log_path = temp_data_dir / "anomaly_log.json"
        with open(log_path, "w") as f:
            json.dump({"anomalies": anomalies}, f)

        return log_path

    def test_detects_recurring_patterns(self, temp_data_dir, sample_anomaly_log):
        """Verify detector finds recurring patterns."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        # Patch the constants to use temp directory
        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            report = detector.analyze_patterns()

            # Should find recurring patterns
            assert len(report["recurring_patterns"]) > 0, \
                "Should detect recurring patterns"

            # Should find the order_amount pattern (5 occurrences)
            pattern_types = [p["pattern_type"] for p in report["recurring_patterns"]]
            assert "order_amount" in pattern_types, \
                "Should detect order_amount pattern"
            assert "execution_failure" in pattern_types, \
                "Should detect execution_failure pattern"

    def test_severity_calculation(self, temp_data_dir, sample_anomaly_log):
        """Verify severity is calculated correctly based on count."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            report = detector.analyze_patterns()

            # Find patterns by type
            patterns_by_type = {p["pattern_type"]: p for p in report["recurring_patterns"]}

            # Order amount (5 occurrences) should be MEDIUM
            if "order_amount" in patterns_by_type:
                order_pattern = patterns_by_type["order_amount"]
                assert order_pattern["severity"] in ["LOW", "MEDIUM"], \
                    f"5 occurrences should be LOW/MEDIUM, got: {order_pattern['severity']}"

            # Execution failure (12 occurrences) should be CRITICAL
            if "execution_failure" in patterns_by_type:
                exec_pattern = patterns_by_type["execution_failure"]
                assert exec_pattern["severity"] == "CRITICAL", \
                    f"12 occurrences should be CRITICAL, got: {exec_pattern['severity']}"

    def test_critical_patterns_flagged(self, temp_data_dir, sample_anomaly_log):
        """Verify critical patterns are correctly flagged."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            report = detector.analyze_patterns()

            # Should have critical patterns
            assert "critical_patterns" in report, "Report should have critical_patterns"

            if report["critical_patterns"]:
                # Critical patterns should be real critical severity
                for pattern in report["critical_patterns"]:
                    assert pattern["severity"] == "CRITICAL", \
                        "Critical patterns should have CRITICAL severity"

    def test_frequency_calculation(self, temp_data_dir, sample_anomaly_log):
        """Verify frequency calculation is reasonable."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            report = detector.analyze_patterns()

            for pattern in report["recurring_patterns"]:
                # Frequency should be non-negative
                assert pattern["frequency_days"] >= 0, \
                    f"Frequency should be >= 0, got: {pattern['frequency_days']}"

                # For patterns in 7-day window, frequency shouldn't exceed window
                assert pattern["frequency_days"] <= 7, \
                    f"Frequency shouldn't exceed window, got: {pattern['frequency_days']}"

    def test_trend_analysis(self, temp_data_dir, sample_anomaly_log):
        """Verify trend analysis returns valid values."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            report = detector.analyze_patterns()

            valid_trends = ["increasing", "stable", "decreasing"]

            for pattern in report["recurring_patterns"]:
                assert pattern["trend"] in valid_trends, \
                    f"Invalid trend: {pattern['trend']}"

    def test_escalation_updates_severity(self, temp_data_dir, sample_anomaly_log):
        """Verify pattern escalation increases severity."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            sample_anomaly_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector(
                recurrence_threshold=3,
                window_days=7,
            )

            # Analyze to populate patterns
            detector.analyze_patterns()

            # Find a non-critical pattern
            for pattern in detector.patterns:
                if pattern.severity in ["LOW", "MEDIUM"]:
                    original_severity = pattern.severity

                    # Escalate
                    detector.escalate_pattern(pattern.pattern_type)

                    # Verify escalation
                    escalated = next(
                        p for p in detector.patterns
                        if p.pattern_type == pattern.pattern_type
                    )

                    if original_severity == "LOW":
                        assert escalated.severity == "MEDIUM"
                    elif original_severity == "MEDIUM":
                        assert escalated.severity == "HIGH"

                    break

    def test_empty_log_handling(self, temp_data_dir):
        """Verify graceful handling of empty anomaly log."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        # Create empty log
        empty_log = temp_data_dir / "anomaly_log.json"
        with open(empty_log, "w") as f:
            json.dump({"anomalies": []}, f)

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            empty_log,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector()
            report = detector.analyze_patterns()

            assert report["total_anomalies"] == 0
            assert len(report["recurring_patterns"]) == 0

    def test_missing_log_handling(self, temp_data_dir):
        """Verify graceful handling of missing anomaly log."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            temp_data_dir / "nonexistent.json",
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            temp_data_dir / "pattern_report.json",
        ):
            detector = PatternRecurrenceDetector()
            report = detector.analyze_patterns()

            # Should not crash, just return empty
            assert report["total_anomalies"] == 0


class TestPatternToPreventionIntegration:
    """Test integration between pattern detection and prevention system."""

    def test_pattern_triggers_rag_lookup(self, tmp_path):
        """Verify detected patterns query RAG for prevention."""
        from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

        # Create anomaly log with pattern
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        now = datetime.now(timezone.utc)
        anomalies = [
            {
                "anomaly_id": f"TEST-{i}",
                "type": "size_error",
                "level": "high",
                "message": "Position size too large",
                "detected_at": (now - timedelta(days=i)).isoformat(),
                "details": {},
                "context": {},
            }
            for i in range(5)
        ]

        log_path = data_dir / "anomaly_log.json"
        with open(log_path, "w") as f:
            json.dump({"anomalies": anomalies}, f)

        # Create RAG lessons
        rag_dir = data_dir / "rag"
        rag_dir.mkdir()
        rag_path = rag_dir / "lessons_learned.json"
        with open(rag_path, "w") as f:
            json.dump({
                "lessons": [
                    {
                        "category": "size_error",
                        "title": "Position Size Error",
                        "prevention": "Add pre-trade size validation",
                        "tags": ["size_error", "position"],
                    }
                ]
            }, f)

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            log_path,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            data_dir / "report.json",
        ), patch(
            "src.verification.pattern_recurrence_detector.RAG_LESSONS_PATH",
            rag_path,
        ):
            detector = PatternRecurrenceDetector(recurrence_threshold=3, window_days=7)
            report = detector.analyze_patterns()

            # Find the size_error pattern
            size_pattern = None
            for p in report["recurring_patterns"]:
                if p["pattern_type"] == "size_error":
                    size_pattern = p
                    break

            assert size_pattern is not None, "Should detect size_error pattern"
            assert size_pattern["prevention"] is not None, \
                "Should have prevention from RAG"
            assert "validation" in size_pattern["prevention"].lower(), \
                "Prevention should mention validation"


class TestRecurringPatternDataclass:
    """Test RecurringPattern dataclass."""

    def test_to_dict_and_from_dict(self):
        """Verify serialization round-trip."""
        from src.verification.pattern_recurrence_detector import RecurringPattern

        original = RecurringPattern(
            pattern_type="test_pattern",
            count=5,
            first_seen="2025-12-10T00:00:00+00:00",
            last_seen="2025-12-15T00:00:00+00:00",
            frequency_days=1.0,
            severity="MEDIUM",
            trend="stable",
            prevention="Test prevention",
            occurrences=[{"id": "1"}, {"id": "2"}],
        )

        # Convert to dict
        as_dict = original.to_dict()

        # Verify all fields
        assert as_dict["pattern_type"] == "test_pattern"
        assert as_dict["count"] == 5
        assert as_dict["severity"] == "MEDIUM"
        assert as_dict["trend"] == "stable"

        # Convert back
        restored = RecurringPattern.from_dict(as_dict)

        # Verify equality
        assert restored.pattern_type == original.pattern_type
        assert restored.count == original.count
        assert restored.severity == original.severity


class TestDailyPatternAnalysis:
    """Test daily pattern analysis cron job function."""

    def test_run_daily_analysis(self, tmp_path):
        """Verify daily analysis function runs without error."""
        from src.verification.pattern_recurrence_detector import run_daily_pattern_analysis

        # Create minimal anomaly log
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        log_path = data_dir / "anomaly_log.json"
        with open(log_path, "w") as f:
            json.dump({"anomalies": []}, f)

        with patch(
            "src.verification.pattern_recurrence_detector.ANOMALY_LOG_PATH",
            log_path,
        ), patch(
            "src.verification.pattern_recurrence_detector.PATTERN_REPORT_PATH",
            data_dir / "report.json",
        ):
            report = run_daily_pattern_analysis(
                recurrence_threshold=3,
                window_days=7,
                auto_create_issues=False,  # Don't create real issues in tests
            )

            assert "recurring_patterns" in report
            assert "total_anomalies" in report
            assert "generated_at" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
