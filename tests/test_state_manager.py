"""
Tests for scripts/state_manager.py

Ensures state management works correctly for trade recording and win rate tracking.
"""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.state_manager import StateManager


class TestStateManager:
    """Tests for StateManager class."""

    def test_init_creates_empty_state(self, tmp_path: Path) -> None:
        """StateManager should create empty state if file doesn't exist."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        assert "performance" in sm.state
        assert sm.state["performance"]["closed_trades"] == []
        assert sm.state["performance"]["winning_trades"] == 0
        assert sm.state["performance"]["losing_trades"] == 0

    def test_load_existing_state(self, tmp_path: Path) -> None:
        """StateManager should load existing state from file."""
        state_file = tmp_path / "test_state.json"
        existing_state = {
            "last_updated": "2026-01-13T10:00:00",
            "portfolio": {"equity": 5000, "cash": 4000},
            "performance": {
                "closed_trades": [],
                "winning_trades": 5,
                "losing_trades": 2,
                "win_rate": 71.4,
            },
        }
        state_file.write_text(json.dumps(existing_state))

        sm = StateManager(state_file=state_file)

        assert sm.state["performance"]["winning_trades"] == 5
        assert sm.state["performance"]["losing_trades"] == 2

    def test_record_winning_trade(self, tmp_path: Path) -> None:
        """Recording a winning trade should track it correctly."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        trade = sm.record_closed_trade(
            symbol="SOFI",
            entry_price=24.0,
            exit_price=26.0,
            quantity=100,
            entry_date="2026-01-13T09:00:00",
        )

        assert trade["is_winner"] is True
        assert trade["pl"] == 200.0  # (26-24) * 100
        assert trade["pl_pct"] == pytest.approx(8.33, rel=0.01)
        assert len(sm.state["performance"]["closed_trades"]) == 1

    def test_record_losing_trade(self, tmp_path: Path) -> None:
        """Recording a losing trade should track it correctly."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        trade = sm.record_closed_trade(
            symbol="F",
            entry_price=12.0,
            exit_price=11.0,
            quantity=50,
            entry_date="2026-01-13T09:00:00",
        )

        assert trade["is_winner"] is False
        assert trade["pl"] == -50.0  # (11-12) * 50
        assert len(sm.state["performance"]["closed_trades"]) == 1

    def test_save_and_reload_state(self, tmp_path: Path) -> None:
        """State should persist correctly after save."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        sm.record_closed_trade(
            symbol="SOFI",
            entry_price=24.0,
            exit_price=26.0,
            quantity=100,
        )
        sm.state["performance"]["winning_trades"] = 1
        sm.save_state()

        # Reload
        sm2 = StateManager(state_file=state_file)
        assert len(sm2.state["performance"]["closed_trades"]) == 1
        assert sm2.state["performance"]["winning_trades"] == 1

    def test_get_win_rate(self, tmp_path: Path) -> None:
        """Win rate calculation should be accurate."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        sm.state["performance"]["winning_trades"] = 8
        sm.state["performance"]["losing_trades"] = 2

        assert sm.get_win_rate() == 80.0

    def test_get_win_rate_zero_trades(self, tmp_path: Path) -> None:
        """Win rate should be 0 with no trades."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        assert sm.get_win_rate() == 0.0

    def test_get_total_pl(self, tmp_path: Path) -> None:
        """Total P/L should sum all closed trades."""
        state_file = tmp_path / "test_state.json"
        sm = StateManager(state_file=state_file)

        sm.record_closed_trade("SOFI", 24.0, 26.0, 100)  # +$200
        sm.record_closed_trade("F", 12.0, 11.0, 50)  # -$50

        assert sm.get_total_pl() == 150.0


class TestStateManagerIntegration:
    """Integration tests for StateManager with real system_state.json."""

    def test_default_path_exists(self) -> None:
        """Default state file path should be valid."""
        from scripts.state_manager import SYSTEM_STATE_PATH

        assert SYSTEM_STATE_PATH == Path("data/system_state.json")

    def test_handles_corrupted_json(self, tmp_path: Path) -> None:
        """StateManager should handle corrupted JSON gracefully."""
        state_file = tmp_path / "corrupted.json"
        state_file.write_text("{ this is not valid json }")

        sm = StateManager(state_file=state_file)

        # Should create fresh state, not crash
        assert "performance" in sm.state
        assert sm.state["performance"]["closed_trades"] == []
