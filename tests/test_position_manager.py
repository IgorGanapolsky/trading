"""Tests for Position Manager stop-loss functionality."""

import pytest
from src.risk.position_manager import ExitConditions, Position, PositionManager


class TestPositionManager:
    """Test position manager exit logic."""

    def test_stop_loss_triggers_on_loss(self):
        """Stop-loss should trigger when loss exceeds threshold."""
        pm = PositionManager()
        test_positions = [
            {
                "symbol": "TEST",
                "qty": -1,
                "avg_entry_price": 0.75,
                "current_price": 1.04,
                "unrealized_pl": -29.0,
                "unrealized_plpc": -0.387,  # 38.7% loss
            }
        ]
        exits = pm.manage_all_positions(test_positions)
        assert len(exits) == 1
        assert exits[0]["reason"] == "STOP_LOSS"

    def test_no_exit_when_within_threshold(self):
        """No exit should trigger when loss is within threshold."""
        pm = PositionManager()
        test_positions = [
            {
                "symbol": "TEST",
                "qty": 100,
                "avg_entry_price": 10.0,
                "current_price": 9.50,
                "unrealized_pl": -50.0,
                "unrealized_plpc": -0.05,  # 5% loss (under 8% threshold)
            }
        ]
        exits = pm.manage_all_positions(test_positions)
        assert len(exits) == 0

    def test_take_profit_triggers_on_gain(self):
        """Take-profit should trigger when gain exceeds threshold."""
        pm = PositionManager()
        test_positions = [
            {
                "symbol": "WINNER",
                "qty": 100,
                "avg_entry_price": 10.0,
                "current_price": 12.0,
                "unrealized_pl": 200.0,
                "unrealized_plpc": 0.20,  # 20% gain (over 15% target)
            }
        ]
        exits = pm.manage_all_positions(test_positions)
        assert len(exits) == 1
        assert exits[0]["reason"] == "TAKE_PROFIT"

    def test_custom_thresholds(self):
        """Custom exit conditions should be respected."""
        conditions = ExitConditions(
            stop_loss_pct=0.05,  # 5% stop-loss
            take_profit_pct=0.10,  # 10% take-profit
        )
        pm = PositionManager(conditions=conditions)

        # 6% loss should trigger with 5% threshold
        test_positions = [
            {
                "symbol": "TIGHT_STOP",
                "qty": 100,
                "avg_entry_price": 10.0,
                "current_price": 9.40,
                "unrealized_pl": -60.0,
                "unrealized_plpc": -0.06,  # 6% loss
            }
        ]
        exits = pm.manage_all_positions(test_positions)
        assert len(exits) == 1
        assert exits[0]["reason"] == "STOP_LOSS"

    def test_position_dataclass(self):
        """Position dataclass should hold correct values."""
        pos = Position(
            symbol="TEST",
            quantity=-1,
            entry_price=0.75,
            current_price=1.04,
            unrealized_pl=-29.0,
            unrealized_plpc=-0.387,
        )
        assert pos.symbol == "TEST"
        assert pos.quantity == -1
        assert pos.entry_price == 0.75
        assert pos.current_price == 1.04

    def test_exit_conditions_defaults(self):
        """Exit conditions should have sensible defaults."""
        conditions = ExitConditions()
        assert conditions.stop_loss_pct == 0.08
        assert conditions.take_profit_pct == 0.15
        assert conditions.max_holding_days == 30
