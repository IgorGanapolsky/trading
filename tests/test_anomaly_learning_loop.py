"""
Tests for Anomaly Learning Feedback Loop.

Tests the continuous learning system that automatically learns from
every anomaly and updates prevention strategies in RAG.

Author: Trading System
Created: 2025-12-11
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.verification.anomaly_learning_feedback_loop import (
    AnomalyLearningLoop,
    RecurrenceRecord,
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    reports_dir = tmp_path / "reports" / "anomaly_reports"
    reports_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_rag():
    """Create mock RAG system."""
    rag = MagicMock(spec=LessonsLearnedRAG)
    rag.add_lesson.return_value = "lesson_20251211_120000_0"
    return rag


@pytest.fixture
def learning_loop(mock_rag, temp_data_dir, monkeypatch):
    """Create AnomalyLearningLoop with mocked dependencies."""
    # Patch file paths to use temp directory
    monkeypatch.setattr(
        "src.verification.anomaly_learning_feedback_loop.RECURRENCE_DB_PATH",
        temp_data_dir / "data" / "anomaly_recurrence.json",
    )
    monkeypatch.setattr(
        "src.verification.anomaly_learning_feedback_loop.DAILY_REPORT_PATH",
        temp_data_dir / "reports" / "anomaly_reports",
    )

    loop = AnomalyLearningLoop(rag=mock_rag)
    return loop


@pytest.fixture
def sample_anomaly():
    """Create sample anomaly dict."""
    return {
        "anomaly_id": "ANO-20251211120000-AMT",
        "type": "order_amount",
        "level": "warning",
        "message": "Order amount $150.00 exceeds threshold $100.00",
        "details": {
            "amount": 150.0,
            "max_amount": 100.0,
            "expected_daily": 10.0,
            "multiplier": 15.0,
        },
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "context": {
            "symbol": "SPY",
            "amount": 150.0,
            "action": "BUY",
        },
    }


class TestAnomalyLearningLoop:
    """Test suite for AnomalyLearningLoop."""

    def test_initialization(self, mock_rag):
        """Test loop initializes correctly."""
        loop = AnomalyLearningLoop(rag=mock_rag, similarity_threshold=0.8)

        assert loop.rag == mock_rag
        assert loop.similarity_threshold == 0.8
        assert isinstance(loop.recurrence_records, dict)
        assert isinstance(loop.daily_anomalies, list)

    def test_process_first_anomaly(self, learning_loop, mock_rag, sample_anomaly):
        """Test processing a brand new anomaly."""
        result = learning_loop.process_anomaly(sample_anomaly)

        # Should create new lesson
        assert result["anomaly_processed"] is True
        assert result["is_recurring"] is False
        assert result["recurrence_count"] == 1
        assert result["severity"] == "LOW"
        assert result["lesson_id"] is not None
        assert result["prevention_suggested"] is not None

        # Should add to daily tracking
        assert len(learning_loop.daily_anomalies) == 1

        # Should call RAG to create lesson
        mock_rag.add_lesson.assert_called_once()

    def test_process_recurring_anomaly(self, learning_loop, sample_anomaly):
        """Test processing same anomaly type twice."""
        # Process first time
        result1 = learning_loop.process_anomaly(sample_anomaly)
        assert result1["recurrence_count"] == 1
        assert result1["severity"] == "LOW"

        # Process second time
        sample_anomaly["anomaly_id"] = "ANO-20251211120001-AMT"
        result2 = learning_loop.process_anomaly(sample_anomaly)

        assert result2["anomaly_processed"] is True
        assert result2["is_recurring"] is True
        assert result2["recurrence_count"] == 2
        assert result2["severity"] == "LOW"  # Still LOW (need 3+ for MEDIUM)

    def test_severity_escalation(self, learning_loop):
        """Test severity escalates with recurrence count."""
        assert learning_loop.escalate_severity("test", 1) == "LOW"
        assert learning_loop.escalate_severity("test", 2) == "LOW"
        assert learning_loop.escalate_severity("test", 3) == "MEDIUM"
        assert learning_loop.escalate_severity("test", 4) == "MEDIUM"
        assert learning_loop.escalate_severity("test", 5) == "HIGH"
        assert learning_loop.escalate_severity("test", 6) == "HIGH"
        assert learning_loop.escalate_severity("test", 7) == "CRITICAL"
        assert learning_loop.escalate_severity("test", 10) == "CRITICAL"

    def test_check_if_recurring_new_pattern(self, learning_loop):
        """Test checking for recurring pattern that doesn't exist."""
        result = learning_loop.check_if_recurring("order_amount")

        assert result["is_recurring"] is False
        assert result["recurrence_count"] == 0
        assert result["last_seen"] is None
        assert result["severity"] == "LOW"

    def test_check_if_recurring_existing_pattern(self, learning_loop, sample_anomaly):
        """Test checking for recurring pattern that exists."""
        # Create initial occurrence
        learning_loop.process_anomaly(sample_anomaly)

        # Check recurrence
        result = learning_loop.check_if_recurring("order_amount")

        assert result["is_recurring"] is True
        assert result["recurrence_count"] == 1
        assert result["last_seen"] is not None
        assert result["severity"] == "LOW"

    def test_auto_ingest_lesson(self, learning_loop, mock_rag, sample_anomaly):
        """Test automatic lesson ingestion."""
        lesson_id = learning_loop.auto_ingest_lesson(sample_anomaly)

        assert lesson_id is not None
        assert lesson_id.startswith("lesson_")

        # Verify RAG was called with correct parameters
        mock_rag.add_lesson.assert_called_once()
        call_kwargs = mock_rag.add_lesson.call_args.kwargs

        assert call_kwargs["category"] == "order_amount"
        assert "Anomaly: order_amount" in call_kwargs["title"]
        assert call_kwargs["severity"] == "medium"
        assert "anomaly" in call_kwargs["tags"]
        assert "auto_generated" in call_kwargs["tags"]

    def test_auto_ingest_lesson_with_financial_impact(self, learning_loop, mock_rag):
        """Test lesson ingestion includes financial impact."""
        anomaly = {
            "anomaly_id": "ANO-TEST",
            "type": "execution_failure",
            "level": "critical",
            "message": "Trade failed",
            "details": {"financial_impact": 100.50},
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "context": {"symbol": "NVDA"},
        }

        learning_loop.auto_ingest_lesson(anomaly)

        call_kwargs = mock_rag.add_lesson.call_args.kwargs
        assert call_kwargs["financial_impact"] == 100.50
        assert call_kwargs["symbol"] == "NVDA"
        assert call_kwargs["severity"] == "critical"

    def test_generate_daily_report_empty(self, learning_loop):
        """Test daily report with no anomalies."""
        report = learning_loop.generate_daily_report()

        assert report["total_anomalies"] == 0
        assert report["by_type"] == {}
        assert report["by_severity"] == {}
        assert report["new_patterns"] == 0
        assert report["recurring_patterns"] == 0
        assert len(report["critical_issues"]) == 0
        assert report["lessons_created"] == 0

    def test_generate_daily_report_with_anomalies(self, learning_loop, sample_anomaly):
        """Test daily report with multiple anomalies."""
        # Add several anomalies
        learning_loop.process_anomaly(sample_anomaly)

        anomaly2 = {
            **sample_anomaly,
            "anomaly_id": "ANO-20251211120002-STL",
            "type": "data_staleness",
            "level": "critical",
        }
        learning_loop.process_anomaly(anomaly2)

        # Same type as first (recurring)
        anomaly3 = {
            **sample_anomaly,
            "anomaly_id": "ANO-20251211120003-AMT",
        }
        learning_loop.process_anomaly(anomaly3)

        report = learning_loop.generate_daily_report()

        assert report["total_anomalies"] == 3
        assert report["by_type"]["order_amount"] == 2
        assert report["by_type"]["data_staleness"] == 1
        # After processing, data_staleness has count=1 (new), order_amount has count=2 (recurring)
        assert report["new_patterns"] == 1
        assert report["recurring_patterns"] == 1
        assert len(report["critical_issues"]) == 1  # One critical anomaly

    def test_daily_report_resets_tracking(self, learning_loop, sample_anomaly):
        """Test daily report resets daily tracking."""
        learning_loop.process_anomaly(sample_anomaly)
        assert len(learning_loop.daily_anomalies) == 1

        learning_loop.generate_daily_report()
        assert len(learning_loop.daily_anomalies) == 0

    @patch("subprocess.run")
    def test_create_github_issue_success(self, mock_run, learning_loop, sample_anomaly):
        """Test creating GitHub issue for critical anomaly."""
        # Mock successful gh CLI call
        mock_run.return_value = Mock(
            returncode=0, stdout="https://github.com/user/repo/issues/123\n"
        )

        # Process anomaly 7 times to trigger CRITICAL
        for i in range(7):
            sample_anomaly["anomaly_id"] = f"ANO-{i}"
            learning_loop.process_anomaly(sample_anomaly)

        # Last process should create GitHub issue
        pattern_id = learning_loop._get_pattern_id("order_amount")
        record = learning_loop.recurrence_records[pattern_id]

        assert record.github_issue == "https://github.com/user/repo/issues/123"
        mock_run.assert_called_once()

        # Verify gh CLI was called correctly
        call_args = mock_run.call_args.args[0]
        assert "gh" in call_args
        assert "issue" in call_args
        assert "create" in call_args

    @patch("subprocess.run")
    def test_create_github_issue_only_once(self, mock_run, learning_loop, sample_anomaly):
        """Test GitHub issue is only created once per pattern."""
        mock_run.return_value = Mock(
            returncode=0, stdout="https://github.com/user/repo/issues/123\n"
        )

        # Process anomaly 10 times
        for i in range(10):
            sample_anomaly["anomaly_id"] = f"ANO-{i}"
            learning_loop.process_anomaly(sample_anomaly)

        # Should only create issue once (at 7th occurrence)
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_create_github_issue_failure(self, mock_run, learning_loop, sample_anomaly):
        """Test handling GitHub issue creation failure."""
        # Mock failed gh CLI call
        mock_run.return_value = Mock(returncode=1, stderr="Error: gh not configured")

        # Process anomaly 7 times
        for i in range(7):
            sample_anomaly["anomaly_id"] = f"ANO-{i}"
            result = learning_loop.process_anomaly(sample_anomaly)

        # Should handle failure gracefully
        assert result["github_issue"] is None

    def test_recurrence_db_persistence(self, learning_loop, sample_anomaly, temp_data_dir):
        """Test recurrence records are saved and loaded correctly."""
        # Process anomaly
        learning_loop.process_anomaly(sample_anomaly)

        # Verify file was created
        db_path = temp_data_dir / "data" / "anomaly_recurrence.json"
        assert db_path.exists()

        # Load and verify contents
        with open(db_path) as f:
            data = json.load(f)

        assert "pattern_order_amount" in data
        record = data["pattern_order_amount"]
        assert record["count"] == 1
        assert record["severity"] == "LOW"
        assert record["anomaly_type"] == "order_amount"

    def test_load_existing_recurrence_db(self, temp_data_dir, mock_rag, monkeypatch):
        """Test loading existing recurrence database."""
        # Create existing database
        db_path = temp_data_dir / "data" / "anomaly_recurrence.json"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        existing_data = {
            "pattern_order_amount": {
                "pattern_id": "pattern_order_amount",
                "anomaly_type": "order_amount",
                "first_seen": "2025-12-10T10:00:00Z",
                "last_seen": "2025-12-10T15:00:00Z",
                "count": 5,
                "severity": "HIGH",
                "lesson_id": "lesson_123",
                "github_issue": None,
            }
        }

        with open(db_path, "w") as f:
            json.dump(existing_data, f)

        # Patch file paths
        monkeypatch.setattr(
            "src.verification.anomaly_learning_feedback_loop.RECURRENCE_DB_PATH", db_path
        )

        # Create new loop - should load existing data
        loop = AnomalyLearningLoop(rag=mock_rag)

        assert len(loop.recurrence_records) == 1
        record = loop.recurrence_records["pattern_order_amount"]
        assert record.count == 5
        assert record.severity == "HIGH"
        assert record.lesson_id == "lesson_123"

    def test_daily_report_file_creation(self, learning_loop, sample_anomaly, temp_data_dir):
        """Test daily report is saved to file."""
        learning_loop.process_anomaly(sample_anomaly)
        report = learning_loop.generate_daily_report()

        # Verify report file was created
        report_dir = temp_data_dir / "reports" / "anomaly_reports"
        report_files = list(report_dir.glob("anomaly_report_*.json"))

        assert len(report_files) == 1

        # Verify contents
        with open(report_files[0]) as f:
            saved_report = json.load(f)

        assert saved_report["total_anomalies"] == report["total_anomalies"]
        assert saved_report["date"] == report["date"]

    def test_prevention_generation(self, learning_loop):
        """Test prevention strategy generation for different anomaly types."""
        anomaly_types = [
            "order_amount",
            "data_staleness",
            "execution_failure",
            "symbol_unknown",
            "market_hours",
            "position_size",
            "volatility_spike",
        ]

        for anomaly_type in anomaly_types:
            anomaly = {
                "anomaly_id": f"ANO-{anomaly_type}",
                "type": anomaly_type,
                "level": "warning",
                "message": "Test anomaly",
                "details": {},
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "context": {},
            }

            prevention = learning_loop._generate_prevention(anomaly)
            assert prevention is not None
            assert len(prevention) > 0
            # Prevention should contain some validation/check/prevention keyword
            assert any(
                keyword in prevention.lower()
                for keyword in [
                    "valid",
                    "check",
                    "prevent",
                    "enforce",
                    "add",
                    "implement",
                    "monitor",
                ]
            )

    def test_root_cause_inference(self, learning_loop):
        """Test root cause inference for different anomaly types."""
        anomaly = {
            "anomaly_id": "ANO-TEST",
            "type": "order_amount",
            "level": "warning",
            "message": "Amount exceeds threshold",
            "details": {"multiplier": 15.0},
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "context": {},
        }

        root_cause = learning_loop._infer_root_cause(anomaly)

        assert root_cause is not None
        assert "calculation error" in root_cause.lower() or "conversion" in root_cause.lower()
        assert "15.0x expected" in root_cause  # Should include multiplier detail

    def test_pattern_id_generation(self, learning_loop):
        """Test pattern ID generation is consistent."""
        pattern_id1 = learning_loop._get_pattern_id("order_amount")
        pattern_id2 = learning_loop._get_pattern_id("order_amount")

        assert pattern_id1 == pattern_id2
        assert pattern_id1 == "pattern_order_amount"

    def test_multiple_anomaly_types_tracking(self, learning_loop):
        """Test tracking multiple different anomaly types."""
        anomalies = [
            {
                "anomaly_id": f"ANO-{i}",
                "type": anomaly_type,
                "level": "warning",
                "message": f"Test {anomaly_type}",
                "details": {},
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "context": {},
            }
            for i, anomaly_type in enumerate(
                [
                    "order_amount",
                    "data_staleness",
                    "execution_failure",
                    "order_amount",  # Duplicate
                    "data_staleness",  # Duplicate
                ]
            )
        ]

        for anomaly in anomalies:
            learning_loop.process_anomaly(anomaly)

        # Should have 3 unique patterns
        assert len(learning_loop.recurrence_records) == 3

        # Check counts
        assert learning_loop.recurrence_records["pattern_order_amount"].count == 2
        assert learning_loop.recurrence_records["pattern_data_staleness"].count == 2
        assert learning_loop.recurrence_records["pattern_execution_failure"].count == 1

    def test_critical_anomaly_severity(self, learning_loop):
        """Test processing anomaly that's already critical level."""
        anomaly = {
            "anomaly_id": "ANO-CRITICAL",
            "type": "execution_failure",
            "level": "block",  # Highest alert level
            "message": "Critical failure",
            "details": {"financial_impact": 500.0},
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "context": {"symbol": "SPY"},
        }

        result = learning_loop.process_anomaly(anomaly)

        # Should still process correctly
        assert result["anomaly_processed"] is True
        assert result["recurrence_count"] == 1

    def test_lesson_description_formatting(self, learning_loop, sample_anomaly):
        """Test lesson description includes all relevant details."""
        description = learning_loop._format_lesson_description(sample_anomaly)

        assert sample_anomaly["message"] in description
        assert "Details:" in description
        assert "Context:" in description
        assert "Detected at:" in description
        assert sample_anomaly["anomaly_id"] in description
        assert "amount: 150.0" in description
        assert "symbol: SPY" in description


class TestRecurrenceRecord:
    """Test suite for RecurrenceRecord dataclass."""

    def test_to_dict(self):
        """Test converting record to dict."""
        record = RecurrenceRecord(
            pattern_id="pattern_test",
            anomaly_type="order_amount",
            first_seen="2025-12-11T10:00:00Z",
            last_seen="2025-12-11T15:00:00Z",
            count=5,
            severity="HIGH",
            lesson_id="lesson_123",
            github_issue="https://github.com/user/repo/issues/1",
        )

        data = record.to_dict()

        assert data["pattern_id"] == "pattern_test"
        assert data["anomaly_type"] == "order_amount"
        assert data["count"] == 5
        assert data["severity"] == "HIGH"
        assert data["lesson_id"] == "lesson_123"
        assert data["github_issue"] == "https://github.com/user/repo/issues/1"

    def test_from_dict(self):
        """Test creating record from dict."""
        data = {
            "pattern_id": "pattern_test",
            "anomaly_type": "order_amount",
            "first_seen": "2025-12-11T10:00:00Z",
            "last_seen": "2025-12-11T15:00:00Z",
            "count": 5,
            "severity": "HIGH",
            "lesson_id": "lesson_123",
            "github_issue": None,
        }

        record = RecurrenceRecord.from_dict(data)

        assert record.pattern_id == "pattern_test"
        assert record.anomaly_type == "order_amount"
        assert record.count == 5
        assert record.severity == "HIGH"
        assert record.lesson_id == "lesson_123"
        assert record.github_issue is None

    def test_round_trip_serialization(self):
        """Test record can be serialized and deserialized."""
        original = RecurrenceRecord(
            pattern_id="pattern_test",
            anomaly_type="order_amount",
            first_seen="2025-12-11T10:00:00Z",
            last_seen="2025-12-11T15:00:00Z",
            count=3,
            severity="MEDIUM",
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = RecurrenceRecord.from_dict(data)

        assert restored.pattern_id == original.pattern_id
        assert restored.anomaly_type == original.anomaly_type
        assert restored.count == original.count
        assert restored.severity == original.severity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
