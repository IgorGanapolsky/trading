#!/usr/bin/env python3
"""
Comprehensive sanity tests for the promotion gate to ensure it's not degenerate.

Tests verify that:
1. Clearly bad metrics are rejected
2. Clearly good metrics are accepted
3. Borderline metrics are handled appropriately (defer/reject with explanation)
4. Gate is monotonic (improving metrics shouldn't flip accept→reject)
5. Gate doesn't accept everything or reject everything
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

# Import the gate evaluation logic
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.enforce_promotion_gate import (
    evaluate_gate,
    normalize_percent,
)


def create_system_state(
    win_rate: float,
    sharpe: float,
    drawdown: float,
    total_trades: int = 150,
) -> dict[str, Any]:
    """Create a synthetic system_state.json for testing."""
    return {
        "meta": {
            "last_updated": "2025-12-11T10:00:00Z",
        },
        "performance": {
            "win_rate": win_rate,
            "total_trades": total_trades,
        },
        "heuristics": {
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "max_drawdown": -abs(drawdown),  # Stored as negative
        },
    }


def create_backtest_summary(
    min_win_rate: float,
    min_sharpe: float,
    max_drawdown: float,
    min_profitable_streak: int,
    total_trades: int = 150,
) -> dict[str, Any]:
    """Create a synthetic backtest summary for testing."""
    return {
        "aggregate_metrics": {
            "min_win_rate": min_win_rate,
            "min_sharpe_ratio": min_sharpe,
            "max_drawdown": max_drawdown,
            "min_profitable_streak": min_profitable_streak,
            "total_trades": total_trades,
        },
    }


def create_default_args() -> argparse.Namespace:
    """Create default arguments matching production settings."""
    return argparse.Namespace(
        required_win_rate=55.0,
        required_sharpe=1.2,
        max_drawdown=10.0,
        min_profitable_days=30,
        min_trades=100,
        override_env="ALLOW_PROMOTION_OVERRIDE",
        stale_threshold_hours=48.0,
        json=False,
        json_output=None,
    )


class TestPromotionGateSanity(unittest.TestCase):
    """Comprehensive sanity tests for the promotion gate."""

    def test_clearly_bad_metrics_rejected(self):
        """
        Test that CLEARLY BAD metrics are rejected.
        Scenario: Massive drawdown (>20%), negative Sharpe (<0), low win rate (<40%)
        """
        system_state = create_system_state(
            win_rate=35.0,  # Way below 55% threshold
            sharpe=-0.5,    # Negative (losing money consistently)
            drawdown=25.0,  # Massive drawdown (>20%)
            total_trades=150,
        )
        backtest_summary = create_backtest_summary(
            min_win_rate=38.0,
            min_sharpe=-0.3,
            max_drawdown=22.0,
            min_profitable_streak=5,  # Way below 30 days
            total_trades=150,
        )
        args = create_default_args()

        deficits = evaluate_gate(system_state, backtest_summary, args)

        # Should have MULTIPLE deficits (not just one)
        self.assertGreaterEqual(
            len(deficits), 4,
            f"Clearly bad metrics should trigger multiple deficits, got {len(deficits)}: {deficits}"
        )

        # Verify specific deficits are present
        deficit_text = " ".join(deficits)
        self.assertTrue("Win rate" in deficit_text or "win-rate" in deficit_text)
        self.assertIn("Sharpe", deficit_text)
        self.assertTrue("drawdown" in deficit_text or "Drawdown" in deficit_text)
        self.assertTrue("profitable streak" in deficit_text or "streak" in deficit_text)

    def test_clearly_good_metrics_accepted(self):
        """
        Test that CLEARLY GOOD metrics are accepted.
        Scenario: Sharpe > 2, DD < 5%, win rate > 60%, 40+ profitable days
        """
        system_state = create_system_state(
            win_rate=65.0,  # Well above 55% threshold
            sharpe=2.5,     # Excellent Sharpe ratio
            drawdown=3.5,   # Very low drawdown
            total_trades=200,
        )
        backtest_summary = create_backtest_summary(
            min_win_rate=62.0,
            min_sharpe=2.2,
            max_drawdown=4.0,
            min_profitable_streak=45,  # Well above 30 days
            total_trades=200,
        )
        args = create_default_args()

        deficits = evaluate_gate(system_state, backtest_summary, args)

        # Should have NO deficits
        self.assertEqual(
            len(deficits), 0,
            f"Clearly good metrics should have zero deficits, got {len(deficits)}: {deficits}"
        )

    def test_borderline_metrics_handled_appropriately(self):
        """
        Test that BORDERLINE metrics are handled consistently.
        Scenario: Sharpe ~1.2, DD ~8%, win rate ~55% (at or near thresholds)

        Borderline cases should either:
        - Reject with clear explanation of what's missing
        - Accept if all thresholds are met
        """
        # Just barely passing all thresholds
        system_state_passing = create_system_state(
            win_rate=56.0,  # Just above 55%
            sharpe=1.25,    # Just above 1.2
            drawdown=9.5,   # Just below 10%
            total_trades=105,
        )
        backtest_summary_passing = create_backtest_summary(
            min_win_rate=55.5,
            min_sharpe=1.22,
            max_drawdown=9.8,
            min_profitable_streak=31,  # Just above 30
            total_trades=105,
        )

        # Just barely failing multiple thresholds
        system_state_failing = create_system_state(
            win_rate=54.0,  # Just below 55%
            sharpe=1.15,    # Just below 1.2
            drawdown=10.5,  # Just above 10%
            total_trades=95,
        )
        backtest_summary_failing = create_backtest_summary(
            min_win_rate=54.5,
            min_sharpe=1.18,
            max_drawdown=10.2,
            min_profitable_streak=28,  # Just below 30
            total_trades=95,
        )

        args = create_default_args()

        deficits_passing = evaluate_gate(system_state_passing, backtest_summary_passing, args)
        deficits_failing = evaluate_gate(system_state_failing, backtest_summary_failing, args)

        # Passing borderline should have zero or very few deficits
        self.assertEqual(
            len(deficits_passing), 0,
            f"Borderline passing metrics should have zero deficits, got {len(deficits_passing)}: {deficits_passing}"
        )

        # Failing borderline should have several deficits with clear explanations
        self.assertGreaterEqual(
            len(deficits_failing), 3,
            f"Borderline failing metrics should have multiple deficits, got {len(deficits_failing)}: {deficits_failing}"
        )

    def test_gate_monotonicity_improving_metrics(self):
        """
        Test gate monotonicity: improving metrics should not flip accept→reject.

        If a configuration passes, then improving ANY metric should still pass.
        If a configuration fails, then improving ALL metrics should eventually pass.
        """
        # Start with baseline that just barely passes
        baseline_state = create_system_state(
            win_rate=56.0,
            sharpe=1.25,
            drawdown=9.5,
            total_trades=105,
        )
        baseline_backtest = create_backtest_summary(
            min_win_rate=55.5,
            min_sharpe=1.22,
            max_drawdown=9.8,
            min_profitable_streak=31,
            total_trades=105,
        )
        args = create_default_args()

        baseline_deficits = evaluate_gate(baseline_state, baseline_backtest, args)
        self.assertEqual(len(baseline_deficits), 0, "Baseline should pass")

        # Test 1: Improve win rate only
        improved_state_wr = create_system_state(
            win_rate=60.0,  # IMPROVED
            sharpe=1.25,
            drawdown=9.5,
            total_trades=105,
        )
        improved_deficits_wr = evaluate_gate(improved_state_wr, baseline_backtest, args)
        self.assertEqual(
            len(improved_deficits_wr), 0,
            "Improving win rate should not cause rejection"
        )

        # Test 2: Improve Sharpe only
        improved_state_sharpe = create_system_state(
            win_rate=56.0,
            sharpe=1.8,  # IMPROVED
            drawdown=9.5,
            total_trades=105,
        )
        improved_deficits_sharpe = evaluate_gate(improved_state_sharpe, baseline_backtest, args)
        self.assertEqual(
            len(improved_deficits_sharpe), 0,
            "Improving Sharpe should not cause rejection"
        )

        # Test 3: Reduce drawdown (improve)
        improved_state_dd = create_system_state(
            win_rate=56.0,
            sharpe=1.25,
            drawdown=5.0,  # IMPROVED (lower drawdown is better)
            total_trades=105,
        )
        improved_deficits_dd = evaluate_gate(improved_state_dd, baseline_backtest, args)
        self.assertEqual(
            len(improved_deficits_dd), 0,
            "Reducing drawdown should not cause rejection"
        )

        # Test 4: Improve ALL metrics together
        improved_state_all = create_system_state(
            win_rate=65.0,  # IMPROVED
            sharpe=2.0,     # IMPROVED
            drawdown=4.0,   # IMPROVED
            total_trades=200,  # IMPROVED
        )
        improved_backtest_all = create_backtest_summary(
            min_win_rate=62.0,  # IMPROVED
            min_sharpe=1.8,     # IMPROVED
            max_drawdown=5.0,   # IMPROVED
            min_profitable_streak=45,  # IMPROVED
            total_trades=200,
        )
        improved_deficits_all = evaluate_gate(improved_state_all, improved_backtest_all, args)
        self.assertEqual(
            len(improved_deficits_all), 0,
            "Improving all metrics should definitely not cause rejection"
        )

    def test_gate_not_degenerate_all_accept(self):
        """
        Test that gate doesn't accept EVERYTHING.
        At least one scenario should be rejected.
        """
        # Test multiple bad scenarios
        bad_scenarios = [
            # Scenario 1: Everything terrible
            (
                create_system_state(20.0, -1.5, 40.0, 150),
                create_backtest_summary(25.0, -1.0, 35.0, 3, 150),
            ),
            # Scenario 2: Good win rate but terrible Sharpe/drawdown
            (
                create_system_state(70.0, -0.5, 30.0, 150),
                create_backtest_summary(65.0, -0.3, 28.0, 5, 150),
            ),
            # Scenario 3: Good Sharpe but terrible win rate/drawdown
            (
                create_system_state(30.0, 2.0, 25.0, 150),
                create_backtest_summary(28.0, 1.8, 22.0, 8, 150),
            ),
        ]

        args = create_default_args()
        rejections = 0

        for system_state, backtest_summary in bad_scenarios:
            deficits = evaluate_gate(system_state, backtest_summary, args)
            if len(deficits) > 0:
                rejections += 1

        self.assertEqual(
            rejections, len(bad_scenarios),
            f"Gate should reject ALL clearly bad scenarios, but only rejected {rejections}/{len(bad_scenarios)}"
        )

    def test_gate_not_degenerate_all_reject(self):
        """
        Test that gate doesn't reject EVERYTHING.
        At least one scenario should be accepted.
        """
        # Test multiple good scenarios
        good_scenarios = [
            # Scenario 1: Everything excellent
            (
                create_system_state(70.0, 2.5, 3.0, 200),
                create_backtest_summary(68.0, 2.3, 4.0, 45, 200),
            ),
            # Scenario 2: Solid all-around performance
            (
                create_system_state(60.0, 1.8, 7.0, 150),
                create_backtest_summary(58.0, 1.6, 8.0, 35, 150),
            ),
            # Scenario 3: Just above thresholds but consistent
            (
                create_system_state(57.0, 1.3, 9.0, 110),
                create_backtest_summary(56.0, 1.25, 9.5, 32, 110),
            ),
        ]

        args = create_default_args()
        acceptances = 0

        for system_state, backtest_summary in good_scenarios:
            deficits = evaluate_gate(system_state, backtest_summary, args)
            if len(deficits) == 0:
                acceptances += 1

        self.assertEqual(
            acceptances, len(good_scenarios),
            f"Gate should accept ALL clearly good scenarios, but only accepted {acceptances}/{len(good_scenarios)}"
        )

    def test_edge_case_exactly_at_thresholds(self):
        """
        Test behavior when metrics are exactly at thresholds.
        Should accept (≥ comparison for good metrics, ≤ for bad ones).
        """
        system_state = create_system_state(
            win_rate=55.0,  # Exactly at threshold
            sharpe=1.2,     # Exactly at threshold
            drawdown=10.0,  # Exactly at threshold
            total_trades=100,  # Exactly at threshold
        )
        backtest_summary = create_backtest_summary(
            min_win_rate=55.0,
            min_sharpe=1.2,
            max_drawdown=10.0,
            min_profitable_streak=30,  # Exactly at threshold
            total_trades=100,
        )
        args = create_default_args()

        deficits = evaluate_gate(system_state, backtest_summary, args)

        # At exact thresholds should pass (inclusive boundaries)
        self.assertEqual(
            len(deficits), 0,
            f"Metrics exactly at thresholds should pass, got deficits: {deficits}"
        )

    def test_insufficient_trades_rejected(self):
        """
        Test that configurations with too few trades are rejected regardless of other metrics.
        """
        system_state = create_system_state(
            win_rate=70.0,  # Great metrics
            sharpe=2.5,
            drawdown=3.0,
            total_trades=50,  # But too few trades
        )
        backtest_summary = create_backtest_summary(
            min_win_rate=68.0,
            min_sharpe=2.3,
            max_drawdown=4.0,
            min_profitable_streak=45,
            total_trades=50,  # Too few
        )
        args = create_default_args()

        deficits = evaluate_gate(system_state, backtest_summary, args)

        # Should be rejected due to insufficient trades
        self.assertGreater(len(deficits), 0, "Should reject due to insufficient trades")
        deficit_text = " ".join(deficits).lower()
        self.assertTrue(
            "trades" in deficit_text or "statistical significance" in deficit_text,
            f"Should mention insufficient trades, got: {deficits}"
        )

    def test_normalize_percent_utility(self):
        """Test the normalize_percent utility function."""
        # Test decimal format (0.0-1.0)
        self.assertAlmostEqual(normalize_percent(0.55), 55.0, places=5)
        self.assertAlmostEqual(normalize_percent(0.95), 95.0, places=5)

        # Test percentage format (already in 0-100)
        self.assertAlmostEqual(normalize_percent(55.0), 55.0, places=5)
        self.assertAlmostEqual(normalize_percent(95.0), 95.0, places=5)

        # Test edge cases
        self.assertAlmostEqual(normalize_percent(0.0), 0.0, places=5)
        self.assertAlmostEqual(normalize_percent(1.0), 100.0, places=5)
        self.assertAlmostEqual(normalize_percent(100.0), 100.0, places=5)

        # Test invalid inputs
        self.assertAlmostEqual(normalize_percent(None), 0.0, places=5)
        self.assertAlmostEqual(normalize_percent("invalid"), 0.0, places=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
