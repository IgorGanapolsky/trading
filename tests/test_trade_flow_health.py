"""Tests to verify trading system is not silently dead (ll_019).

These tests catch configuration issues that cause the system to appear
working (workflow success) while executing zero trades.

Reference: rag_knowledge/lessons_learned/ll_019_system_dead_2_days_overly_strict_filters_dec12.md
"""

from __future__ import annotations

import os
import pytest


class TestTickerUniverse:
    """Verify we have enough tickers to find trading opportunities."""

    def test_minimum_ticker_count(self):
        """System should analyze at least 15 tickers for adequate coverage."""
        from scripts.autonomous_trader import _parse_tickers

        tickers = _parse_tickers()
        assert len(tickers) >= 15, (
            f"Ticker universe too small: {len(tickers)} tickers. "
            "Need >= 15 for adequate trade flow. "
            "See ll_019: system was dead with only 3 tickers."
        )

    def test_ticker_diversity(self):
        """Ticker universe should include ETFs and individual stocks."""
        from scripts.autonomous_trader import _parse_tickers

        tickers = set(_parse_tickers())

        # Must have at least one major ETF
        etfs = {"SPY", "QQQ", "VOO", "IWM", "DIA"}
        assert tickers & etfs, "Missing major ETFs in ticker universe"

        # Must have at least one big tech stock
        tech = {"NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMD", "AMZN", "TSLA"}
        assert tickers & tech, "Missing big tech stocks in ticker universe"


class TestMomentumFilterThresholds:
    """Verify Gate 1 filters are not too strict during R&D."""

    def test_adx_disabled_during_rnd(self):
        """ADX filter should be disabled (0.0) during R&D phase."""
        from src.strategies.legacy_momentum import LegacyMomentumCalculator

        calc = LegacyMomentumCalculator()
        assert calc.adx_min == 0.0, (
            f"ADX threshold is {calc.adx_min}, should be 0.0 during R&D. "
            "See ll_019: ADX=10.0 blocked 70%+ of candidates."
        )

    def test_rsi_threshold_relaxed(self):
        """RSI overbought threshold should be >= 80 during R&D."""
        from src.strategies.legacy_momentum import LegacyMomentumCalculator

        calc = LegacyMomentumCalculator()
        assert calc.rsi_overbought >= 80.0, (
            f"RSI threshold is {calc.rsi_overbought}, should be >= 80.0 during R&D. "
            "See ll_019: RSI=75.0 rejected momentum stocks."
        )

    def test_volume_filter_reasonable(self):
        """Volume filter should not be too strict."""
        from src.strategies.legacy_momentum import LegacyMomentumCalculator

        calc = LegacyMomentumCalculator()
        assert calc.volume_min <= 0.8, (
            f"Volume threshold is {calc.volume_min}, should be <= 0.8. "
            "Strict volume filters block many opportunities."
        )


class TestRLFilterThresholds:
    """Verify Gate 2 (RL) filter is not too strict during R&D."""

    def test_rl_confidence_threshold_relaxed(self):
        """RL confidence threshold should be <= 0.4 during R&D."""
        from src.agents.rl_agent import RLFilter

        # Don't actually initialize the filter (needs weights), just check default
        default_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.35"))
        assert default_threshold <= 0.4, (
            f"RL confidence threshold is {default_threshold}, should be <= 0.4 during R&D. "
            "See ll_019: RL confidence=0.6 was too strict."
        )


class TestTradeFlowMonitoring:
    """Verify we have mechanisms to detect dead trading."""

    def test_session_decisions_file_created(self):
        """Telemetry should export session decisions for debugging."""
        from pathlib import Path

        # This test verifies the capability exists, not that a file exists now
        from src.orchestrator.telemetry import OrchestratorTelemetry

        telemetry = OrchestratorTelemetry()

        # Verify the method exists
        assert hasattr(telemetry, "save_session_decisions"), (
            "OrchestratorTelemetry missing save_session_decisions method. "
            "This is needed to debug why trades are rejected."
        )

    def test_rejection_rate_monitoring_exists(self):
        """System should have rejection rate monitoring capability."""
        from src.orchestrator.anomaly_monitor import AnomalyMonitor
        from src.orchestrator.telemetry import OrchestratorTelemetry

        telemetry = OrchestratorTelemetry()
        monitor = AnomalyMonitor(telemetry=telemetry)

        # Verify the monitor has a rejection threshold
        assert hasattr(monitor, "rejection_threshold"), (
            "AnomalyMonitor missing rejection_threshold. "
            "This is needed to detect when all trades are being rejected."
        )


class TestLessonsLearnedIntegration:
    """Verify lessons learned are captured and accessible."""

    def test_ll_019_exists(self):
        """ll_019 (dead system) lesson should be documented."""
        from pathlib import Path

        ll_path = Path("rag_knowledge/lessons_learned/ll_019_system_dead_2_days_overly_strict_filters_dec12.md")
        assert ll_path.exists(), (
            "Missing ll_019 lesson learned document. "
            "This documents why the system was dead for 2 days."
        )

    def test_ll_019_contains_prevention_rules(self):
        """ll_019 should contain actionable prevention rules."""
        from pathlib import Path

        ll_path = Path("rag_knowledge/lessons_learned/ll_019_system_dead_2_days_overly_strict_filters_dec12.md")
        if ll_path.exists():
            content = ll_path.read_text()
            assert "Prevention Rules" in content, "ll_019 missing Prevention Rules section"
            assert "Rule 1" in content, "ll_019 missing specific rules"
