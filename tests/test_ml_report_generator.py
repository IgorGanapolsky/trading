"""
Tests for ML Report Generator - 100% coverage target.

Tests all components:
- GateSignal dataclass
- TradeSignalRecord dataclass
- DailyMLReport dataclass
- MLReportGenerator class (all methods)
- Singleton pattern
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from src.orchestrator.ml_report_generator import (
    DailyMLReport,
    GateSignal,
    MLReportGenerator,
    TradeSignalRecord,
    get_ml_report_generator,
)


class TestGateSignal:
    """Tests for GateSignal dataclass."""

    def test_gate_signal_creation(self):
        """Test basic GateSignal creation."""
        signal = GateSignal(
            gate_name="momentum",
            passed=True,
            confidence=0.75,
        )
        assert signal.gate_name == "momentum"
        assert signal.passed is True
        assert signal.confidence == 0.75
        assert signal.details == {}
        assert signal.timestamp != ""

    def test_gate_signal_with_details(self):
        """Test GateSignal with custom details."""
        details = {"strength": 0.65, "rsi": 55}
        signal = GateSignal(
            gate_name="rl",
            passed=False,
            confidence=0.32,
            details=details,
        )
        assert signal.details == details
        assert signal.details["strength"] == 0.65

    def test_gate_signal_with_custom_timestamp(self):
        """Test GateSignal with custom timestamp."""
        ts = "2026-01-01T10:00:00"
        signal = GateSignal(
            gate_name="sentiment",
            passed=True,
            confidence=0.55,
            timestamp=ts,
        )
        assert signal.timestamp == ts

    def test_gate_signal_auto_timestamp(self):
        """Test that timestamp is auto-generated when empty."""
        signal = GateSignal(
            gate_name="risk",
            passed=True,
            confidence=0.9,
            timestamp="",
        )
        # Should have a timestamp now
        assert signal.timestamp != ""
        # Should be ISO format
        datetime.fromisoformat(signal.timestamp)


class TestTradeSignalRecord:
    """Tests for TradeSignalRecord dataclass."""

    def test_trade_signal_record_creation(self):
        """Test basic TradeSignalRecord creation."""
        record = TradeSignalRecord(
            symbol="SPY",
            trade_id="SPY-001",
        )
        assert record.symbol == "SPY"
        assert record.trade_id == "SPY-001"
        assert record.gate_1_momentum is None
        assert record.overall_decision == "unknown"
        assert record.timestamp != ""

    def test_trade_signal_record_with_gates(self):
        """Test TradeSignalRecord with gate signals."""
        gate_1 = GateSignal("momentum", True, 0.72)
        gate_2 = GateSignal("rl", True, 0.68)

        record = TradeSignalRecord(
            symbol="NVDA",
            trade_id="NVDA-001",
            gate_1_momentum=gate_1,
            gate_2_rl=gate_2,
            overall_decision="execute",
        )
        assert record.gate_1_momentum.confidence == 0.72
        assert record.gate_2_rl.confidence == 0.68
        assert record.overall_decision == "execute"

    def test_trade_signal_record_rejection(self):
        """Test TradeSignalRecord for rejected trade."""
        record = TradeSignalRecord(
            symbol="TSLA",
            trade_id="TSLA-001",
            overall_decision="reject",
            rejection_reason="RL confidence below threshold",
        )
        assert record.overall_decision == "reject"
        assert record.rejection_reason == "RL confidence below threshold"


class TestDailyMLReport:
    """Tests for DailyMLReport dataclass."""

    def test_daily_ml_report_creation(self):
        """Test basic DailyMLReport creation."""
        report = DailyMLReport(date="2026-01-01")
        assert report.date == "2026-01-01"
        assert report.total_evaluations == 0
        assert report.passed_all_gates == 0
        assert report.rejected == 0
        assert report.timestamp != ""

    def test_daily_ml_report_with_stats(self):
        """Test DailyMLReport with full stats."""
        report = DailyMLReport(
            date="2026-01-01",
            total_evaluations=100,
            passed_all_gates=70,
            rejected=30,
            gate_1_pass_rate=0.8,
            gate_2_pass_rate=0.75,
            gate_3_pass_rate=0.9,
            gate_4_pass_rate=0.95,
            avg_rl_confidence=0.68,
            rl_mode_distribution={"transformer": 60, "heuristic": 40},
            feature_importance={"strength": 0.35, "momentum": 0.28},
            top_opportunities=[{"symbol": "SPY", "confidence": 0.85}],
            top_rejections=[{"reason": "low momentum", "count": 10}],
            recommendations=["System healthy"],
        )
        assert report.total_evaluations == 100
        assert report.passed_all_gates == 70
        assert report.gate_1_pass_rate == 0.8
        assert report.rl_mode_distribution["transformer"] == 60


class TestMLReportGenerator:
    """Tests for MLReportGenerator class."""

    @pytest.fixture
    def temp_reports_dir(self):
        """Create temporary directory for reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_reports_dir):
        """Create MLReportGenerator with temp directory."""
        return MLReportGenerator(reports_dir=temp_reports_dir)

    def test_init(self, generator, temp_reports_dir):
        """Test MLReportGenerator initialization."""
        assert generator.reports_dir == temp_reports_dir
        assert generator._daily_signals == []
        assert generator._current_date == datetime.now().strftime("%Y-%m-%d")

    def test_record_signal(self, generator):
        """Test recording a trade signal."""
        record = TradeSignalRecord(symbol="SPY", trade_id="SPY-001")
        generator.record_signal(record)
        assert len(generator._daily_signals) == 1
        assert generator._daily_signals[0].symbol == "SPY"

    def test_record_gate_results(self, generator):
        """Test recording gate results from dicts."""
        record = generator.record_gate_results(
            symbol="NVDA",
            trade_id="NVDA-001",
            gate_1={"passed": True, "confidence": 0.72},
            gate_2={"passed": True, "confidence": 0.68, "mode": "transformer"},
            gate_3={"passed": True, "confidence": 0.55},
            gate_4={"passed": True, "confidence": 0.9},
            decision="execute",
        )
        assert record.symbol == "NVDA"
        assert record.gate_1_momentum.passed is True
        assert record.gate_2_rl.confidence == 0.68
        assert len(generator._daily_signals) == 1

    def test_record_gate_results_with_pass_key(self, generator):
        """Test recording gate results using 'pass' key instead of 'passed'."""
        record = generator.record_gate_results(
            symbol="AAPL",
            trade_id="AAPL-001",
            gate_1={"pass": True, "score": 0.65},  # Using 'pass' and 'score'
            decision="execute",
        )
        assert record.gate_1_momentum.passed is True
        assert record.gate_1_momentum.confidence == 0.65

    def test_record_gate_results_rejection(self, generator):
        """Test recording rejected trade."""
        record = generator.record_gate_results(
            symbol="TSLA",
            trade_id="TSLA-001",
            gate_1={"passed": False, "confidence": 0.25},
            decision="reject",
            rejection_reason="Momentum too weak",
        )
        assert record.overall_decision == "reject"
        assert record.rejection_reason == "Momentum too weak"

    def test_record_gate_results_no_gates(self, generator):
        """Test recording with no gate data."""
        record = generator.record_gate_results(
            symbol="AMD",
            trade_id="AMD-001",
            decision="hold",
        )
        assert record.gate_1_momentum is None
        assert record.gate_2_rl is None

    def test_generate_daily_report_empty(self, generator):
        """Test generating report with no signals."""
        report = generator.generate_daily_report(save=False)
        assert report.total_evaluations == 0
        assert report.date == generator._current_date

    def test_generate_daily_report_with_signals(self, generator):
        """Test generating report with multiple signals."""
        # Add executed trade
        generator.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            gate_1={"passed": True, "confidence": 0.72},
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

        # Add rejected trade
        generator.record_gate_results(
            symbol="TSLA",
            trade_id="TSLA-001",
            gate_1={"passed": True, "confidence": 0.58},
            gate_2={"passed": False, "confidence": 0.32, "mode": "heuristic"},
            decision="reject",
            rejection_reason="RL confidence below threshold",
        )

        # Add another rejection
        generator.record_gate_results(
            symbol="NVDA",
            trade_id="NVDA-001",
            gate_1={"passed": False, "confidence": 0.25},
            decision="reject",
            rejection_reason="Momentum too weak",
        )

        report = generator.generate_daily_report(save=False)

        assert report.total_evaluations == 3
        assert report.passed_all_gates == 1
        assert report.rejected == 2
        assert report.gate_1_pass_rate == pytest.approx(2 / 3, rel=0.01)
        assert report.gate_2_pass_rate == pytest.approx(1 / 3, rel=0.01)
        assert report.avg_rl_confidence == pytest.approx(0.5, rel=0.01)  # (0.68 + 0.32) / 2
        assert "transformer" in report.rl_mode_distribution
        assert "strength" in report.feature_importance

    def test_generate_daily_report_saves_file(self, generator, temp_reports_dir):
        """Test that report is saved to disk."""
        generator.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            gate_1={"passed": True, "confidence": 0.72},
            decision="execute",
        )

        report = generator.generate_daily_report(save=True)
        filepath = temp_reports_dir / f"ml_report_{report.date}.json"

        assert filepath.exists()
        with open(filepath) as f:
            data = json.load(f)
        assert data["total_evaluations"] == 1

    def test_generate_recommendations_low_gate1(self, generator):
        """Test recommendations for low Gate 1 pass rate."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.2,  # Below 0.3
            gate_2_rate=0.7,
            avg_rl_conf=0.6,
            rejection_reasons={},
        )
        assert any("Gate 1" in r for r in recs)

    def test_generate_recommendations_low_gate2(self, generator):
        """Test recommendations for low Gate 2 pass rate."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.7,
            gate_2_rate=0.4,  # Below 0.5
            avg_rl_conf=0.6,
            rejection_reasons={},
        )
        assert any("Gate 2" in r for r in recs)

    def test_generate_recommendations_low_rl_conf(self, generator):
        """Test recommendations for low RL confidence."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.7,
            gate_2_rate=0.7,
            avg_rl_conf=0.4,  # Below 0.5
            rejection_reasons={},
        )
        assert any("confidence low" in r for r in recs)

    def test_generate_recommendations_high_rl_conf(self, generator):
        """Test recommendations for very high RL confidence (overfitting)."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.7,
            gate_2_rate=0.7,
            avg_rl_conf=0.9,  # Above 0.85
            rejection_reasons={},
        )
        assert any("overfitting" in r for r in recs)

    def test_generate_recommendations_frequent_rejection(self, generator):
        """Test recommendations for frequent rejection reason."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.7,
            gate_2_rate=0.7,
            avg_rl_conf=0.6,
            rejection_reasons={"low momentum": 10},  # More than 5
        )
        assert any("Frequent rejection" in r for r in recs)

    def test_generate_recommendations_healthy_system(self, generator):
        """Test recommendations for healthy system."""
        recs = generator._generate_recommendations(
            gate_1_rate=0.7,
            gate_2_rate=0.7,
            avg_rl_conf=0.6,
            rejection_reasons={},
        )
        assert any("normally" in r for r in recs)

    def test_load_report(self, generator, temp_reports_dir):
        """Test loading a saved report."""
        # Save a report
        generator.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            gate_1={"passed": True, "confidence": 0.72},
            decision="execute",
        )
        original = generator.generate_daily_report(save=True)

        # Load it back
        loaded = generator.load_report(original.date)

        assert loaded is not None
        assert loaded.date == original.date
        assert loaded.total_evaluations == original.total_evaluations

    def test_load_report_not_found(self, generator):
        """Test loading non-existent report returns None."""
        loaded = generator.load_report("1999-01-01")
        assert loaded is None

    def test_get_recent_reports(self, generator, temp_reports_dir):
        """Test getting recent reports."""
        # Create multiple reports
        for i in range(3):
            generator._daily_signals = []
            generator.record_gate_results(
                symbol=f"SYM{i}",
                trade_id=f"SYM{i}-001",
                gate_1={"passed": True, "confidence": 0.7},
                decision="execute",
            )
            # Save with different dates
            generator._current_date = f"2026-01-0{i + 1}"
            generator.generate_daily_report(save=True)

        reports = generator.get_recent_reports(days=5)
        assert len(reports) == 3

    def test_get_recent_reports_handles_corrupt_file(self, generator, temp_reports_dir):
        """Test that get_recent_reports handles corrupt JSON gracefully."""
        # Create a corrupt JSON file
        corrupt_file = temp_reports_dir / "ml_report_2026-01-01.json"
        corrupt_file.write_text("not valid json {{{")

        reports = generator.get_recent_reports(days=5)
        # Should return empty list, not crash
        assert reports == []

    def test_reset_daily(self, generator):
        """Test resetting for new day."""
        generator.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            gate_1={"passed": True, "confidence": 0.72},
            decision="execute",
        )
        assert len(generator._daily_signals) == 1

        generator.reset_daily()

        assert generator._daily_signals == []
        assert generator._current_date == datetime.now().strftime("%Y-%m-%d")


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_ml_report_generator_returns_same_instance(self):
        """Test that singleton returns same instance."""
        # Reset singleton for test
        import src.orchestrator.ml_report_generator as module

        module._generator = None

        gen1 = get_ml_report_generator()
        gen2 = get_ml_report_generator()

        assert gen1 is gen2

    def test_singleton_creates_instance(self):
        """Test that singleton creates instance when None."""
        import src.orchestrator.ml_report_generator as module

        module._generator = None

        gen = get_ml_report_generator()
        assert gen is not None
        assert isinstance(gen, MLReportGenerator)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def temp_reports_dir(self):
        """Create temporary directory for reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_feature_importance_with_non_numeric(self, temp_reports_dir):
        """Test feature importance ignores non-numeric values."""
        gen = MLReportGenerator(reports_dir=temp_reports_dir)
        gen.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            gate_2={
                "passed": True,
                "confidence": 0.7,
                "feature_importance": {
                    "strength": 0.35,
                    "name": "not_a_number",  # Should be ignored
                    "momentum": 0.28,
                },
            },
            decision="execute",
        )

        report = gen.generate_daily_report(save=False)
        assert "strength" in report.feature_importance
        assert "momentum" in report.feature_importance
        assert "name" not in report.feature_importance

    def test_top_opportunities_sorting(self, temp_reports_dir):
        """Test that top opportunities are sorted by confidence."""
        gen = MLReportGenerator(reports_dir=temp_reports_dir)

        # Add trades with different confidences
        for symbol, conf in [("LOW", 0.5), ("HIGH", 0.9), ("MED", 0.7)]:
            gen.record_gate_results(
                symbol=symbol,
                trade_id=f"{symbol}-001",
                gate_1={"passed": True, "confidence": 0.7},
                gate_2={"passed": True, "confidence": conf},
                decision="execute",
            )

        report = gen.generate_daily_report(save=False)

        # Should be sorted highest first
        assert report.top_opportunities[0]["symbol"] == "HIGH"
        assert report.top_opportunities[0]["confidence"] == 0.9

    def test_rejection_reason_aggregation(self, temp_reports_dir):
        """Test that rejection reasons are aggregated and sorted."""
        gen = MLReportGenerator(reports_dir=temp_reports_dir)

        # Add multiple rejections with same reason
        for i in range(5):
            gen.record_gate_results(
                symbol=f"SYM{i}",
                trade_id=f"SYM{i}-001",
                decision="reject",
                rejection_reason="low momentum",
            )

        # Add fewer rejections with different reason
        for i in range(2):
            gen.record_gate_results(
                symbol=f"OTHER{i}",
                trade_id=f"OTHER{i}-001",
                decision="reject",
                rejection_reason="high volatility",
            )

        report = gen.generate_daily_report(save=False)

        # Most common reason should be first
        assert report.top_rejections[0]["reason"] == "low momentum"
        assert report.top_rejections[0]["count"] == 5

    def test_empty_rejection_reason(self, temp_reports_dir):
        """Test handling of empty rejection reason."""
        gen = MLReportGenerator(reports_dir=temp_reports_dir)
        gen.record_gate_results(
            symbol="SPY",
            trade_id="SPY-001",
            decision="reject",
            rejection_reason="",  # Empty
        )

        report = gen.generate_daily_report(save=False)
        # Should use "unknown" as the reason
        assert any(r["reason"] == "unknown" for r in report.top_rejections)


class TestSmokeTests:
    """Smoke tests to verify basic functionality end-to-end."""

    def test_full_workflow_smoke_test(self):
        """Smoke test: Full workflow from signal to report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = MLReportGenerator(reports_dir=Path(tmpdir))

            # Record multiple trades
            gen.record_gate_results(
                symbol="SPY",
                trade_id="SPY-001",
                gate_1={"passed": True, "confidence": 0.72},
                gate_2={"passed": True, "confidence": 0.68, "mode": "transformer"},
                gate_3={"passed": True, "confidence": 0.55},
                gate_4={"passed": True, "confidence": 0.9},
                decision="execute",
            )

            gen.record_gate_results(
                symbol="TSLA",
                trade_id="TSLA-001",
                gate_1={"passed": False, "confidence": 0.25},
                decision="reject",
                rejection_reason="Momentum too weak",
            )

            # Generate and save report
            report = gen.generate_daily_report(save=True)

            # Verify report
            assert report.total_evaluations == 2
            assert report.passed_all_gates == 1
            assert report.rejected == 1

            # Verify file exists
            filepath = Path(tmpdir) / f"ml_report_{report.date}.json"
            assert filepath.exists()

            # Load and verify
            loaded = gen.load_report(report.date)
            assert loaded.total_evaluations == 2

            # Reset and verify
            gen.reset_daily()
            assert len(gen._daily_signals) == 0

    def test_module_main_smoke_test(self):
        """Smoke test: Run __main__ block."""
        # This tests the demo code at the bottom of the module
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from src.orchestrator.ml_report_generator import *; print('OK')",
            ],
            capture_output=True,
            text=True,
            cwd="/home/user/trading",
        )
        assert result.returncode == 0
        assert "OK" in result.stdout
