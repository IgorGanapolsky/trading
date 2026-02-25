"""Tests for trading policy A/B drift metrics."""

from __future__ import annotations

from pathlib import Path

from src.safety.trading_policy_drift import (
    collect_trading_policy_ab_metrics,
    extract_policy_values_from_text,
)


def test_extract_policy_values_from_text() -> None:
    text = """
    IRON_CONDOR_STOP_LOSS_MULTIPLIER = 2.0
    NORTH_STAR_MONTHLY_AFTER_TAX = 6000.0
    MAX_POSITIONS = 8
    """
    values = extract_policy_values_from_text(text)
    assert values["IRON_CONDOR_STOP_LOSS_MULTIPLIER"] == 2.0
    assert values["NORTH_STAR_MONTHLY_AFTER_TAX"] == 6000.0
    assert values["MAX_POSITIONS"] == 8


def _write_doc(path: Path, *, max_positions: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "IRON_CONDOR_STOP_LOSS_MULTIPLIER = 2.0",
                "NORTH_STAR_MONTHLY_AFTER_TAX = 6000.0",
                f"MAX_POSITIONS = {max_positions}",
            ]
        ),
        encoding="utf-8",
    )


def test_collect_trading_policy_ab_metrics_no_drift(tmp_path: Path) -> None:
    _write_doc(tmp_path / ".claude/CLAUDE.md")
    _write_doc(tmp_path / ".claude/rules/risk-management.md")
    _write_doc(tmp_path / ".claude/rules/trading.md")

    metrics = collect_trading_policy_ab_metrics(repo_root=tmp_path)

    assert metrics["drift_detected"] is False
    assert metrics["checks_failed"] == 0
    assert metrics["checks_passed"] == metrics["checks_total"]


def test_collect_trading_policy_ab_metrics_detects_drift(tmp_path: Path) -> None:
    _write_doc(tmp_path / ".claude/CLAUDE.md")
    _write_doc(tmp_path / ".claude/rules/risk-management.md", max_positions=5)
    _write_doc(tmp_path / ".claude/rules/trading.md")

    metrics = collect_trading_policy_ab_metrics(repo_root=tmp_path)

    assert metrics["drift_detected"] is True
    assert metrics["checks_failed"] == 1
    assert any("MAX_POSITIONS expected 8" in item for item in metrics["drift_items"])
