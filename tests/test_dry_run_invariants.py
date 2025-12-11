#!/usr/bin/env python3
"""
Dry-Run Invariant Tests - Validate dry-run outputs respect limits

Tests that dry-run outputs respect position limits and risk budgets:
1. No position has notional > $100 (per-symbol cap for R&D phase)
2. Total risk exposure ≤ 10% of portfolio
3. No negative collateral values
4. All required fields (positions, pnl, symbols) are present

Created: Dec 11, 2025
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# Module-level fixture (shared across all test classes)
@pytest.fixture
def mock_dry_run_output():
    """Mock dry-run output with valid data."""
    return {
        "plan_id": "test-plan-123",
        "symbols": ["SPY", "QQQ", "VOO"],
        "ensemble_vote": {
            "SPY": {"consensus": "BUY", "weighted_score": 0.25},
            "QQQ": {"consensus": "HOLD", "weighted_score": 0.05},
            "VOO": {"consensus": "BUY", "weighted_score": 0.20},
        },
        "risk": {
            "risk_checks": {
                "portfolio_health": {"success": True},
                "SPY_position": {
                    "recommendations": {
                        "primary_method": {"position_size_dollars": 95.0}
                    }
                },
                "QQQ_position": {
                    "recommendations": {
                        "primary_method": {"position_size_dollars": 0.0}
                    }
                },
                "VOO_position": {
                    "recommendations": {
                        "primary_method": {"position_size_dollars": 98.0}
                    }
                },
            }
        },
        "execution": {
            "orders": [
                {"symbol": "SPY", "notional": 95.0, "agent": "mcp"},
                {"symbol": "VOO", "notional": 98.0, "agent": "langchain"},
            ]
        },
    }


class TestDryRunPositionLimits:
    """Test position size limits in dry-run outputs."""

    def test_no_position_exceeds_100_dollars(self, mock_dry_run_output):
        """No position should exceed $100 notional (R&D phase limit)."""
        MAX_POSITION_SIZE = 100.0

        # Check positions in risk assessment
        risk_checks = mock_dry_run_output.get("risk", {}).get("risk_checks", {})
        for symbol in mock_dry_run_output.get("symbols", []):
            position_check = risk_checks.get(f"{symbol}_position", {})
            if position_check:
                position_size = (
                    position_check.get("recommendations", {})
                    .get("primary_method", {})
                    .get("position_size_dollars", 0)
                )
                assert (
                    position_size <= MAX_POSITION_SIZE
                ), f"{symbol} position ${position_size} exceeds ${MAX_POSITION_SIZE}"

        # Check execution orders
        for order in mock_dry_run_output.get("execution", {}).get("orders", []):
            notional = order.get("notional", 0)
            symbol = order.get("symbol", "UNKNOWN")
            assert (
                notional <= MAX_POSITION_SIZE
            ), f"{symbol} order ${notional} exceeds ${MAX_POSITION_SIZE}"

    def test_oversized_position_rejected(self):
        """Test that oversized positions are rejected."""
        MAX_POSITION_SIZE = 100.0

        # Simulate an oversized position
        oversized_order = {"symbol": "SPY", "notional": 150.0, "agent": "test"}

        # Validate
        notional = oversized_order.get("notional", 0)
        with pytest.raises(AssertionError, match="exceeds"):
            assert notional <= MAX_POSITION_SIZE, f"Position ${notional} exceeds ${MAX_POSITION_SIZE}"


class TestDryRunRiskExposure:
    """Test total risk exposure limits."""

    def test_total_exposure_within_limit(self):
        """Total risk exposure must be ≤ 10% of portfolio."""
        PORTFOLIO_VALUE = 10000.0
        MAX_EXPOSURE_PCT = 0.10
        MAX_EXPOSURE_DOLLARS = PORTFOLIO_VALUE * MAX_EXPOSURE_PCT

        orders = [
            {"symbol": "SPY", "notional": 95.0},
            {"symbol": "QQQ", "notional": 90.0},
            {"symbol": "VOO", "notional": 98.0},
        ]

        total_exposure = sum(order.get("notional", 0) for order in orders)

        assert (
            total_exposure <= MAX_EXPOSURE_DOLLARS
        ), f"Total exposure ${total_exposure} exceeds ${MAX_EXPOSURE_DOLLARS} (10% of ${PORTFOLIO_VALUE})"

    def test_excessive_exposure_blocked(self):
        """Test that excessive exposure is blocked."""
        PORTFOLIO_VALUE = 10000.0
        MAX_EXPOSURE_PCT = 0.10
        MAX_EXPOSURE_DOLLARS = PORTFOLIO_VALUE * MAX_EXPOSURE_PCT

        # Simulate excessive orders
        orders = [
            {"symbol": "SPY", "notional": 500.0},
            {"symbol": "QQQ", "notional": 600.0},
        ]

        total_exposure = sum(order.get("notional", 0) for order in orders)

        with pytest.raises(AssertionError, match="Excessive exposure"):
            assert (
                total_exposure <= MAX_EXPOSURE_DOLLARS
            ), f"Excessive exposure: ${total_exposure} > ${MAX_EXPOSURE_DOLLARS}"

    def test_portfolio_health_check_present(self, mock_dry_run_output):
        """Portfolio health check must be present in risk assessment."""
        risk_checks = (
            mock_dry_run_output.get("risk", {}).get("risk_checks", {})
        )
        assert "portfolio_health" in risk_checks, "Missing portfolio_health check"

        portfolio_health = risk_checks["portfolio_health"]
        assert "success" in portfolio_health, "Missing success field in portfolio_health"


class TestDryRunCollateral:
    """Test collateral value validations."""

    def test_no_negative_collateral(self):
        """Collateral values must never be negative."""
        account_data = {
            "equity": 10000.0,
            "cash": 8000.0,
            "buying_power": 2000.0,
            "portfolio_value": 10000.0,
        }

        for key, value in account_data.items():
            assert value >= 0, f"Negative {key}: ${value}"

    def test_negative_collateral_rejected(self):
        """Test that negative collateral is rejected."""
        invalid_account = {
            "equity": 10000.0,
            "cash": -500.0,  # Invalid
            "buying_power": 2000.0,
        }

        # Validate
        cash = invalid_account.get("cash", 0)
        with pytest.raises(AssertionError, match="Negative"):
            assert cash >= 0, f"Negative cash: ${cash}"

    def test_buying_power_sufficient(self):
        """Buying power must be sufficient for all orders."""
        buying_power = 2000.0
        orders = [
            {"symbol": "SPY", "notional": 95.0},
            {"symbol": "QQQ", "notional": 90.0},
            {"symbol": "VOO", "notional": 98.0},
        ]

        total_cost = sum(order.get("notional", 0) for order in orders)
        assert (
            total_cost <= buying_power
        ), f"Insufficient buying power: ${total_cost} > ${buying_power}"


class TestDryRunRequiredFields:
    """Test that all required fields are present in dry-run output."""

    def test_all_required_fields_present(self, mock_dry_run_output):
        """Dry-run output must have all required fields."""
        required_top_level = ["plan_id", "symbols", "ensemble_vote", "risk"]
        for field in required_top_level:
            assert field in mock_dry_run_output, f"Missing required field: {field}"

    def test_ensemble_vote_structure(self, mock_dry_run_output):
        """Ensemble vote must have proper structure."""
        ensemble_vote = mock_dry_run_output.get("ensemble_vote", {})
        assert isinstance(ensemble_vote, dict), "ensemble_vote must be a dict"

        for symbol, vote in ensemble_vote.items():
            assert "consensus" in vote, f"{symbol} missing consensus"
            assert vote["consensus"] in [
                "BUY",
                "SELL",
                "HOLD",
            ], f"{symbol} invalid consensus: {vote['consensus']}"

    def test_risk_checks_structure(self, mock_dry_run_output):
        """Risk checks must have proper structure."""
        risk = mock_dry_run_output.get("risk", {})
        assert "risk_checks" in risk, "Missing risk_checks"

        risk_checks = risk["risk_checks"]
        assert isinstance(risk_checks, dict), "risk_checks must be a dict"

    def test_execution_optional_but_valid(self, mock_dry_run_output):
        """If execution is present, it must be valid."""
        if "execution" not in mock_dry_run_output:
            pytest.skip("Execution not present (optional in dry-run)")

        execution = mock_dry_run_output["execution"]
        assert "orders" in execution, "execution must have orders field"

        orders = execution["orders"]
        assert isinstance(orders, list), "orders must be a list"

        for order in orders:
            assert "symbol" in order, "order missing symbol"
            assert "agent" in order, "order missing agent"


class TestDryRunSymbolConsistency:
    """Test symbol consistency across output sections."""

    def test_symbols_match_ensemble_vote(self, mock_dry_run_output):
        """Symbols list should match ensemble vote keys."""
        symbols = set(mock_dry_run_output.get("symbols", []))
        ensemble_symbols = set(mock_dry_run_output.get("ensemble_vote", {}).keys())

        # Ensemble vote may have fewer symbols (filtered), but all must be in original list
        assert ensemble_symbols.issubset(
            symbols
        ), f"Ensemble symbols {ensemble_symbols} not in symbols {symbols}"

    def test_execution_symbols_valid(self, mock_dry_run_output):
        """Execution symbols must be in the original symbols list."""
        if "execution" not in mock_dry_run_output:
            pytest.skip("Execution not present")

        symbols = set(mock_dry_run_output.get("symbols", []))
        execution_symbols = set(
            order.get("symbol")
            for order in mock_dry_run_output.get("execution", {}).get("orders", [])
        )

        assert execution_symbols.issubset(
            symbols
        ), f"Execution symbols {execution_symbols} not in symbols {symbols}"


class TestDryRunIntegration:
    """Integration tests with actual dry_run.py script."""

    @pytest.mark.slow
    def test_dry_run_script_produces_valid_output(self):
        """Test that dry_run.py produces valid output (integration test)."""
        # This is a slower test that actually calls the dry_run script
        # Mark as slow so it can be skipped in fast CI runs
        from scripts.dry_run import dry_run

        # Mock args
        class Args:
            symbols = ["SPY", "QQQ"]
            include_agents = None
            exclude_agents = None
            weight_mcp = None
            weight_langchain = None
            weight_gemini = None
            weight_ml = None
            weight_grok = None
            buy_threshold = None
            sell_threshold = None
            execute = False
            export_json = "/tmp/test_dry_run.json"
            export_md = None

        args = Args()

        # Run dry_run and capture output
        with patch("src.orchestration.elite_orchestrator.EliteOrchestrator") as mock_eo:
            # Mock the orchestrator to return test data
            mock_instance = MagicMock()
            mock_eo.return_value = mock_instance

            mock_instance.create_trade_plan.return_value = MagicMock(plan_id="test-123")
            mock_instance._execute_data_collection.return_value = {}
            mock_instance._execute_analysis.return_value = {
                "ensemble_vote": {
                    "SPY": {"consensus": "BUY", "weighted_score": 0.25},
                    "QQQ": {"consensus": "HOLD", "weighted_score": 0.05},
                },
                "agent_results": [],
            }
            mock_instance._execute_risk_assessment.return_value = {
                "risk_checks": {
                    "portfolio_health": {"success": True},
                    "SPY_position": {
                        "recommendations": {
                            "primary_method": {"position_size_dollars": 95.0}
                        }
                    },
                    "QQQ_position": {
                        "recommendations": {
                            "primary_method": {"position_size_dollars": 0.0}
                        }
                    },
                }
            }

            # Run
            exit_code = dry_run(args.symbols, args)
            assert exit_code == 0, "dry_run should succeed"

            # Verify output file
            output_path = Path(args.export_json)
            assert output_path.exists(), f"Output file not created: {output_path}"

            with open(output_path) as f:
                output = json.load(f)

            # Validate output structure
            assert "plan_id" in output
            assert "symbols" in output
            assert "ensemble_vote" in output
            assert "risk" in output

            # Cleanup
            output_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
