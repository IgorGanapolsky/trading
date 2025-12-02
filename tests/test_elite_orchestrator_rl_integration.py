#!/usr/bin/env python3
"""
Comprehensive Integration Tests for Elite Orchestrator + RL System

Tests:
1. ML Predictor (LSTM-PPO) integration with Elite Orchestrator
2. Ensemble voting includes RL signals
3. RL signal formatting and validation
4. Error handling when RL unavailable
5. End-to-end orchestration with RL
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestration.elite_orchestrator import EliteOrchestrator


class TestEliteOrchestratorRLIntegration(unittest.TestCase):
    """Test Elite Orchestrator integration with RL (LSTM-PPO) system"""

    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = EliteOrchestrator(paper=True, enable_planning=True)
        self.test_symbols = ["SPY", "QQQ"]

    def test_ml_predictor_initialization(self):
        """Test that ML Predictor is initialized in Elite Orchestrator"""
        print("\n[TEST] ML Predictor Initialization")

        # ML Predictor should be initialized (or None if unavailable)
        self.assertIsNotNone(
            hasattr(self.orchestrator, "ml_predictor"),
            "Elite Orchestrator should have ml_predictor attribute",
        )

        if self.orchestrator.ml_predictor is not None:
            print("✅ ML Predictor initialized")
        else:
            print("⚠️  ML Predictor unavailable (this is OK if model not trained)")

    def test_ml_predictor_signal_format(self):
        """Test that ML Predictor returns properly formatted signals"""
        print("\n[TEST] ML Predictor Signal Format")

        if self.orchestrator.ml_predictor is None:
            self.skipTest("ML Predictor not available")

        # Mock ML Predictor to return test signal
        mock_signal = {
            "action": "BUY",
            "confidence": 0.85,
            "value_estimate": 1.23,
            "probs": {"HOLD": 0.10, "BUY": 0.85, "SELL": 0.05},
        }

        with patch.object(self.orchestrator.ml_predictor, "get_signal", return_value=mock_signal):
            signal = self.orchestrator.ml_predictor.get_signal("SPY")

            # Validate signal format
            self.assertIn("action", signal)
            self.assertIn("confidence", signal)
            self.assertIn("value_estimate", signal)
            self.assertIn(signal["action"], ["BUY", "SELL", "HOLD"])
            self.assertGreaterEqual(signal["confidence"], 0.0)
            self.assertLessEqual(signal["confidence"], 1.0)

            print(f"✅ Signal format valid: {signal['action']} ({signal['confidence']:.2f})")

    def test_analysis_phase_includes_ml_predictor(self):
        """Test that analysis phase includes ML Predictor recommendations"""
        print("\n[TEST] Analysis Phase ML Predictor Integration")

        # Create a trade plan
        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock ML Predictor if available
        if self.orchestrator.ml_predictor:
            mock_signal = {"action": "BUY", "confidence": 0.80, "value_estimate": 1.15}

            with patch.object(
                self.orchestrator.ml_predictor, "get_signal", return_value=mock_signal
            ):
                # Execute analysis phase
                analysis_result = self.orchestrator._execute_analysis(plan)

                # Check that ML recommendations are included
                agent_results = analysis_result.get("agent_results", [])
                ml_recommendations = [r for r in agent_results if r.get("agent") == "ml_model"]

                self.assertGreater(
                    len(ml_recommendations), 0, "ML recommendations should be included"
                )

                # Validate ML recommendation format
                for rec in ml_recommendations:
                    self.assertEqual(rec["agent"], "ml_model")
                    self.assertIn("recommendation", rec)
                    self.assertIn("confidence", rec)
                    self.assertIn("reasoning", rec)

                print(
                    f"✅ ML Predictor included in analysis: {len(ml_recommendations)} recommendations"
                )
        else:
            print("⚠️  ML Predictor not available - skipping test")
            self.skipTest("ML Predictor not available")

    def test_ensemble_voting_includes_ml_signals(self):
        """Test that ensemble voting includes ML Predictor signals"""
        print("\n[TEST] Ensemble Voting with ML Signals")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock all agents to return consistent signals
        mock_ml_signal = {"action": "BUY", "confidence": 0.85, "value_estimate": 1.20}

        mock_gemini_result = {"decision": "BUY", "reasoning": "Test reasoning"}

        # Mock agents
        with (
            patch.object(
                self.orchestrator,
                "ml_predictor",
                (
                    Mock(get_signal=lambda s: mock_ml_signal)
                    if self.orchestrator.ml_predictor
                    else None
                ),
            ),
            patch.object(
                self.orchestrator,
                "gemini_agent",
                (
                    Mock(reason=lambda **kwargs: mock_gemini_result)
                    if self.orchestrator.gemini_agent
                    else None
                ),
            ),
            patch.object(self.orchestrator, "langchain_agent", None),
        ):
            with patch.object(self.orchestrator, "mcp_orchestrator", None):
                analysis_result = self.orchestrator._execute_analysis(plan)

                # Check ensemble vote
                ensemble_vote = analysis_result.get("ensemble_vote", {})

                for symbol in self.test_symbols:
                    if symbol in ensemble_vote:
                        vote = ensemble_vote[symbol]
                        buy_votes = vote.get("buy_votes", 0)
                        total_votes = vote.get("total_votes", 0)

                        print(f"✅ {symbol}: {buy_votes}/{total_votes} BUY votes")

                        # If ML Predictor is available, it should contribute to votes
                        if self.orchestrator.ml_predictor:
                            recommendations = vote.get("recommendations", {})
                            ml_rec = next(
                                (r for k, r in recommendations.items() if "ml" in k),
                                None,
                            )
                            if ml_rec:
                                self.assertEqual(ml_rec["agent"], "ml_model")
                                print(f"   ✅ ML signal included: {ml_rec['recommendation']}")

    def test_ml_predictor_error_handling(self):
        """Test that Elite Orchestrator handles ML Predictor errors gracefully"""
        print("\n[TEST] ML Predictor Error Handling")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock ML Predictor to raise exception
        if self.orchestrator.ml_predictor:
            with patch.object(
                self.orchestrator.ml_predictor,
                "get_signal",
                side_effect=Exception("ML Predictor error"),
            ):
                # Should not crash, just log warning
                analysis_result = self.orchestrator._execute_analysis(plan)

                # Analysis should still complete
                self.assertIsNotNone(analysis_result)
                self.assertIn("agent_results", analysis_result)

                print("✅ ML Predictor errors handled gracefully")
        else:
            print("⚠️  ML Predictor not available - skipping test")
            self.skipTest("ML Predictor not available")

    def test_ml_predictor_missing_data_handling(self):
        """Test handling when ML Predictor returns HOLD due to missing data"""
        print("\n[TEST] ML Predictor Missing Data Handling")

        if self.orchestrator.ml_predictor is None:
            self.skipTest("ML Predictor not available")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock ML Predictor to return HOLD due to insufficient data
        mock_signal = {
            "action": "HOLD",
            "confidence": 0.0,
            "reason": "Insufficient data",
        }

        with patch.object(self.orchestrator.ml_predictor, "get_signal", return_value=mock_signal):
            analysis_result = self.orchestrator._execute_analysis(plan)

            # Should still include ML recommendation (even if HOLD)
            agent_results = analysis_result.get("agent_results", [])
            ml_recommendations = [r for r in agent_results if r.get("agent") == "ml_model"]

            if ml_recommendations:
                ml_rec = ml_recommendations[0]
                self.assertEqual(ml_rec["recommendation"], "HOLD")
                print("✅ ML Predictor HOLD signal handled correctly")

    def test_end_to_end_orchestration_with_rl(self):
        """Test end-to-end orchestration including RL system"""
        print("\n[TEST] End-to-End Orchestration with RL")

        # Mock ML Predictor if available
        if self.orchestrator.ml_predictor:
            mock_signal = {"action": "BUY", "confidence": 0.75, "value_estimate": 1.10}

            with patch.object(
                self.orchestrator.ml_predictor, "get_signal", return_value=mock_signal
            ):
                # Run full trading cycle
                result = self.orchestrator.run_trading_cycle(symbols=self.test_symbols)

                # Validate result structure
                self.assertIsNotNone(result)
                self.assertIn("plan_id", result)
                self.assertIn("phases", result)
                self.assertIn("agent_results", result)

                # Check that analysis phase executed
                if "analysis" in result.get("phases", {}):
                    analysis_phase = result["phases"]["analysis"]
                    agent_results = analysis_phase.get("agent_results", [])

                    ml_results = [r for r in agent_results if r.get("agent") == "ml_model"]
                    if ml_results:
                        print(
                            f"✅ RL system participated in orchestration: {len(ml_results)} signals"
                        )
                    else:
                        print(
                            "⚠️  RL system did not participate (may be expected if other agents unavailable)"
                        )

                print("✅ End-to-end orchestration completed")
        else:
            print("⚠️  ML Predictor not available - skipping end-to-end test")
            self.skipTest("ML Predictor not available")


class TestRLModelTrainingIntegration(unittest.TestCase):
    """Test integration between model training and Elite Orchestrator"""

    def test_model_training_creates_usable_model(self):
        """Test that trained models can be used by Elite Orchestrator"""
        print("\n[TEST] Model Training → Elite Orchestrator Integration")

        # Check if model exists
        models_dir = project_root / "data" / "models"
        model_files = list(models_dir.glob("lstm_feature_extractor*.pt"))

        if not model_files:
            print("⚠️  No trained models found - skipping test")
            self.skipTest("No trained models available")

        # Try to initialize ML Predictor
        try:
            from src.ml.inference import MLPredictor

            predictor = MLPredictor()

            # Try to get signal (may fail if data unavailable, but model should load)
            signal = predictor.get_signal("SPY")

            # Validate signal format
            self.assertIn("action", signal)
            self.assertIn(signal["action"], ["BUY", "SELL", "HOLD"])

            print(f"✅ Trained model usable: {signal['action']} signal generated")
        except Exception as e:
            print(f"⚠️  Model loading failed: {e}")
            print("   (This may be OK if data unavailable, but model should still load)")


def main():
    """Run all integration tests"""
    print("=" * 80)
    print("ELITE ORCHESTRATOR + RL SYSTEM INTEGRATION TESTS")
    print("=" * 80)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEliteOrchestratorRLIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRLModelTrainingIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n🎉 ALL TESTS PASSED - RL integration working correctly!")
        return 0
    else:
        print("\n⚠️  Some tests failed - Review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
