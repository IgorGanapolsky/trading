"""Tests for USD macro sentiment signal updater."""

from datetime import date, timedelta

from scripts.update_usd_macro_sentiment_signal import (
    SeriesSummary,
    _build_payload,
    evaluate_usd_macro_sentiment_signal,
    parse_fred_csv,
)


def test_parse_fred_csv_skips_missing_values() -> None:
    csv_text = """DATE,DTWEXBGS
2026-02-16,110.12
2026-02-17,.
2026-02-18,109.77
"""
    points = parse_fred_csv(csv_text)
    assert len(points) == 2
    assert points[0][0].isoformat() == "2026-02-16"
    assert points[1][1] == 109.77


def test_evaluate_usd_macro_sentiment_returns_blocked_with_multiplier() -> None:
    metrics = {
        "broad_usd_index": SeriesSummary(
            series_id="DTWEXBGS",
            latest_value=100.0,
            latest_date="2026-02-19",
            ma_20=102.0,
            ma_50=103.0,
            pct_change_5d=-0.012,
            pct_change_20d=-0.03,
            point_count=120,
        ),
        "usd_per_euro": SeriesSummary(
            series_id="DEXUSEU",
            latest_value=1.12,
            latest_date="2026-02-19",
            ma_20=1.10,
            ma_50=1.105,
            pct_change_5d=0.01,
            pct_change_20d=0.022,
            point_count=120,
        ),
    }
    status, score, multiplier, reasons = evaluate_usd_macro_sentiment_signal(metrics)
    assert status == "blocked"
    assert score >= 60.0
    assert multiplier == 0.90
    assert reasons


def test_build_payload_marks_stale_as_unknown() -> None:
    stale_date = (date.today() - timedelta(days=20)).isoformat()
    metrics = {
        "broad_usd_index": SeriesSummary(
            series_id="DTWEXBGS",
            latest_value=100.0,
            latest_date=stale_date,
            ma_20=101.0,
            ma_50=102.0,
            pct_change_5d=-0.01,
            pct_change_20d=-0.02,
            point_count=120,
        )
    }
    payload = _build_payload(
        metrics=metrics,
        status="watch",
        bearish_score=45.0,
        position_size_multiplier=0.95,
        reasons=["example"],
        source="fred_public",
        max_stale_days=7,
    )
    assert payload["status"] == "unknown"
    assert payload["position_size_multiplier"] == 1.0
    assert payload["stale_days"] >= 20
