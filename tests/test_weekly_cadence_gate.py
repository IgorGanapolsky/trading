"""Tests for weekly cadence KPI checker."""

from scripts.check_weekly_cadence_gate import (
    _should_fail,
    evaluate_weekly_cadence,
    markdown_public_report,
)


def test_evaluate_weekly_cadence_extracts_kpi_and_diagnostic():
    state = {
        "north_star_weekly_gate": {
            "cadence_kpi": {
                "passed": False,
                "alert_level": "warning",
                "summary": "Cadence KPI miss.",
                "qualified_setups_observed": 1,
                "min_qualified_setups_per_week": 3,
                "closed_trades_observed": 1,
                "min_closed_trades_per_week": 1,
            },
            "no_trade_diagnostic": {
                "summary": "Likely blocked by liquidity.",
                "blocked_categories": ["liquidity"],
                "gate_status": {
                    "ai_credit_stress": {
                        "status": "watch",
                        "severity_score": 42.0,
                        "source": "fred_public",
                    },
                    "usd_macro": {
                        "status": "watch",
                        "bearish_score": 37.0,
                        "position_size_multiplier": 0.95,
                        "source": "fred_public",
                    },
                    "ai_cycle": {
                        "status": "blocked",
                        "severity_score": 72.0,
                        "position_size_multiplier": 0.85,
                        "regime": "capex_deceleration",
                        "capex_deceleration_shock": True,
                        "source": "yfinance_public",
                    },
                },
                "top_rejection_reasons": [{"reason": "Vol=0.1x (low)", "count": 2}],
            },
        }
    }

    result = evaluate_weekly_cadence(state)
    assert result["passed"] is False
    assert result["alert_level"] == "warning"
    assert result["qualified_setups_observed"] == 1
    assert result["min_qualified_setups_per_week"] == 3
    assert result["blocked_categories"] == ["liquidity"]
    assert result["ai_credit_stress_status"] == "watch"
    assert result["ai_credit_stress_score"] == 42.0
    assert result["usd_macro_status"] == "watch"
    assert result["usd_macro_score"] == 37.0
    assert result["usd_macro_multiplier"] == 0.95
    assert result["ai_cycle_status"] == "blocked"
    assert result["ai_cycle_score"] == 72.0
    assert result["ai_cycle_multiplier"] == 0.85
    assert result["ai_cycle_regime"] == "capex_deceleration"
    assert result["ai_cycle_capex_deceleration_shock"] is True
    assert result["top_rejection_reasons"][0]["count"] == 2


def test_should_fail_respects_strict_and_threshold():
    result_warning = {"passed": False, "alert_level": "warning"}
    result_critical = {"passed": False, "alert_level": "critical"}
    result_ok = {"passed": True, "alert_level": "ok"}

    assert _should_fail(result=result_ok, strict=False, fail_on="warning") is False
    assert _should_fail(result=result_warning, strict=False, fail_on="critical") is False
    assert _should_fail(result=result_critical, strict=False, fail_on="critical") is True
    assert _should_fail(result=result_warning, strict=True, fail_on="none") is True


def test_markdown_public_report_is_minimal_and_deterministic():
    result = {
        "passed": False,
        "alert_level": "warning",
        "qualified_setups_observed": 1,
        "min_qualified_setups_per_week": 3,
        "closed_trades_observed": 0,
        "min_closed_trades_per_week": 1,
        "blocked_categories": ["liquidity"],
        "summary": "do not include this in public artifact",
        "diagnostic_summary": "do not include this either",
        "ai_credit_stress_source": "internal_only",
    }
    text = markdown_public_report(result)
    assert "Weekly Cadence KPI Check" in text
    assert "Qualified Setups: `1/3`" in text
    assert "Blocked Categories: `liquidity`" in text
    assert "do not include" not in text
    assert "ai_credit_stress_source" not in text
