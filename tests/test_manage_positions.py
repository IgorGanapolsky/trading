"""
Tests for manage_positions.py script.

CEO Directive (Jan 7, 2026):
"Losing money is NOT allowed" - Phil Town Rule 1

This tests the position management script that enforces stop-losses.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestManagePositions:
    """Test the manage_positions script."""

    def test_position_manager_import(self):
        """Verify PositionManager can be imported."""
        from src.risk.position_manager import (
            ExitConditions,
            ExitReason,
            PositionInfo,
            PositionManager,
        )

        assert PositionManager is not None
        assert ExitConditions is not None
        assert PositionInfo is not None
        assert ExitReason is not None

    def test_exit_conditions_defaults(self):
        """Verify exit conditions have Phil Town-aligned defaults."""
        from src.risk.position_manager import ExitConditions

        conditions = ExitConditions()

        # Phil Town Rule 1: Don't lose money
        assert conditions.stop_loss_pct == 0.08  # 8% max loss
        assert conditions.take_profit_pct == 0.15  # 15% profit target
        assert conditions.max_holding_days == 30  # Don't hold forever

    def test_stop_loss_triggers(self):
        """Test that stop-loss correctly triggers on losing position."""
        from datetime import datetime

        from src.risk.position_manager import (
            ExitConditions,
            ExitReason,
            PositionInfo,
            PositionManager,
        )

        conditions = ExitConditions(stop_loss_pct=0.08)
        manager = PositionManager(conditions=conditions)

        # Position with -10% loss (exceeds 8% stop)
        position = PositionInfo(
            symbol="TEST",
            quantity=100,
            entry_price=100.0,
            current_price=89.0,  # -11% loss
            entry_date=datetime.now(),
            unrealized_pl=-1100.0,
            unrealized_plpc=-0.11,
            market_value=8900.0,
        )

        signal = manager.evaluate_position(position)

        assert signal.should_exit is True
        assert signal.reason == ExitReason.STOP_LOSS

    def test_take_profit_triggers(self):
        """Test that take-profit correctly triggers on winning position."""
        from datetime import datetime

        from src.risk.position_manager import (
            ExitConditions,
            ExitReason,
            PositionInfo,
            PositionManager,
        )

        conditions = ExitConditions(take_profit_pct=0.15)
        manager = PositionManager(conditions=conditions)

        # Position with +20% gain (exceeds 15% target)
        position = PositionInfo(
            symbol="TEST",
            quantity=100,
            entry_price=100.0,
            current_price=120.0,  # +20% gain
            entry_date=datetime.now(),
            unrealized_pl=2000.0,
            unrealized_plpc=0.20,
            market_value=12000.0,
        )

        signal = manager.evaluate_position(position)

        assert signal.should_exit is True
        assert signal.reason == ExitReason.TAKE_PROFIT

    def test_hold_when_no_exit_condition(self):
        """Test that position is held when no exit conditions met."""
        from datetime import datetime

        from src.risk.position_manager import (
            ExitConditions,
            PositionInfo,
            PositionManager,
        )

        conditions = ExitConditions(stop_loss_pct=0.08, take_profit_pct=0.15)
        manager = PositionManager(conditions=conditions)

        # Position with +5% gain (between thresholds)
        position = PositionInfo(
            symbol="TEST",
            quantity=100,
            entry_price=100.0,
            current_price=105.0,  # +5% gain
            entry_date=datetime.now(),
            unrealized_pl=500.0,
            unrealized_plpc=0.05,
            market_value=10500.0,
        )

        signal = manager.evaluate_position(position)

        assert signal.should_exit is False

    def test_manage_all_positions_returns_exits(self):
        """Test that manage_all_positions returns list of exits."""
        from src.risk.position_manager import (
            ExitConditions,
            PositionManager,
        )

        conditions = ExitConditions(stop_loss_pct=0.08, take_profit_pct=0.15)
        manager = PositionManager(conditions=conditions)

        positions = [
            {
                "symbol": "WINNER",
                "qty": 100,
                "avg_entry_price": 100.0,
                "current_price": 120.0,  # +20% - should exit
                "unrealized_pl": 2000.0,
                "unrealized_plpc": 0.20,
                "market_value": 12000.0,
            },
            {
                "symbol": "LOSER",
                "qty": 100,
                "avg_entry_price": 100.0,
                "current_price": 85.0,  # -15% - should exit
                "unrealized_pl": -1500.0,
                "unrealized_plpc": -0.15,
                "market_value": 8500.0,
            },
            {
                "symbol": "HOLDER",
                "qty": 100,
                "avg_entry_price": 100.0,
                "current_price": 103.0,  # +3% - should hold
                "unrealized_pl": 300.0,
                "unrealized_plpc": 0.03,
                "market_value": 10300.0,
            },
        ]

        exits = manager.manage_all_positions(positions)

        # Should return 2 exits (WINNER and LOSER), not HOLDER
        assert len(exits) == 2
        symbols = {e["symbol"] for e in exits}
        assert "WINNER" in symbols
        assert "LOSER" in symbols
        assert "HOLDER" not in symbols


class TestPhilTownCompliance:
    """Test Phil Town Rule 1 compliance."""

    def test_rule_1_stop_loss_configured(self):
        """Verify stop-loss is configured per Phil Town Rule 1."""
        from src.risk.position_manager import DEFAULT_POSITION_MANAGER

        # Phil Town Rule 1: Don't lose money
        # System must have stop-loss to protect capital
        assert DEFAULT_POSITION_MANAGER.conditions.stop_loss_pct > 0
        assert DEFAULT_POSITION_MANAGER.conditions.stop_loss_pct <= 0.10  # Max 10%

    def test_rule_1_atr_stop_enabled(self):
        """Verify ATR-based dynamic stop is enabled."""
        from src.risk.position_manager import DEFAULT_POSITION_MANAGER

        # ATR stop provides volatility-adjusted protection
        assert DEFAULT_POSITION_MANAGER.conditions.enable_atr_stop is True
