#!/usr/bin/env python3
"""
Test Script for LLM Introspective Awareness Module

Tests:
1. LLMIntrospector - Self-consistency, epistemic uncertainty, self-critique
2. IntrospectiveCouncil - Combined analysis with LLM Council
3. UncertaintyTracker - Persistence and metrics

Usage:
    python scripts/test_introspective_awareness.py
    python scripts/test_introspective_awareness.py --live  # Use real LLM calls
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.introspective_council import (
    IntrospectiveCouncil,
    IntrospectiveTradeRecommendation,
    TradeDecision,
    create_introspective_council,
)
from src.core.llm_introspection import (
    ConfidenceLevel,
    EpistemicUncertaintyResult,
    IntrospectionResult,
    IntrospectionState,
    LLMIntrospector,
    SelfConsistencyResult,
    SelfCritiqueResult,
    UncertaintyType,
)
from src.core.uncertainty_tracker import (
    UncertaintySnapshot,
    UncertaintyTracker,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test data
SAMPLE_MARKET_DATA = {
    "symbol": "SPY",
    "price": 450.25,
    "volume": 85000000,
    "change_pct": 0.75,
    "rsi": 62.5,
    "macd": {"signal": "bullish", "histogram": 0.45},
    "moving_averages": {
        "sma_20": 445.10,
        "sma_50": 440.50,
        "sma_200": 425.00,
    },
    "sentiment": {
        "news": "positive",
        "social": "neutral",
    },
}


def create_mock_analyzer():
    """Create a mock analyzer for testing without API calls."""
    mock = MagicMock()
    mock.models = [MagicMock(value="mock-model")]

    # Mock async client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="DECISION: BUY\n\nBased on analysis..."))
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock.async_client = mock_client

    return mock


class TestLLMIntrospector:
    """Tests for LLMIntrospector class."""

    def __init__(self, use_live: bool = False):
        self.use_live = use_live

    async def run_tests(self) -> dict:
        """Run all introspector tests."""
        results = {
            "test_self_consistency": await self.test_self_consistency(),
            "test_epistemic_assessment": await self.test_epistemic_assessment(),
            "test_self_critique": await self.test_self_critique(),
            "test_full_introspection": await self.test_full_introspection(),
        }
        return results

    async def test_self_consistency(self) -> dict:
        """Test self-consistency analysis."""
        logger.info("Testing self-consistency analysis...")

        if self.use_live:
            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
        else:
            analyzer = create_mock_analyzer()

        introspector = LLMIntrospector(
            analyzer=analyzer,
            consistency_samples=3,  # Reduced for testing
        )

        try:
            result = await introspector._run_self_consistency(
                "Symbol: SPY\nPrice: $450.25\nRSI: 62.5\nMACD: Bullish"
            )

            assert isinstance(result, SelfConsistencyResult)
            assert result.decision in ["BUY", "SELL", "HOLD"]
            assert 0 <= result.confidence <= 1
            assert isinstance(result.vote_breakdown, dict)

            return {
                "status": "PASSED",
                "decision": result.decision,
                "confidence": result.confidence,
                "votes": result.vote_breakdown,
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}

    async def test_epistemic_assessment(self) -> dict:
        """Test epistemic uncertainty assessment."""
        logger.info("Testing epistemic uncertainty assessment...")

        if self.use_live:
            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
        else:
            analyzer = create_mock_analyzer()
            # Mock epistemic response
            mock_response = """
EPISTEMIC_SCORE: 45
EPISTEMIC_GAPS: earnings report pending, sector rotation unclear
ALEATORIC_SCORE: 35
ALEATORIC_FACTORS: market volatility, geopolitical events
DETAILED_ASSESSMENT: The analysis has moderate uncertainty...
"""
            analyzer.async_client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=MagicMock(content=mock_response))]
                )
            )

        introspector = LLMIntrospector(analyzer=analyzer)

        try:
            result = await introspector._run_epistemic_assessment(
                f"Symbol: SPY\nMarket Data: {json.dumps(SAMPLE_MARKET_DATA)}"
            )

            assert isinstance(result, EpistemicUncertaintyResult)
            assert 0 <= result.epistemic_score <= 100
            assert 0 <= result.aleatoric_score <= 100
            assert result.dominant_type in UncertaintyType

            return {
                "status": "PASSED",
                "epistemic_score": result.epistemic_score,
                "aleatoric_score": result.aleatoric_score,
                "dominant_type": result.dominant_type.value,
                "knowledge_gaps": result.knowledge_gaps,
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}

    async def test_self_critique(self) -> dict:
        """Test self-critique analysis."""
        logger.info("Testing self-critique analysis...")

        if self.use_live:
            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
        else:
            analyzer = create_mock_analyzer()
            mock_response = """
ASSUMPTIONS: Recent trend will continue, no major news events
POTENTIAL_ERRORS: May miss sentiment shift, RSI could reverse
CONFIDENCE_AFTER_CRITIQUE: 65
SHOULD_TRUST: YES
REASONING: The analysis is reasonable but should consider...
"""
            analyzer.async_client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    choices=[MagicMock(message=MagicMock(content=mock_response))]
                )
            )

        introspector = LLMIntrospector(analyzer=analyzer)

        try:
            result = await introspector._run_self_critique(
                "Symbol: SPY\nPrice: $450.25",
                initial_decision="BUY",
            )

            assert isinstance(result, SelfCritiqueResult)
            assert 0 <= result.confidence_after_critique <= 100
            assert isinstance(result.assumptions_made, list)
            assert isinstance(result.errors_found, list)

            return {
                "status": "PASSED",
                "confidence_after_critique": result.confidence_after_critique,
                "assumptions": result.assumptions_made,
                "potential_errors": result.errors_found,
                "should_trust": result.should_trust,
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}

    async def test_full_introspection(self) -> dict:
        """Test full introspection pipeline."""
        logger.info("Testing full introspection pipeline...")

        if self.use_live:
            from src.core.multi_llm_analysis import MultiLLMAnalyzer

            analyzer = MultiLLMAnalyzer()
        else:
            analyzer = create_mock_analyzer()

        introspector = LLMIntrospector(
            analyzer=analyzer,
            consistency_samples=3,
            strict_mode=True,
        )

        try:
            result = await introspector.analyze_with_introspection(
                market_data=SAMPLE_MARKET_DATA,
                symbol="SPY",
                context="Market showing bullish momentum",
            )

            assert isinstance(result, IntrospectionResult)
            assert result.decision in ["BUY", "SELL", "HOLD"]
            assert result.introspection_state in IntrospectionState
            assert result.confidence_level in ConfidenceLevel
            assert 0 <= result.aggregate_confidence <= 1
            assert 0 <= result.position_multiplier <= 1

            return {
                "status": "PASSED",
                "decision": result.decision,
                "introspection_state": result.introspection_state.value,
                "aggregate_confidence": result.aggregate_confidence,
                "confidence_level": result.confidence_level.value,
                "execute_trade": result.execute_trade,
                "position_multiplier": result.position_multiplier,
                "recommendation": result.recommendation,
                "processing_time_ms": result.processing_time_ms,
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}


class TestIntrospectiveCouncil:
    """Tests for IntrospectiveCouncil class."""

    def __init__(self, use_live: bool = False):
        self.use_live = use_live

    async def run_tests(self) -> dict:
        """Run all council tests."""
        results = {
            "test_analyze_trade": await self.test_analyze_trade(),
            "test_position_sizing": await self.test_position_sizing(),
            "test_metrics_tracking": await self.test_metrics_tracking(),
        }
        return results

    async def test_analyze_trade(self) -> dict:
        """Test full trade analysis with introspection."""
        logger.info("Testing introspective trade analysis...")

        if self.use_live:
            council = create_introspective_council(
                enable_introspection=True,
                strict_mode=True,
            )
        else:
            mock_analyzer = create_mock_analyzer()
            council = IntrospectiveCouncil(
                multi_llm_analyzer=mock_analyzer,
                enable_introspection=True,
                strict_mode=True,
            )

        try:
            result = await council.analyze_trade(
                symbol="SPY",
                market_data=SAMPLE_MARKET_DATA,
                news="Market sentiment positive after Fed meeting",
            )

            assert isinstance(result, IntrospectiveTradeRecommendation)
            assert result.symbol == "SPY"
            assert result.decision in TradeDecision
            assert 0 <= result.combined_confidence <= 1
            assert 0 <= result.position_multiplier <= 1

            return {
                "status": "PASSED",
                "symbol": result.symbol,
                "decision": result.decision.value,
                "action": result.action,
                "combined_confidence": result.combined_confidence,
                "epistemic_uncertainty": result.epistemic_uncertainty,
                "aleatoric_uncertainty": result.aleatoric_uncertainty,
                "position_multiplier": result.position_multiplier,
                "execute": result.execute,
                "recommendation": result.recommendation,
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e)}

    async def test_position_sizing(self) -> dict:
        """Test position sizing based on confidence."""
        logger.info("Testing confidence-based position sizing...")

        mock_analyzer = create_mock_analyzer()
        council = IntrospectiveCouncil(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,  # Disable for controlled test
        )

        # Test different confidence levels
        sizing_map = council.POSITION_SIZING

        results = {}
        for level, multiplier in sizing_map.items():
            results[level.value] = multiplier

        return {
            "status": "PASSED",
            "position_sizing_map": results,
            "very_high_size": sizing_map[ConfidenceLevel.VERY_HIGH],
            "low_size": sizing_map[ConfidenceLevel.LOW],
        }

    async def test_metrics_tracking(self) -> dict:
        """Test metrics tracking."""
        logger.info("Testing metrics tracking...")

        mock_analyzer = create_mock_analyzer()
        council = IntrospectiveCouncil(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )

        # Make a few analyses
        for symbol in ["SPY", "QQQ", "IWM"]:
            await council.analyze_trade(
                symbol=symbol,
                market_data=SAMPLE_MARKET_DATA,
            )

        metrics = council.get_metrics()

        return {
            "status": "PASSED",
            "recommendations_made": metrics["recommendations_made"],
            "trades_skipped": metrics["trades_skipped"],
            "average_confidence": metrics["average_confidence"],
        }


class TestUncertaintyTracker:
    """Tests for UncertaintyTracker class."""

    def run_tests(self) -> dict:
        """Run all tracker tests."""
        results = {
            "test_record_assessment": self.test_record_assessment(),
            "test_metrics_calculation": self.test_metrics_calculation(),
            "test_calibration_report": self.test_calibration_report(),
            "test_knowledge_gap_report": self.test_knowledge_gap_report(),
        }
        return results

    def test_record_assessment(self) -> dict:
        """Test recording uncertainty assessments."""
        logger.info("Testing uncertainty recording...")

        # Use non-persistent tracker for testing
        tracker = UncertaintyTracker(persist=False)

        snapshot = tracker.record(
            symbol="SPY",
            decision="BUY",
            epistemic_score=45.0,
            aleatoric_score=35.0,
            aggregate_confidence=0.72,
            consistency_score=0.85,
            vote_breakdown={"BUY": 4, "HOLD": 1},
            introspection_state="informed_guess",
            knowledge_gaps=["earnings pending", "sector rotation unclear"],
            trade_executed=True,
        )

        assert isinstance(snapshot, UncertaintySnapshot)
        assert snapshot.symbol == "SPY"
        assert snapshot.epistemic_score == 45.0

        return {
            "status": "PASSED",
            "recorded_symbol": snapshot.symbol,
            "epistemic_score": snapshot.epistemic_score,
            "knowledge_gaps": snapshot.knowledge_gaps,
        }

    def test_metrics_calculation(self) -> dict:
        """Test aggregate metrics calculation."""
        logger.info("Testing metrics calculation...")

        tracker = UncertaintyTracker(persist=False)

        # Record multiple assessments
        test_data = [
            {"symbol": "SPY", "epistemic": 40, "aleatoric": 30, "conf": 0.75},
            {"symbol": "QQQ", "epistemic": 60, "aleatoric": 45, "conf": 0.55},
            {"symbol": "IWM", "epistemic": 70, "aleatoric": 50, "conf": 0.40},
        ]

        for data in test_data:
            tracker.record(
                symbol=data["symbol"],
                decision="BUY",
                epistemic_score=data["epistemic"],
                aleatoric_score=data["aleatoric"],
                aggregate_confidence=data["conf"],
                consistency_score=0.8,
                vote_breakdown={"BUY": 3},
            )

        metrics = tracker.get_metrics()

        # Verify averages
        expected_avg_epistemic = (40 + 60 + 70) / 3
        _expected_avg_conf = (0.75 + 0.55 + 0.40) / 3

        return {
            "status": "PASSED",
            "total_assessments": metrics.total_assessments,
            "avg_epistemic": metrics.avg_epistemic,
            "expected_avg_epistemic": expected_avg_epistemic,
            "avg_confidence": metrics.avg_confidence,
            "high_uncertainty_count": metrics.high_uncertainty_count,
        }

    def test_calibration_report(self) -> dict:
        """Test calibration report generation."""
        logger.info("Testing calibration report...")

        tracker = UncertaintyTracker(persist=False)

        # Record assessments with outcomes
        # High confidence trades
        for _ in range(5):
            snapshot = tracker.record(
                symbol="SPY",
                decision="BUY",
                epistemic_score=30,
                aleatoric_score=25,
                aggregate_confidence=0.85,
                consistency_score=0.9,
                vote_breakdown={"BUY": 5},
                trade_executed=True,
            )
            # Record winning outcome
            tracker.record_outcome(
                symbol="SPY",
                timestamp=snapshot.timestamp,
                outcome="WIN",
                pnl=50.0,
            )

        # Low confidence trades
        for _ in range(5):
            snapshot = tracker.record(
                symbol="QQQ",
                decision="BUY",
                epistemic_score=70,
                aleatoric_score=60,
                aggregate_confidence=0.35,
                consistency_score=0.5,
                vote_breakdown={"BUY": 2, "HOLD": 3},
                trade_executed=True,
            )
            # Record losing outcome
            tracker.record_outcome(
                symbol="QQQ",
                timestamp=snapshot.timestamp,
                outcome="LOSS",
                pnl=-30.0,
            )

        report = tracker.get_calibration_report()

        return {
            "status": "PASSED",
            "total_assessments": report["total_assessments"],
            "high_conf_win_rate": report["high_confidence_win_rate"],
            "low_conf_win_rate": report["low_confidence_win_rate"],
            "calibration_gap": report["calibration_gap"],
            "is_well_calibrated": report["is_well_calibrated"],
            "recommendation": report["recommendation"],
        }

    def test_knowledge_gap_report(self) -> dict:
        """Test knowledge gap analysis."""
        logger.info("Testing knowledge gap report...")

        tracker = UncertaintyTracker(persist=False)

        # Record assessments with various knowledge gaps
        gaps_data = [
            ["earnings pending", "sector rotation"],
            ["earnings pending", "fed policy"],
            ["earnings pending", "geopolitical risk"],
            ["sector rotation", "volatility regime"],
        ]

        for gaps in gaps_data:
            tracker.record(
                symbol="TEST",
                decision="HOLD",
                epistemic_score=55,
                aleatoric_score=40,
                aggregate_confidence=0.6,
                consistency_score=0.7,
                vote_breakdown={"HOLD": 3},
                knowledge_gaps=gaps,
            )

        report = tracker.get_knowledge_gap_report()

        return {
            "status": "PASSED",
            "total_unique_gaps": report["total_unique_gaps"],
            "top_gaps": report["top_10_gaps"][:5],
            "high_epistemic_rate": report["high_epistemic_rate"],
            "recommendation": report["recommendation"],
        }


async def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description="Test LLM Introspective Awareness Module")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live LLM API calls (requires OPENROUTER_API_KEY)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("LLM INTROSPECTIVE AWARENESS MODULE - TEST SUITE")
    print("=" * 60)
    print(f"Mode: {'LIVE API' if args.live else 'MOCK'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60 + "\n")

    all_results = {}

    # Test LLMIntrospector
    print("\n--- Testing LLMIntrospector ---")
    introspector_tests = TestLLMIntrospector(use_live=args.live)
    all_results["LLMIntrospector"] = await introspector_tests.run_tests()

    # Test IntrospectiveCouncil
    print("\n--- Testing IntrospectiveCouncil ---")
    council_tests = TestIntrospectiveCouncil(use_live=args.live)
    all_results["IntrospectiveCouncil"] = await council_tests.run_tests()

    # Test UncertaintyTracker
    print("\n--- Testing UncertaintyTracker ---")
    tracker_tests = TestUncertaintyTracker()
    all_results["UncertaintyTracker"] = tracker_tests.run_tests()

    # Print results
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    total_tests = 0
    passed_tests = 0

    for component, tests in all_results.items():
        print(f"\n{component}:")
        for test_name, result in tests.items():
            total_tests += 1
            status = result.get("status", "UNKNOWN")
            if status == "PASSED":
                passed_tests += 1
                print(f"  ✅ {test_name}: PASSED")
            else:
                print(f"  ❌ {test_name}: {status}")
                if "error" in result:
                    print(f"     Error: {result['error']}")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed_tests}/{total_tests} tests passed")
    print("=" * 60)

    # Save results
    results_file = Path("data/introspection_test_results.json")
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "mode": "live" if args.live else "mock",
                "results": all_results,
                "summary": {
                    "total": total_tests,
                    "passed": passed_tests,
                    "failed": total_tests - passed_tests,
                },
            },
            f,
            indent=2,
            default=str,
        )
    print(f"\nResults saved to: {results_file}")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
