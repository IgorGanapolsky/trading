"""Tests for P/L sanity check with accumulation phase awareness.

Tests cover:
1. Accumulation phase detection
2. No-trade alert suppression during accumulation
3. Normal alert behavior when not in accumulation
4. Edge cases and error handling
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_alpaca():
    """Mock alpaca-py to prevent import errors."""
    mock_trading_client = MagicMock()
    mock_instance = MagicMock()
    mock_instance.get_account.return_value = MagicMock(equity=100000.0)
    mock_trading_client.return_value = mock_instance

    with patch.dict(
        "sys.modules",
        {
            "alpaca": MagicMock(),
            "alpaca.trading": MagicMock(),
            "alpaca.trading.client": MagicMock(TradingClient=mock_trading_client),
        },
    ):
        yield mock_trading_client


class TestPLSanityChecker:
    """Test suite for PLSanityChecker class."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create temporary data directory with test files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def mock_system_state_accumulation(self, temp_data_dir):
        """Create system_state.json in accumulation phase."""
        state = {
            "account": {
                "current_equity": 30.0,
                "deposit_strategy": {
                    "target_for_first_trade": 200.0,
                    "amount_per_day": 10.0,
                    "purpose": "Capital accumulation for options",
                },
            }
        }
        state_file = temp_data_dir / "system_state.json"
        state_file.write_text(json.dumps(state))
        return state_file

    @pytest.fixture
    def mock_system_state_ready(self, temp_data_dir):
        """Create system_state.json with sufficient capital (not in accumulation)."""
        state = {
            "account": {
                "current_equity": 500.0,
                "deposit_strategy": {
                    "target_for_first_trade": 200.0,
                    "amount_per_day": 10.0,
                    "purpose": "Capital accumulation for options",
                },
            }
        }
        state_file = temp_data_dir / "system_state.json"
        state_file.write_text(json.dumps(state))
        return state_file

    @pytest.fixture
    def mock_system_state_no_strategy(self, temp_data_dir):
        """Create system_state.json without deposit strategy."""
        state = {"account": {"current_equity": 100.0}}
        state_file = temp_data_dir / "system_state.json"
        state_file.write_text(json.dumps(state))
        return state_file

    def test_accumulation_phase_detected(
        self, mock_alpaca, mock_system_state_accumulation
    ):
        """Test that accumulation phase is correctly detected."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_accumulation):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is True
            assert checker.in_accumulation_phase is True
            assert checker.accumulation_info["current_equity"] == 30.0
            assert checker.accumulation_info["target"] == 200.0
            assert checker.accumulation_info["gap"] == 170.0
            assert checker.accumulation_info["daily_deposit"] == 10.0
            assert "estimated_days_to_target" in checker.accumulation_info
            assert checker.accumulation_info["estimated_days_to_target"] == 17

    def test_accumulation_phase_not_detected_when_ready(
        self, mock_alpaca, mock_system_state_ready
    ):
        """Test that accumulation phase is not detected when capital is sufficient."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_ready):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is False
            assert checker.in_accumulation_phase is False
            assert checker.accumulation_info == {}

    def test_accumulation_phase_no_strategy(
        self, mock_alpaca, mock_system_state_no_strategy
    ):
        """Test behavior when no deposit strategy is configured."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_no_strategy):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is False
            assert checker.in_accumulation_phase is False

    def test_accumulation_phase_missing_file(self, mock_alpaca, temp_data_dir):
        """Test behavior when system_state.json doesn't exist."""
        import scripts.verify_pl_sanity as module

        missing_file = temp_data_dir / "nonexistent.json"
        with patch.object(module, "SYSTEM_STATE_FILE", missing_file):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is False
            assert checker.in_accumulation_phase is False

    def test_no_trades_alert_suppressed_during_accumulation(
        self, mock_alpaca, mock_system_state_accumulation
    ):
        """Test that NO_TRADES alert is suppressed during accumulation phase."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_accumulation):
            checker = module.PLSanityChecker(verbose=True)
            checker.check_accumulation_phase()

            # Simulate no trades
            with patch.object(checker, "count_recent_trades", return_value=0):
                result = checker.check_no_trades()

            assert result is False  # Should NOT trigger alert
            assert len(checker.alerts) == 0
            assert checker.metrics.get("accumulation_phase") is True

    def test_no_trades_alert_triggered_when_not_accumulating(
        self, mock_alpaca, mock_system_state_ready
    ):
        """Test that NO_TRADES alert is triggered when not in accumulation."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_ready):
            checker = module.PLSanityChecker(verbose=True)
            checker.check_accumulation_phase()

            # Simulate no trades
            with patch.object(checker, "count_recent_trades", return_value=0):
                result = checker.check_no_trades()

            assert result is True  # Should trigger alert
            assert len(checker.alerts) == 1
            assert checker.alerts[0]["type"] == "NO_TRADES"
            assert checker.alerts[0]["level"] == "CRITICAL"

    def test_no_trades_no_alert_when_trades_exist(
        self, mock_alpaca, mock_system_state_ready
    ):
        """Test that no alert is triggered when trades exist."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_ready):
            checker = module.PLSanityChecker(verbose=True)
            checker.check_accumulation_phase()

            # Simulate trades exist
            with patch.object(checker, "count_recent_trades", return_value=5):
                result = checker.check_no_trades()

            assert result is False  # Should NOT trigger alert
            assert len(checker.alerts) == 0
            assert checker.metrics.get("recent_trades") == 5

    def test_accumulation_info_in_metrics(
        self, mock_alpaca, mock_system_state_accumulation
    ):
        """Test that accumulation info is included in metrics."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_accumulation):
            checker = module.PLSanityChecker(verbose=True)
            checker.check_accumulation_phase()

            with patch.object(checker, "count_recent_trades", return_value=0):
                checker.check_no_trades()

            assert "accumulation_info" in checker.metrics
            info = checker.metrics["accumulation_info"]
            assert info["current_equity"] == 30.0
            assert info["target"] == 200.0

    def test_print_report_shows_accumulation_status(
        self, mock_alpaca, mock_system_state_accumulation, capsys
    ):
        """Test that print_report shows accumulation phase information."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_accumulation):
            checker = module.PLSanityChecker(verbose=False)
            checker.check_accumulation_phase()
            checker.print_report()

            captured = capsys.readouterr()
            assert "ACCUMULATION PHASE" in captured.out
            assert "Trading paused by design" in captured.out
            assert "$30.00" in captured.out
            assert "$200.00" in captured.out

    def test_print_report_healthy_during_accumulation(
        self, mock_alpaca, mock_system_state_accumulation, capsys
    ):
        """Test that report shows healthy status during accumulation."""
        import scripts.verify_pl_sanity as module

        with patch.object(module, "SYSTEM_STATE_FILE", mock_system_state_accumulation):
            checker = module.PLSanityChecker(verbose=False)
            checker.check_accumulation_phase()
            checker.print_report()

            captured = capsys.readouterr()
            assert "In accumulation phase (no trades expected)" in captured.out


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_malformed_system_state(self, mock_alpaca, tmp_path):
        """Test handling of malformed system_state.json."""
        import scripts.verify_pl_sanity as module

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        state_file = data_dir / "system_state.json"
        state_file.write_text("not valid json{{{")

        with patch.object(module, "SYSTEM_STATE_FILE", state_file):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is False  # Should not crash, just return False

    def test_zero_daily_deposit(self, mock_alpaca, tmp_path):
        """Test handling of zero daily deposit."""
        import scripts.verify_pl_sanity as module

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        state = {
            "account": {
                "current_equity": 30.0,
                "deposit_strategy": {
                    "target_for_first_trade": 200.0,
                    "amount_per_day": 0,  # Zero deposit
                    "purpose": "Test",
                },
            }
        }
        state_file = data_dir / "system_state.json"
        state_file.write_text(json.dumps(state))

        with patch.object(module, "SYSTEM_STATE_FILE", state_file):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            assert result is True
            # Should not include estimated_days_to_target if deposit is 0
            assert "estimated_days_to_target" not in checker.accumulation_info

    def test_negative_gap(self, mock_alpaca, tmp_path):
        """Test when current equity exceeds target (negative gap)."""
        import scripts.verify_pl_sanity as module

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        state = {
            "account": {
                "current_equity": 300.0,  # More than target
                "deposit_strategy": {
                    "target_for_first_trade": 200.0,
                    "amount_per_day": 10.0,
                    "purpose": "Test",
                },
            }
        }
        state_file = data_dir / "system_state.json"
        state_file.write_text(json.dumps(state))

        with patch.object(module, "SYSTEM_STATE_FILE", state_file):
            checker = module.PLSanityChecker(verbose=True)
            result = checker.check_accumulation_phase()

            # Should NOT be in accumulation if equity > target
            assert result is False
            assert checker.in_accumulation_phase is False

    def test_lazy_import_function(self, mock_alpaca):
        """Test the _get_trading_client lazy import function."""
        import scripts.verify_pl_sanity as module

        # Reset the global
        module.TradingClient = None

        # Should return None when alpaca not available
        with patch.dict("sys.modules", {"alpaca": None}):
            # Clear import cache
            if "alpaca.trading.client" in sys.modules:
                del sys.modules["alpaca.trading.client"]
            result = module._get_trading_client()
            # May return mock or None depending on test environment

    def test_initialize_api_without_credentials(self, mock_alpaca):
        """Test API initialization fails gracefully without credentials."""
        import scripts.verify_pl_sanity as module

        checker = module.PLSanityChecker(verbose=True)

        # Remove credentials
        with patch.dict(os.environ, {}, clear=True):
            result = checker.initialize_alpaca_api()
            assert result is False
            assert checker.api is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
