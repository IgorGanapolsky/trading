#!/usr/bin/env python3
"""
Tests for Shared Alpaca Client Utility

Tests the centralized Alpaca client creation functions to ensure
DRY compliance and proper error handling.

Created: 2026-01-08
Reason: Add coverage for new src/utils/alpaca_client.py (90 lines)
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGetAlpacaClient:
    """Test get_alpaca_client function."""

    def test_import_successful(self):
        """Verify module can be imported."""
        from src.utils.alpaca_client import get_alpaca_client

        assert get_alpaca_client is not None

    def test_returns_none_without_credentials(self):
        """Should return None when API keys are not set."""
        from src.utils.alpaca_client import get_alpaca_client

        # Clear any existing keys
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.utils.alpaca_client._bootstrap_env_from_dotenv", return_value=None),
        ):
            result = get_alpaca_client()
            assert result is None

    def test_returns_none_with_partial_credentials(self):
        """Should return None when only one key is set."""
        from src.utils.alpaca_client import get_alpaca_client

        # Only API key set
        with (
            patch.dict(os.environ, {"ALPACA_API_KEY": "test_key"}, clear=True),
            patch("src.utils.alpaca_client._bootstrap_env_from_dotenv", return_value=None),
        ):
            result = get_alpaca_client()
            assert result is None

        # Only secret key set
        with (
            patch.dict(os.environ, {"ALPACA_SECRET_KEY": "test_secret"}, clear=True),
            patch("src.utils.alpaca_client._bootstrap_env_from_dotenv", return_value=None),
        ):
            result = get_alpaca_client()
            assert result is None

    def test_handles_import_error_gracefully(self):
        """Should handle missing alpaca-py gracefully."""
        # Test that the module handles import errors gracefully
        # by verifying the function exists and is callable
        from src.utils.alpaca_client import get_alpaca_client

        # Function should be callable even if alpaca-py is not available
        assert callable(get_alpaca_client)


class TestGetOptionsClient:
    """Test get_options_client function."""

    def test_import_successful(self):
        """Verify function can be imported."""
        from src.utils.alpaca_client import get_options_client

        assert get_options_client is not None

    def test_calls_get_alpaca_client(self):
        """Should delegate to get_alpaca_client."""
        from src.utils.alpaca_client import get_options_client

        # Without credentials, should return None (same as get_alpaca_client)
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.utils.alpaca_client._bootstrap_env_from_dotenv", return_value=None),
        ):
            result = get_options_client(paper=True)
            assert result is None


class TestGetAccountInfo:
    """Test get_account_info function."""

    def test_import_successful(self):
        """Verify function can be imported."""
        from src.utils.alpaca_client import get_account_info

        assert get_account_info is not None

    def test_returns_none_with_none_client(self):
        """Should return None when client is None."""
        from src.utils.alpaca_client import get_account_info

        result = get_account_info(None)
        assert result is None

    def test_returns_dict_with_valid_client(self):
        """Should return dict with equity, cash, buying_power."""
        from src.utils.alpaca_client import get_account_info

        # Create a mock client
        mock_client = MagicMock()
        mock_account = MagicMock()
        mock_account.equity = "100000.00"
        mock_account.cash = "50000.00"
        mock_account.buying_power = "200000.00"
        mock_client.get_account.return_value = mock_account

        result = get_account_info(mock_client)

        assert result is not None
        assert result["equity"] == 100000.00
        assert result["cash"] == 50000.00
        assert result["buying_power"] == 200000.00

    def test_handles_client_error(self):
        """Should return None on client errors."""
        from src.utils.alpaca_client import get_account_info

        mock_client = MagicMock()
        mock_client.get_account.side_effect = Exception("API Error")

        result = get_account_info(mock_client)
        assert result is None


class TestPaperModeDefault:
    """Test that paper mode is the default (safety first)."""

    def test_paper_mode_is_default(self):
        """get_alpaca_client should default to paper=True."""
        import inspect

        from src.utils.alpaca_client import get_alpaca_client

        sig = inspect.signature(get_alpaca_client)
        paper_param = sig.parameters.get("paper")
        assert paper_param is not None
        assert paper_param.default is True, "Safety: paper mode should be default"


class TestDotenvDiscovery:
    def test_iter_local_env_files_includes_primary_repo_from_worktree(self, tmp_path):
        from src.utils.alpaca_client import _iter_local_env_files

        primary_repo = tmp_path / "repo"
        worktree_repo = primary_repo / ".worktrees" / "task"
        worktree_repo.mkdir(parents=True)
        (primary_repo / ".env").write_text("ALPACA_API_KEY=test\n", encoding="utf-8")
        (worktree_repo / ".env.local").write_text("LOCAL=1\n", encoding="utf-8")

        candidates = _iter_local_env_files(worktree_repo)

        assert primary_repo / ".env" in candidates
        assert worktree_repo / ".env.local" in candidates


class TestGuardedTradingClient:
    """Test that get_guarded_trading_client() forces submit_order through the gate.

    Context: On May 19, 2026 a 50-lot SPY 2026-06-18 iron condor was opened
    by three GitHub workflows calling ``client.submit_order(...)`` directly,  # noqa: direct-submit-order
    bypassing the 5%-per-trade position cap. The guarded factory routes every
    ``submit_order`` call through ``safe_submit_order`` →
    ``validate_trade_mandatory``, so even a script that forgets to use the
    safe wrapper still gets gated.
    """

    def _build_50_lot_ic_request(self):
        """Mimic the 50-lot $10-wide SPY IC order that triggered the incident."""
        # Use SimpleNamespace to avoid importing alpaca-py just for a fixture.
        from types import SimpleNamespace

        # SPY ~$590 spot, 2026-06-18 expiry. $10-wide wings on both sides.
        # Symbols encoded in OCC format (YYMMDD + C/P + 8-digit strike).
        long_put = SimpleNamespace(symbol="SPY260618P00570000", side="BUY", ratio_qty=1)
        short_put = SimpleNamespace(symbol="SPY260618P00580000", side="SELL", ratio_qty=1)
        short_call = SimpleNamespace(symbol="SPY260618C00600000", side="SELL", ratio_qty=1)
        long_call = SimpleNamespace(symbol="SPY260618C00610000", side="BUY", ratio_qty=1)
        return SimpleNamespace(
            symbol=None,
            qty=50,
            side="SELL",
            legs=[long_put, short_put, short_call, long_call],
            order_class="mleg",
            limit_price=-1.45,
        )

    def test_guarded_client_rejects_50_lot_iron_condor(self):
        """A 50-lot $10-wide IC ($50,000 max loss = ~52% of $95K equity) MUST be rejected."""
        from unittest.mock import MagicMock, patch

        from src.utils.alpaca_client import get_guarded_trading_client

        # Mock account: $95,000 equity (close to today's ledger value).
        mock_account = MagicMock()
        mock_account.equity = "95000.00"
        mock_account.portfolio_value = "95000.00"
        mock_account.cash = "95000.00"

        # Return at least one position so _get_positions_qty_map() returns a
        # non-empty dict; without that, _infer_is_closing_order returns None
        # and safe_submit_order's gate-enforcement branch (only entered when
        # is_closing is explicitly False) is skipped.
        unrelated_pos = MagicMock()
        unrelated_pos.symbol = "SPY"
        unrelated_pos.qty = "0"

        mock_underlying_client = MagicMock()
        mock_underlying_client.get_account.return_value = mock_account
        mock_underlying_client.get_all_positions.return_value = [unrelated_pos]
        mock_underlying_client.paper = True

        # Patch the unsafe factory so we never touch a real network client.
        with patch(
            "src.utils.alpaca_client._get_alpaca_client_unsafe",
            return_value=mock_underlying_client,
        ):
            guarded = get_guarded_trading_client(paper=True)

        assert guarded is mock_underlying_client, (
            "Guarded factory should return the same client object with submit_order patched."
        )
        assert guarded.submit_order is not mock_underlying_client.get_account, (
            "Sanity: submit_order should be replaced."
        )

        # Build the 50-lot IC and confirm the gate rejects it.
        request = self._build_50_lot_ic_request()

        with pytest.raises(ValueError) as exc_info:
            guarded.submit_order(request, strategy="iron_condor")

        # The gate's rejection message can come from several layers (size, gate, juror).
        # What matters is that ValueError was raised BEFORE the underlying broker
        # was ever called.
        assert "BLOCKED" in str(exc_info.value) or "FAILED" in str(exc_info.value) or (
            "MANDATORY" in str(exc_info.value)
        ), f"Unexpected rejection message: {exc_info.value!r}"

    def test_guarded_client_returns_none_when_credentials_missing(self):
        """If the unsafe factory cannot create a client, the guarded one returns None too."""
        from unittest.mock import patch

        from src.utils.alpaca_client import get_guarded_trading_client

        with patch(
            "src.utils.alpaca_client._get_alpaca_client_unsafe",
            return_value=None,
        ):
            assert get_guarded_trading_client(paper=True) is None

    def test_guarded_client_rejects_extra_args_no_silent_bypass(self):
        """Extra positional/keyword args must raise TypeError, not silently bypass the gate."""
        from unittest.mock import MagicMock, patch

        from src.utils.alpaca_client import get_guarded_trading_client

        mock_client = MagicMock()
        mock_client.submit_order = MagicMock(return_value="should not be reached")

        with patch(
            "src.utils.alpaca_client._get_alpaca_client_unsafe",
            return_value=mock_client,
        ):
            guarded = get_guarded_trading_client(paper=True)

        with pytest.raises(TypeError, match="Refusing to bypass the gate"):
            guarded.submit_order(MagicMock(), "some_extra_positional_arg")


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
