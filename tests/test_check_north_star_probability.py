"""Tests for scripts/check_north_star_probability.py."""

from __future__ import annotations


def test_probability_report_reads_snapshot_score_and_label(monkeypatch, capsys):
    import scripts.check_north_star_probability as module

    monkeypatch.setattr(
        module,
        "compute_milestone_snapshot",
        lambda: {
            "north_star_probability": {
                "score": 42.0,
                "label": "medium",
                "target_mode": "asap_monthly_income",
                "estimated_monthly_after_tax_from_expectancy": 612.34,
                "monthly_target_progress_pct": 10.21,
            }
        },
    )

    module.main()
    output = capsys.readouterr().out
    assert "Confidence Score: 42.0%" in output
    assert "Label: MEDIUM" in output
