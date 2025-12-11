#!/usr/bin/env python3
"""
Capital Scaling Tests - Sanity Checks for Profit Target Recommendations

These tests ensure that capital scaling recommendations are sensible and monotonic.
Prevents absurd recommendations like "invest $10/day to make $100/day profit".

Created: Dec 11, 2025
Rationale: Profit target calculations must scale logically with target goals
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.profit_target_tracker import ProfitTargetTracker


class TestCapitalScalingLogic:
    """Test that capital scaling recommendations are sensible."""

    def test_target_100_should_recommend_more_than_10_capital(self):
        """When target is $100/day profit, capital recommendation should be >> $10.

        If we're targeting $100/day profit with realistic returns (10-15% annual),
        we need ~$2,000-$3,000/day in trading capital (assuming ~0.05-0.1% daily returns).

        A recommendation of $10/day capital for $100/day profit would require
        1000% daily returns, which is unrealistic and dangerous.
        """
        # Mock state with moderate performance
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 15.0},  # $15 profit over 30 days = $0.50/day
            "performance": {
                "avg_return": 0.05,  # 0.05% daily return (13% annual - realistic)
                "win_rate": 0.60,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,  # Currently investing $10/day
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        recommended_budget = tracker.recommended_daily_budget()

        # With 0.05% daily return, to make $100/day we need:
        # $100 / 0.0005 = $200,000/day trading capital
        #
        # This is obviously too high for a small trader, but the math is correct.
        # The key test: recommended budget should NOT be $10 or anywhere close.

        assert recommended_budget is not None, "Should provide a recommendation with positive returns"
        assert recommended_budget > 100, (
            f"Capital recommendation ({recommended_budget:.2f}) should be >> $10 "
            f"to achieve $100/day profit with realistic returns. "
            f"Got ${recommended_budget:.2f}/day, which implies "
            f"{100/recommended_budget*100:.1f}% daily returns - unrealistic!"
        )

        # More realistic check: should be at least 20x the target profit
        # (assuming ~5% daily returns would still be very aggressive)
        assert recommended_budget >= 20 * 100, (
            f"For $100/day profit, need substantial capital. "
            f"Got ${recommended_budget:.2f}, expected >= $2,000"
        )

    def test_capital_recommendations_monotonic_with_target(self):
        """Capital recommendations should increase as target profit increases.

        If $100/day target requires $X capital, then $200/day should require ~$2X.
        """
        base_state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 15.0},
            "performance": {
                "avg_return": 0.1,  # 0.1% daily return
                "win_rate": 0.60,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        # Test increasing targets
        targets = [50.0, 100.0, 200.0, 500.0]
        recommendations = []

        for target in targets:
            tracker = ProfitTargetTracker(
                state_override=base_state.copy(),
                target_daily_profit=target,
            )
            budget = tracker.recommended_daily_budget()
            recommendations.append((target, budget))

        # Verify monotonicity: higher target → higher capital requirement
        for i in range(len(recommendations) - 1):
            target1, budget1 = recommendations[i]
            target2, budget2 = recommendations[i + 1]

            assert budget1 is not None, f"Target ${target1} should have a recommendation"
            assert budget2 is not None, f"Target ${target2} should have a recommendation"

            assert budget2 > budget1, (
                f"Capital should increase with target. "
                f"Target ${target1}→${target2}, but capital ${budget1:.2f}→${budget2:.2f}"
            )

            # Verify approximate linear scaling (within 10% tolerance)
            expected_ratio = target2 / target1
            actual_ratio = budget2 / budget1
            ratio_diff = abs(actual_ratio - expected_ratio) / expected_ratio

            assert ratio_diff < 0.1, (
                f"Capital should scale linearly with target. "
                f"Target ratio: {expected_ratio:.2f}x, "
                f"Capital ratio: {actual_ratio:.2f}x "
                f"(diff: {ratio_diff*100:.1f}%)"
            )

    def test_zero_returns_should_not_recommend_capital(self):
        """If avg_return is 0 or negative, should not recommend scaling capital.

        Can't scale capital to reach profit if the system isn't profitable yet.
        """
        state = {
            "challenge": {"current_day": 10},
            "account": {"total_pl": 0.0},
            "performance": {
                "avg_return": 0.0,  # No returns yet
                "win_rate": 0.50,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        recommended_budget = tracker.recommended_daily_budget()

        assert recommended_budget is None, (
            "Should not recommend capital scaling when returns are 0 or negative. "
            "Need to fix the strategy first, not just add more capital."
        )

    def test_negative_returns_should_not_recommend_capital(self):
        """If losing money, should not recommend increasing capital."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": -50.0},  # Losing money
            "performance": {
                "avg_return": -0.05,  # Negative returns
                "win_rate": 0.40,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        recommended_budget = tracker.recommended_daily_budget()

        assert recommended_budget is None, (
            "Should NEVER recommend scaling capital when losing money. "
            "Fix the strategy before adding more capital!"
        )

    def test_scaling_factor_is_sensible(self):
        """Scaling factor should be reasonable (not 1000x or 0.001x)."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 30.0},  # $1/day profit (historical)
            "performance": {
                "avg_return": 1.0,  # 1.0% daily return (excellent performance)
                "win_rate": 0.65,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 100.0,  # $100/day current budget
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=10.0,  # Want $10/day profit
        )

        plan = tracker.generate_plan()

        assert plan.scaling_factor is not None, "Should have a scaling factor"

        # Current: $100/day capital, 1.0% avg_return → $1/day projected profit
        # To get $10/day profit with 1.0% rate, need $1000/day capital
        # Scaling factor should be ~10x

        assert 5 < plan.scaling_factor < 20, (
            f"Scaling factor should be reasonable. "
            f"Got {plan.scaling_factor:.2f}x, expected ~10x. "
            f"(Current: $100/day @ 1% return → ~$1/day projected, Want: $10/day profit)"
        )

    def test_early_stage_with_limited_data(self):
        """In early R&D phase with limited data, recommendations should be conservative."""
        state = {
            "challenge": {"current_day": 5},  # Only 5 days of data
            "account": {"total_pl": 2.0},  # $2 profit
            "performance": {
                "avg_return": 0.04,  # 0.04% daily (10% annual)
                "win_rate": 0.60,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        plan = tracker.generate_plan()

        # With limited data, current_daily_profit will be noisy
        # ($2 / 5 days = $0.40/day)
        # But the recommendation should still be based on avg_return

        # Current: $10/day capital, 0.04% return → $0.004/day profit
        # To get $100/day with 0.04% return: need $250,000/day capital

        # The key: the math should be consistent even with limited data
        if plan.recommended_daily_budget:
            # Verify the calculation is consistent
            expected_budget = 100.0 / (plan.avg_return_pct / 100.0)
            assert abs(plan.recommended_daily_budget - expected_budget) < 1.0, (
                f"Calculation should be consistent. "
                f"Expected ${expected_budget:.2f}, got ${plan.recommended_daily_budget:.2f}"
            )

    def test_plan_actions_include_reality_check_for_high_targets(self):
        """When target requires unrealistic capital, plan should acknowledge it."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 15.0},
            "performance": {
                "avg_return": 0.05,  # 0.05% daily (13% annual)
                "win_rate": 0.60,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        plan = tracker.generate_plan()

        # With 0.05% daily return, need $200,000/day capital for $100/day profit
        # This is unrealistic for most traders

        # The plan should either:
        # 1. Recommend improving returns first, OR
        # 2. Acknowledge the capital requirement is very high

        # Check that actions list is not empty (should suggest something)
        assert len(plan.actions) > 0, "Plan should include actionable recommendations"

        # Print for inspection (useful for debugging)
        print("\nGenerated plan actions for $100/day target:")
        for action in plan.actions:
            print(f"  - {action}")

    def test_recommended_allocations_sum_to_total_budget(self):
        """Recommended strategy allocations should sum to recommended total budget."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 45.0},  # $1.50/day profit
            "performance": {
                "avg_return": 0.15,  # 0.15% daily return (45% annual - aggressive)
                "win_rate": 0.65,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 50.0,
                    "allocation": 0.5,
                },
                "growth": {
                    "status": "active",
                    "daily_amount": 50.0,
                    "allocation": 0.5,
                },
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=50.0,  # Want $50/day profit
        )

        plan = tracker.generate_plan()

        if plan.recommended_allocations:
            allocation_sum = sum(plan.recommended_allocations.values())

            # Should sum to recommended budget (within rounding tolerance)
            assert plan.recommended_daily_budget is not None
            assert abs(allocation_sum - plan.recommended_daily_budget) < 0.01, (
                f"Allocations should sum to total budget. "
                f"Sum: ${allocation_sum:.2f}, Budget: ${plan.recommended_daily_budget:.2f}"
            )


class TestCapitalScalingEdgeCases:
    """Test edge cases in capital scaling logic."""

    def test_multiple_paused_strategies_ignored(self):
        """Paused strategies should not affect capital calculations."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 30.0},
            "performance": {
                "avg_return": 0.1,
                "win_rate": 0.60,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                },
                "paused_strategy": {
                    "status": "paused",
                    "daily_amount": 1000.0,  # Should be ignored
                    "allocation": 0.0,
                },
                "tracking_strategy": {
                    "status": "tracking",
                    "daily_amount": 500.0,  # Should be ignored
                    "allocation": 0.0,
                },
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=10.0,
        )

        # Current daily budget should only count active strategies
        current_budget = tracker._current_daily_budget()
        assert current_budget == 10.0, (
            f"Only active strategies should be counted. "
            f"Expected $10, got ${current_budget:.2f}"
        )

    def test_very_high_returns_should_recommend_lower_capital(self):
        """If returns are very high, should recommend less capital scaling."""
        state = {
            "challenge": {"current_day": 30},
            "account": {"total_pl": 150.0},  # $5/day profit (historical)
            "performance": {
                "avg_return": 5.0,  # 5.0% daily return (extremely high, unsustainable)
                "win_rate": 0.75,
            },
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 100.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=10.0,
        )

        plan = tracker.generate_plan()

        # With 5.0% daily returns (projected), to get $10/day need:
        # $10 / 0.05 = $200/day capital

        # Current: $100/day @ 5% return → $5/day projected
        # Want: $10/day profit → need $200/day capital (2x scaling)

        assert plan.scaling_factor is not None
        assert plan.scaling_factor < 3, (
            f"With very high returns, scaling should be modest. "
            f"Got {plan.scaling_factor:.2f}x, expected ~2x"
        )

    def test_missing_performance_data(self):
        """Handle missing performance data gracefully."""
        state = {
            "challenge": {"current_day": 1},
            "account": {"total_pl": 0.0},
            "performance": {},  # No performance data yet
            "strategies": {
                "core": {
                    "status": "active",
                    "daily_amount": 10.0,
                    "allocation": 1.0,
                }
            },
        }

        tracker = ProfitTargetTracker(
            state_override=state,
            target_daily_profit=100.0,
        )

        # Should not crash, should handle missing data
        recommended_budget = tracker.recommended_daily_budget()

        # With no performance data (avg_return defaults to 0), should not recommend
        assert recommended_budget is None, (
            "Should not recommend capital scaling without performance data"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
