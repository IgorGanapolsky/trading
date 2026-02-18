"""Tests for autonomous_trader risk overlay refresh wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_refresh_risk_overlays_invokes_updater_scripts():
    # Import inside test so patches can target module symbols reliably.
    from scripts import autonomous_trader

    logger = MagicMock()

    with patch.object(autonomous_trader, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        autonomous_trader._refresh_risk_overlays(logger)

        assert mock_subprocess.run.call_count == 2
        calls = mock_subprocess.run.call_args_list
        first_cmd = calls[0].args[0]
        second_cmd = calls[1].args[0]

        assert any("update_ai_credit_stress_signal.py" in str(part) for part in first_cmd)
        assert any("update_north_star_operating_plan.py" in str(part) for part in second_cmd)

