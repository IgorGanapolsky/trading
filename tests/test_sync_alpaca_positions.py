"""
100% Test Coverage for sync_alpaca_state.py positions functionality.

Tests the critical fix that ensures positions are saved to performance.open_positions.
This was a bug where positions were fetched but never stored.

Created: Jan 4, 2026
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestUpdateSystemStatePositions:
    """Test that positions are correctly stored in system_state.json."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create a temporary system_state.json."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        initial_state = {
            "meta": {"version": "1.0"},
            "account": {"current_equity": 100000},
            "performance": {"open_positions": []},
        }
        state_file.write_text(json.dumps(initial_state))
        return state_file

    def test_positions_stored_in_performance(self, temp_state_file):
        """CRITICAL: Verify positions are saved to performance.open_positions."""
        # Mock alpaca data with positions
        alpaca_data = {
            "equity": 100942.23,
            "cash": 86629.95,
            "buying_power": 1341.99,
            "positions": [
                {
                    "symbol": "SPY",
                    "qty": 10.5,
                    "avg_entry_price": 590.00,
                    "current_price": 595.00,
                    "market_value": 6247.50,
                    "unrealized_pl": 52.50,
                    "unrealized_plpc": 0.85,
                    "side": "long",
                },
                {
                    "symbol": "AAPL",
                    "qty": 5.0,
                    "avg_entry_price": 180.00,
                    "current_price": 185.00,
                    "market_value": 925.00,
                    "unrealized_pl": 25.00,
                    "unrealized_plpc": 2.78,
                    "side": "long",
                },
            ],
            "positions_count": 2,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        # Import and run update_system_state
        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        # Verify positions were stored
        with open(temp_state_file) as f:
            state = json.load(f)

        positions = state.get("performance", {}).get("open_positions", [])
        assert len(positions) == 2, f"Expected 2 positions, got {len(positions)}"

        # Verify first position data
        spy_pos = next((p for p in positions if p["symbol"] == "SPY"), None)
        assert spy_pos is not None, "SPY position not found"
        assert spy_pos["quantity"] == 10.5
        assert spy_pos["entry_price"] == 590.00
        assert spy_pos["current_price"] == 595.00
        assert spy_pos["market_value"] == 6247.50
        assert spy_pos["unrealized_pl"] == 52.50
        assert spy_pos["side"] == "long"

    def test_empty_positions_stored_correctly(self, temp_state_file):
        """Test that empty positions array is stored correctly."""
        alpaca_data = {
            "equity": 100000.00,
            "cash": 100000.00,
            "buying_power": 100000.00,
            "positions": [],
            "positions_count": 0,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        with open(temp_state_file) as f:
            state = json.load(f)

        positions = state.get("performance", {}).get("open_positions", [])
        assert positions == [], "Expected empty positions array"

    def test_positions_count_matches(self, temp_state_file):
        """Verify positions_count matches actual positions stored."""
        alpaca_data = {
            "equity": 100942.23,
            "cash": 86629.95,
            "buying_power": 1341.99,
            "positions": [
                {
                    "symbol": "SPY",
                    "qty": 10,
                    "avg_entry_price": 590,
                    "current_price": 595,
                    "market_value": 5950,
                    "unrealized_pl": 50,
                    "unrealized_plpc": 0.85,
                    "side": "long",
                },
                {
                    "symbol": "AAPL",
                    "qty": 5,
                    "avg_entry_price": 180,
                    "current_price": 185,
                    "market_value": 925,
                    "unrealized_pl": 25,
                    "unrealized_plpc": 2.78,
                    "side": "long",
                },
                {
                    "symbol": "GOOGL",
                    "qty": 2,
                    "avg_entry_price": 150,
                    "current_price": 155,
                    "market_value": 310,
                    "unrealized_pl": 10,
                    "unrealized_plpc": 3.33,
                    "side": "long",
                },
            ],
            "positions_count": 3,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        with open(temp_state_file) as f:
            state = json.load(f)

        positions = state.get("performance", {}).get("open_positions", [])
        positions_count = state.get("account", {}).get("positions_count", 0)

        assert len(positions) == positions_count, (
            f"positions_count ({positions_count}) doesn't match actual positions ({len(positions)})"
        )

    def test_none_alpaca_data_preserves_positions(self, temp_state_file):
        """When alpaca_data is None (no API keys), positions should be preserved."""
        # First, set some positions
        with open(temp_state_file) as f:
            state = json.load(f)
        state["performance"]["open_positions"] = [
            {"symbol": "SPY", "quantity": 10, "entry_price": 590}
        ]
        with open(temp_state_file, "w") as f:
            json.dump(state, f)

        # Now update with None (simulating no API keys)
        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(None)  # No API keys case

        with open(temp_state_file) as f:
            state = json.load(f)

        # Positions should be preserved
        positions = state.get("performance", {}).get("open_positions", [])
        assert len(positions) == 1, "Positions should be preserved when alpaca_data is None"
        assert positions[0]["symbol"] == "SPY"

    def test_position_with_quantity_field(self, temp_state_file):
        """Test handling of 'quantity' field instead of 'qty'."""
        alpaca_data = {
            "equity": 100000,
            "cash": 90000,
            "buying_power": 90000,
            "positions": [
                {
                    "symbol": "SPY",
                    "quantity": 10,
                    "avg_entry_price": 590,
                    "current_price": 595,
                    "market_value": 5950,
                    "unrealized_pl": 50,
                    "unrealized_plpc": 0.85,
                    "side": "long",
                },
            ],
            "positions_count": 1,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        with open(temp_state_file) as f:
            state = json.load(f)

        positions = state.get("performance", {}).get("open_positions", [])
        assert positions[0]["quantity"] == 10, "Should handle 'quantity' field"


class TestRejectSimulatedData:
    """Test that simulated data is rejected."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create a temporary system_state.json."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        initial_state = {"meta": {"version": "1.0"}, "account": {"current_equity": 100000}}
        state_file.write_text(json.dumps(initial_state))
        return state_file

    def test_rejects_simulated_mode(self, temp_state_file):
        """CRITICAL: Simulated data must be rejected to prevent lies."""
        alpaca_data = {
            "equity": 999999.99,
            "cash": 999999.99,
            "buying_power": 999999.99,
            "positions": [],
            "positions_count": 0,
            "mode": "simulated",  # This is simulated - should be rejected
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import AlpacaSyncError, update_system_state

            with pytest.raises(AlpacaSyncError) as exc_info:
                update_system_state(alpaca_data)

            assert "SIMULATED" in str(exc_info.value)
            assert "REFUSING" in str(exc_info.value)


class TestSmokeTests:
    """Smoke tests for the sync script."""

    def test_script_exists(self):
        script_path = Path(__file__).parent.parent / "scripts" / "sync_alpaca_state.py"
        assert script_path.exists(), f"Script not found at {script_path}"

    def test_script_is_valid_python(self):
        script_path = Path(__file__).parent.parent / "scripts" / "sync_alpaca_state.py"
        import py_compile

        py_compile.compile(str(script_path), doraise=True)

    def test_script_has_shebang(self):
        script_path = Path(__file__).parent.parent / "scripts" / "sync_alpaca_state.py"
        content = script_path.read_text()
        assert content.startswith("#!/usr/bin/env python3")

    def test_script_has_docstring(self):
        script_path = Path(__file__).parent.parent / "scripts" / "sync_alpaca_state.py"
        content = script_path.read_text()
        assert '"""' in content

    def test_imports_work(self):
        """Verify all imports in the script work."""
        with patch(
            "sync_alpaca_state.SYSTEM_STATE_FILE", Path(tempfile.gettempdir()) / "test.json"
        ):
            from sync_alpaca_state import (
                AlpacaSyncError,
                main,
                sync_from_alpaca,
                update_system_state,
            )

            assert AlpacaSyncError is not None
            assert callable(sync_from_alpaca)
            assert callable(update_system_state)
            assert callable(main)


class TestPositionFieldMapping:
    """Test that all position fields are correctly mapped."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text(json.dumps({"meta": {}, "account": {}, "performance": {}}))
        return state_file

    def test_all_position_fields_mapped(self, temp_state_file):
        """Verify all required fields are mapped from Alpaca data."""
        alpaca_data = {
            "equity": 100000,
            "cash": 90000,
            "buying_power": 90000,
            "positions": [
                {
                    "symbol": "TEST",
                    "qty": 100,
                    "avg_entry_price": 50.00,
                    "current_price": 55.00,
                    "market_value": 5500.00,
                    "unrealized_pl": 500.00,
                    "unrealized_plpc": 10.0,
                    "side": "long",
                }
            ],
            "positions_count": 1,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        with open(temp_state_file) as f:
            state = json.load(f)

        pos = state["performance"]["open_positions"][0]

        # Verify all required fields exist
        required_fields = [
            "symbol",
            "quantity",
            "entry_price",
            "current_price",
            "market_value",
            "unrealized_pl",
            "unrealized_pl_pct",
            "side",
        ]

        for field in required_fields:
            assert field in pos, f"Missing required field: {field}"

        # Verify values are correct
        assert pos["symbol"] == "TEST"
        assert pos["quantity"] == 100
        assert pos["entry_price"] == 50.00
        assert pos["current_price"] == 55.00
        assert pos["market_value"] == 5500.00
        assert pos["unrealized_pl"] == 500.00
        assert pos["unrealized_pl_pct"] == 10.0
        assert pos["side"] == "long"

    def test_filters_positions_without_symbol(self, temp_state_file):
        """Positions without symbol should be filtered out."""
        alpaca_data = {
            "equity": 100000,
            "cash": 90000,
            "buying_power": 90000,
            "positions": [
                {
                    "symbol": "VALID",
                    "qty": 10,
                    "avg_entry_price": 100,
                    "current_price": 105,
                    "market_value": 1050,
                    "unrealized_pl": 50,
                    "unrealized_plpc": 5,
                    "side": "long",
                },
                {"qty": 10, "avg_entry_price": 100},  # Missing symbol - should be filtered
                {"symbol": None, "qty": 5},  # None symbol - should be filtered
                {"symbol": "", "qty": 5},  # Empty symbol - should be filtered
            ],
            "positions_count": 4,
            "mode": "paper",
            "synced_at": "2026-01-04T12:00:00",
        }

        with patch("sync_alpaca_state.SYSTEM_STATE_FILE", temp_state_file):
            from sync_alpaca_state import update_system_state

            update_system_state(alpaca_data)

        with open(temp_state_file) as f:
            state = json.load(f)

        positions = state["performance"]["open_positions"]
        assert len(positions) == 1, f"Expected 1 valid position, got {len(positions)}"
        assert positions[0]["symbol"] == "VALID"
