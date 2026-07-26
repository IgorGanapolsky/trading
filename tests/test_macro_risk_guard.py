import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.safety.macro_risk_guard import MacroRiskGuard


def test_macro_guard_oil_spike():
    guard = MacroRiskGuard()
    # 10% spike in oil
    vitals = {"oil_change": 0.10, "oil_price": 85.0, "yield_change": 0.01}
    safe, reason = guard.check_macro_vitals(vitals)
    assert safe is False
    assert "Oil volatility" in reason


def test_macro_guard_oil_price_limit():
    guard = MacroRiskGuard()
    # Oil at $105
    vitals = {"oil_change": 0.01, "oil_price": 105.0, "yield_change": 0.01}
    safe, reason = guard.check_macro_vitals(vitals)
    assert safe is False
    assert "price ($105.00)" in reason


def test_macro_guard_yield_spike():
    guard = MacroRiskGuard()
    # 6% move in yields
    vitals = {"oil_change": 0.01, "oil_price": 75.0, "yield_change": 0.06}
    safe, reason = guard.check_macro_vitals(vitals)
    assert safe is False
    assert "Fiscal" in reason.upper() or "Yield" in reason


def test_macro_guard_normal_conditions():
    guard = MacroRiskGuard()
    vitals = {"oil_change": 0.01, "oil_price": 75.0, "yield_change": 0.01}
    safe, reason = guard.check_macro_vitals(vitals)
    assert safe is True
    assert reason == ""


@patch("src.safety.macro_risk_guard.logger")
def test_macro_guard_autonomous_fetch_success(mock_logger):
    # Mock Alpaca client and bars data
    mock_client = MagicMock()
    mock_bar_current = MagicMock(close=80.0)
    mock_bar_prev = MagicMock(close=75.0)

    mock_bars = MagicMock()
    mock_bars.data = {
        "USO": [mock_bar_prev, mock_bar_current],
        "TNX": [mock_bar_prev, mock_bar_current],  # Reuse for simplicity
    }
    mock_client.get_stock_bars.return_value = mock_bars

    guard = MacroRiskGuard(data_client=mock_client)
    snapshot = guard.get_macro_snapshot()

    assert snapshot["oil_price"] == 80.0
    assert snapshot["oil_change"] == (80.0 - 75.0) / 75.0
    assert snapshot["yield_change"] == (80.0 - 75.0) / 75.0


def test_macro_guard_fails_closed_on_none_client():
    guard = MacroRiskGuard(data_client=None)
    snapshot = guard.get_macro_snapshot()
    assert snapshot["oil_price"] == 75.0  # Baseline default


def test_macro_guard_blocks_fresh_perplexity_event_risk(tmp_path: Path):
    intel_path = tmp_path / "trading_intel_latest.json"
    intel_path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "recommendation": "BLOCK_NEW_IC",
                "risk_score": 0.82,
                "gate_contract": {
                    "blocks_new_iron_condors": True,
                    "reason": "Fresh FOMC event risk.",
                },
            }
        ),
        encoding="utf-8",
    )

    guard = MacroRiskGuard(data_client=None, intel_path=intel_path)
    vitals = {"oil_change": 0.01, "oil_price": 75.0, "yield_change": 0.01}
    safe, reason = guard.check_macro_vitals(vitals)

    assert safe is False
    assert "PERPLEXITY EVENT RISK HALT" in reason


def test_macro_guard_ignores_stale_perplexity_event_risk(tmp_path: Path):
    intel_path = tmp_path / "trading_intel_latest.json"
    intel_path.write_text(
        json.dumps(
            {
                "generated_at_utc": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                "recommendation": "BLOCK_NEW_IC",
                "risk_score": 0.92,
                "gate_contract": {"blocks_new_iron_condors": True},
            }
        ),
        encoding="utf-8",
    )

    guard = MacroRiskGuard(data_client=None, intel_path=intel_path, intel_max_age_minutes=60)
    vitals = {"oil_change": 0.01, "oil_price": 75.0, "yield_change": 0.01}
    safe, reason = guard.check_macro_vitals(vitals)

    assert safe is True
    assert reason == ""
