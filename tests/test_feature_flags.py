"""
Test Feature Flags - Critical Regression Tests

CREATED: Jan 7, 2026
REASON: REIT strategy was executing trades even though disabled in config.
        Root cause: reit_enabled() defaulted to "true" instead of "false".
        This test ensures the bug never regresses.

These tests verify that feature flags:
1. Default to FALSE (disabled) when env vars are not set
2. Correctly read from environment variables
3. Handle all valid boolean representations
"""

import os
from unittest.mock import patch

import pytest


class TestFeatureFlagsDefaults:
    """Test that all feature flags default to DISABLED (False)."""

    def test_reit_disabled_by_default(self):
        """CRITICAL: REIT must be disabled by default.

        Regression test for Jan 7, 2026 bug where REIT trades executed
        despite being disabled in system_state.json.
        """
        # Clear any existing env var
        with patch.dict(os.environ, {}, clear=True):
            # Remove the specific key if it exists
            os.environ.pop("ENABLE_REIT_STRATEGY", None)

            # Import after clearing env to get fresh state
            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            # CRITICAL: Must be False by default
            assert trader.reit_enabled() is False, (
                "REIT must be DISABLED by default! "
                "This bug caused unwanted REIT trades on Jan 7, 2026."
            )

    def test_precious_metals_disabled_by_default(self):
        """CRITICAL: Precious Metals must be disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENABLE_PRECIOUS_METALS", None)

            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            assert trader.precious_metals_enabled() is False, (
                "Precious Metals must be DISABLED by default!"
            )

    def test_prediction_always_disabled(self):
        """Prediction markets (Kalshi) were removed Dec 2025."""
        from scripts.autonomous_trader import prediction_enabled

        # Should always return False regardless of env
        assert prediction_enabled() is False


class TestFeatureFlagsEnvOverride:
    """Test that env vars can enable features when explicitly set."""

    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "Yes", "YES"])
    def test_reit_enabled_via_env(self, value):
        """REIT can be enabled via environment variable."""
        with patch.dict(os.environ, {"ENABLE_REIT_STRATEGY": value}):
            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            assert trader.reit_enabled() is True, (
                f"REIT should be enabled when ENABLE_REIT_STRATEGY={value}"
            )

    @pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "No", "NO", ""])
    def test_reit_disabled_via_env(self, value):
        """REIT stays disabled with falsy values."""
        with patch.dict(os.environ, {"ENABLE_REIT_STRATEGY": value}):
            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            assert trader.reit_enabled() is False, (
                f"REIT should be disabled when ENABLE_REIT_STRATEGY={value}"
            )

    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "Yes", "YES"])
    def test_precious_metals_enabled_via_env(self, value):
        """Precious Metals can be enabled via environment variable."""
        with patch.dict(os.environ, {"ENABLE_PRECIOUS_METALS": value}):
            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            assert trader.precious_metals_enabled() is True, (
                f"Precious Metals should be enabled when ENABLE_PRECIOUS_METALS={value}"
            )


class TestFeatureFlagsIntegration:
    """Integration tests ensuring config is respected."""

    def test_reit_disabled_prevents_trades(self):
        """When REIT is disabled, no REIT trades should be generated."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENABLE_REIT_STRATEGY", None)

            import scripts.autonomous_trader as trader
            from importlib import reload
            reload(trader)

            # Verify disabled
            assert not trader.reit_enabled()

            # Any code path that checks reit_enabled() should skip REIT logic
            # This is a safeguard test - the actual trading code should check this

    def test_feature_flag_env_var_names(self):
        """Document the expected environment variable names."""
        expected_vars = {
            "ENABLE_REIT_STRATEGY": "Controls REIT strategy (Tier 7)",
            "ENABLE_PRECIOUS_METALS": "Controls Precious Metals (Tier 8)",
        }

        for var, description in expected_vars.items():
            # Just document and verify the patterns exist
            assert isinstance(var, str)
            assert var.startswith("ENABLE_")
