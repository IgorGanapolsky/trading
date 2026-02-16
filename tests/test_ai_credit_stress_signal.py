"""Tests for AI credit stress signal updater."""

from __future__ import annotations

from scripts.update_ai_credit_stress_signal import (
    SeriesSummary,
    evaluate_ai_credit_stress_signal,
    parse_fred_csv,
)


def test_parse_fred_csv_ignores_missing_values():
    csv_text = "\n".join(
        [
            "DATE,BAMLH0A0HYM2",
            "2026-02-10,4.01",
            "2026-02-11,.",
            "2026-02-12,4.33",
        ]
    )

    points = parse_fred_csv(csv_text)
    assert len(points) == 2
    assert points[0][1] == 4.01
    assert points[1][1] == 4.33


def test_evaluate_ai_credit_stress_signal_blocked():
    metrics = {
        "high_yield_oas": SeriesSummary(
            series_id="BAMLH0A0HYM2",
            latest_value=4.7,
            latest_date="2026-02-16",
            lookback_change=0.6,
            point_count=20,
        ),
        "baa_minus_10y": SeriesSummary(
            series_id="BAA10Y",
            latest_value=3.1,
            latest_date="2026-02-16",
            lookback_change=0.2,
            point_count=20,
        ),
    }
    status, score, reasons = evaluate_ai_credit_stress_signal(metrics)
    assert status == "blocked"
    assert score >= 60
    assert reasons


def test_evaluate_ai_credit_stress_signal_pass():
    metrics = {
        "high_yield_oas": SeriesSummary(
            series_id="BAMLH0A0HYM2",
            latest_value=3.2,
            latest_date="2026-02-16",
            lookback_change=0.05,
            point_count=20,
        ),
        "baa_minus_10y": SeriesSummary(
            series_id="BAA10Y",
            latest_value=2.1,
            latest_date="2026-02-16",
            lookback_change=0.03,
            point_count=20,
        ),
    }
    status, score, _reasons = evaluate_ai_credit_stress_signal(metrics)
    assert status == "pass"
    assert score < 30


def test_evaluate_ai_credit_stress_signal_unknown_when_no_data():
    metrics = {
        "high_yield_oas": SeriesSummary(
            series_id="BAMLH0A0HYM2",
            latest_value=None,
            latest_date=None,
            lookback_change=None,
            point_count=0,
        ),
        "baa_minus_10y": SeriesSummary(
            series_id="BAA10Y",
            latest_value=None,
            latest_date=None,
            lookback_change=None,
            point_count=0,
        ),
    }
    status, score, reasons = evaluate_ai_credit_stress_signal(metrics)
    assert status == "unknown"
    assert score == 0.0
    assert reasons
