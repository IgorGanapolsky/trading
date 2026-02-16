"""Tests for weekly cadence KPI checker."""

from scripts.check_weekly_cadence_gate import _should_fail, evaluate_weekly_cadence


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
    assert result["top_rejection_reasons"][0]["count"] == 2


def test_should_fail_respects_strict_and_threshold():
    result_warning = {"passed": False, "alert_level": "warning"}
    result_critical = {"passed": False, "alert_level": "critical"}
    result_ok = {"passed": True, "alert_level": "ok"}

    assert _should_fail(result=result_ok, strict=False, fail_on="warning") is False
    assert _should_fail(result=result_warning, strict=False, fail_on="critical") is False
    assert _should_fail(result=result_critical, strict=False, fail_on="critical") is True
    assert _should_fail(result=result_warning, strict=True, fail_on="none") is True
