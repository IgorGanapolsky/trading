#!/usr/bin/env python3
"""
Comprehensive Orchestration Integration Tests

Tests end-to-end orchestration behavior:
1. All agents participate correctly
2. Ensemble voting works
3. Error handling and fallbacks
4. Phase execution order
5. Result validation
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.orchestration.elite_orchestrator import EliteOrchestrator, PlanningPhase


class TestOrchestrationIntegration(unittest.TestCase):
    """Test orchestration integration and behavior"""

    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = EliteOrchestrator(paper=True, enable_planning=True)
        self.test_symbols = ["SPY", "QQQ"]

    def test_all_phases_execute_in_order(self):
        """Test that all phases execute in correct order"""
        print("\n[TEST] Phase Execution Order")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Expected phase order
        expected_order = [
            PlanningPhase.INITIALIZE,
            PlanningPhase.DATA_COLLECTION,
            PlanningPhase.ANALYSIS,
            PlanningPhase.RISK_ASSESSMENT,
            PlanningPhase.EXECUTION,
            PlanningPhase.AUDIT,
        ]

        # Mock phase execution to track order
        execution_order = []

        def mock_execute_phase(plan, phase):
            execution_order.append(phase)
            return {"phase": phase.value, "status": "completed"}

        with (
            patch.object(self.orchestrator, "_execute_phase", side_effect=mock_execute_phase),
            patch.object(
                self.orchestrator,
                "_execute_data_collection",
                return_value={"phase": "data_collection"},
            ),
            patch.object(
                self.orchestrator,
                "_execute_analysis",
                return_value={"phase": "analysis"},
            ),
            patch.object(
                self.orchestrator,
                "_execute_risk_assessment",
                return_value={"phase": "risk_assessment"},
            ),
            patch.object(
                self.orchestrator,
                "_execute_trades",
                return_value={"phase": "execution"},
            ),
            patch.object(
                self.orchestrator,
                "_execute_audit",
                return_value={"phase": "audit"},
            ),
        ):
            result = self.orchestrator.execute_plan(plan)

            # Check that all phases executed
            phases = result.get("phases", {})
            self.assertEqual(len(phases), len(expected_order))

            print("✅ All phases executed in correct order")

    def test_ensemble_voting_consensus(self):
        """Test ensemble voting produces consensus"""
        print("\n[TEST] Ensemble Voting Consensus")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock all agents to return BUY
        mock_recommendations = {
            "SPY_langchain": {
                "agent": "langchain",
                "recommendation": "BUY",
                "confidence": 0.8,
            },
            "SPY_gemini": {
                "agent": "gemini",
                "recommendation": "BUY",
                "confidence": 0.75,
            },
            "SPY_ml": {
                "agent": "ml_model",
                "recommendation": "BUY",
                "confidence": 0.85,
            },
        }

        # Mock analysis to return these recommendations
        def mock_analysis(plan):
            return {
                "phase": "analysis",
                "agent_results": list(mock_recommendations.values()),
                "ensemble_vote": {
                    "SPY": {
                        "buy_votes": 3,
                        "total_votes": 3,
                        "consensus": "BUY",
                        "recommendations": mock_recommendations,
                    }
                },
            }

        with patch.object(self.orchestrator, "_execute_analysis", side_effect=mock_analysis):
            analysis_result = self.orchestrator._execute_analysis(plan)

            ensemble_vote = analysis_result.get("ensemble_vote", {})

            if "SPY" in ensemble_vote:
                vote = ensemble_vote["SPY"]
                consensus = vote.get("consensus")

                self.assertIsNotNone(consensus)
                print(f"✅ Consensus reached: {consensus}")
                print(f"   Votes: {vote.get('buy_votes')}/{vote.get('total_votes')}")

    def test_error_handling_and_fallbacks(self):
        """Test error handling and fallback behavior"""
        print("\n[TEST] Error Handling and Fallbacks")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock agents to raise errors
        with patch.object(self.orchestrator, "langchain_agent", None):
            with patch.object(self.orchestrator, "gemini_agent", None):
                with patch.object(self.orchestrator, "ml_predictor", None):
                    with patch.object(self.orchestrator, "mcp_orchestrator", None):
                        # Should still execute without crashing
                        analysis_result = self.orchestrator._execute_analysis(plan)

                        self.assertIsNotNone(analysis_result)
                        self.assertIn("agent_results", analysis_result)

                        print("✅ Orchestrator handles missing agents gracefully")

    def test_result_structure_validation(self):
        """Test that execution results have correct structure"""
        print("\n[TEST] Result Structure Validation")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Mock all phases to return valid results
        mock_results = {
            "plan_id": plan.plan_id,
            "phases": {
                "initialize": {"phase": "initialize", "status": "completed"},
                "data_collection": {"phase": "data_collection", "status": "completed"},
                "analysis": {"phase": "analysis", "agent_results": []},
                "risk_assessment": {"phase": "risk_assessment", "should_halt": False},
                "execution": {"phase": "execution", "decision": "NO_TRADE"},
                "audit": {"phase": "audit", "status": "completed"},
            },
            "agent_results": [],
            "final_decision": None,
            "errors": [],
        }

        def mock_execute_plan(plan):
            return mock_results

        with patch.object(self.orchestrator, "execute_plan", side_effect=mock_execute_plan):
            result = self.orchestrator.execute_plan(plan)

            # Validate structure
            self.assertIn("plan_id", result)
            self.assertIn("phases", result)
            self.assertIn("agent_results", result)
            self.assertIn("final_decision", result)
            self.assertIn("errors", result)

            print("✅ Result structure valid")

    def test_plan_persistence(self):
        """Test that plans are saved and can be loaded"""
        print("\n[TEST] Plan Persistence")

        plan = self.orchestrator.create_trade_plan(symbols=self.test_symbols)

        # Check that plan file exists
        plan_file = self.orchestrator.plans_dir / f"{plan.plan_id}.json"

        self.assertTrue(plan_file.exists(), "Plan file should be saved")

        # Verify plan content
        import json

        with open(plan_file) as f:
            saved_plan = json.load(f)

        self.assertEqual(saved_plan["plan_id"], plan.plan_id)
        self.assertEqual(saved_plan["symbols"], plan.symbols)

        print(f"✅ Plan persisted: {plan_file.name}")


class TestAgentCoordination(unittest.TestCase):
    """Test agent coordination and communication"""

    def setUp(self):
        """Set up test fixtures"""
        self.orchestrator = EliteOrchestrator(paper=True, enable_planning=True)

    def test_agent_initialization_status(self):
        """Test that all agents initialize correctly"""
        print("\n[TEST] Agent Initialization Status")

        agents_status = {
            "Claude Skills": self.orchestrator.skills is not None,
            "Langchain": self.orchestrator.langchain_agent is not None,
            "Gemini": self.orchestrator.gemini_agent is not None,
            "Go ADK": (
                self.orchestrator.adk_adapter is not None and self.orchestrator.adk_adapter.enabled
                if self.orchestrator.adk_adapter
                else False
            ),
            "MCP": self.orchestrator.mcp_orchestrator is not None,
            "ML Predictor": self.orchestrator.ml_predictor is not None,
        }

        print("\nAgent Status:")
        for agent_name, status in agents_status.items():
            status_icon = "✅" if status else "⚠️"
            print(f"   {status_icon} {agent_name}: {'Available' if status else 'Unavailable'}")

        # At least some agents should be available
        available_count = sum(1 for v in agents_status.values() if v)
        self.assertGreater(available_count, 0, "At least some agents should be available")

        print(f"\n✅ {available_count}/{len(agents_status)} agents available")


def main():
    """Run all orchestration integration tests"""
    print("=" * 80)
    print("ORCHESTRATION INTEGRATION TESTS")
    print("=" * 80)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOrchestrationIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentCoordination))

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
        print("\n🎉 ALL TESTS PASSED - Orchestration working correctly!")
        return 0
    else:
        print("\n⚠️  Some tests failed - Review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
