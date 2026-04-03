from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_public_status import (
    build_public_status,
    check_public_surfaces,
    render_home,
    render_progress_dashboard,
    write_public_surfaces,
)


def _seed_repo(tmp_path: Path) -> Path:
    (tmp_path / "artifacts/daily_scorecard").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/runtime").mkdir(parents=True, exist_ok=True)
    scorecard = {
        "generated_at_et": "2026-04-03T10:33:34-04:00",
        "paper": {
            "equity": 93990.30,
            "total_pnl_today": -14.0,
            "realized_pnl_today": 0.0,
            "unrealized_pnl_today": -14.0,
            "fills_today_count": 0,
        },
        "live": {"equity": 0.0, "total_pnl_today": 0.0},
    }
    state = {
        "north_star_weekly_gate": {
            "mode": "defensive",
            "block_new_positions": True,
            "verified_edge_available": True,
            "recommended_max_position_pct": 0.01,
            "sample_size": 81,
            "expectancy_per_trade": -14.1852,
            "win_rate_pct": 2.47,
            "reason": "CRITICAL: Negative expectancy.",
            "cadence_kpi": {
                "qualified_setups_observed": 0,
                "closed_trades_observed": 81,
            },
            "scaling_sample_gate": {
                "closed_trades_observed": 134,
                "min_closed_trades_for_scaling": 30,
            },
        }
    }
    runtime = {
        "captured_at": "2026-04-03T14:33:34+00:00",
        "paper": {
            "equity": 93990.30,
            "daily_change": -14.0,
            "positions_count": 4,
        },
        "live": {
            "equity": 0.0,
            "daily_change": 0.0,
            "positions_count": 0,
        },
    }
    trades = {
        "meta": {"last_sync": "2026-04-03T14:33:35+00:00"},
        "stats": {
            "closed_trades": 134,
            "wins": 13,
            "losses": 120,
            "breakeven": 1,
            "win_rate_pct": 9.7,
            "profit_factor": 0.14,
            "total_realized_pnl": -2756.0,
        },
    }
    (tmp_path / "artifacts/daily_scorecard/latest_daily_scorecard.json").write_text(
        json.dumps(scorecard), encoding="utf-8"
    )
    (tmp_path / "data/runtime/intraday_pnl_latest.json").write_text(
        json.dumps(runtime), encoding="utf-8"
    )
    (tmp_path / "data/system_state.json").write_text(json.dumps(state), encoding="utf-8")
    (tmp_path / "data/trades.json").write_text(json.dumps(trades), encoding="utf-8")
    return tmp_path


def test_build_public_status_uses_canonical_inputs(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    status = build_public_status(repo)

    assert status["paper"]["equity"] == 93990.30
    assert status["paper"]["total_pnl_today"] == -14.0
    assert status["paper"]["realized_pnl_today"] is None
    assert status["ledger"]["closed_trades_total"] == 134
    assert status["gate"]["block_new_positions"] is True
    assert status["system"]["public_status"] == "halted"
    assert status["gate"]["verified_edge_available"] is False
    assert status["gate"]["scale_allowed"] is False
    assert status["gate"]["contradiction_detected"] is True
    assert status["gate"]["lifetime_edge_confirmed"] is False
    assert status["ledger"]["expectancy_per_trade"] == -20.5672


def test_write_and_check_public_surfaces(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    changed = write_public_surfaces(repo)

    assert changed["docs/data/public_status.json"] is True
    assert changed["wiki/Home.md"] is True
    assert changed["wiki/Progress-Dashboard.md"] is True
    assert "lifetime paired-trade ledger" in (
        repo / "wiki/Progress-Dashboard.md"
    ).read_text(encoding="utf-8").lower()
    assert check_public_surfaces(repo) == 0


def test_check_public_surfaces_fails_when_dashboard_drifted(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    write_public_surfaces(repo)
    (repo / "wiki/Home.md").write_text("stale", encoding="utf-8")
    assert check_public_surfaces(repo) == 1


def test_renderers_include_live_status(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    status = build_public_status(repo)

    home = render_home(status)
    progress = render_progress_dashboard(status)

    assert "Generated from canonical ledgers" in home
    assert "Paper equity" in progress


def test_build_public_status_falls_back_to_tracked_runtime_without_scorecard(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    (repo / "artifacts/daily_scorecard/latest_daily_scorecard.json").unlink()

    status = build_public_status(repo)

    assert status["generated_at_et"] == "2026-04-03T14:33:34+00:00"
    assert status["paper"]["equity"] == 93990.30
    assert status["paper"]["total_pnl_today"] == -14.0
    assert "tracked broker sync" in status["narrative"]["summary"]


def test_build_public_status_fails_closed_when_weekly_gate_and_lifetime_ledger_conflict(
    tmp_path: Path,
):
    repo = _seed_repo(tmp_path)
    state = json.loads((repo / "data/system_state.json").read_text(encoding="utf-8"))
    state["north_star_weekly_gate"].update(
        {
            "mode": "validation",
            "block_new_positions": False,
            "verified_edge_available": True,
            "reason": "Looks good this week.",
        }
    )
    (repo / "data/system_state.json").write_text(json.dumps(state), encoding="utf-8")

    status = build_public_status(repo)

    assert status["system"]["public_status"] == "halted"
    assert status["gate"]["block_new_positions"] is True
    assert status["gate"]["verified_edge_available"] is False
    assert status["gate"]["scale_allowed"] is False
    assert status["gate"]["contradiction_detected"] is True
    assert "lifetime paired-trade ledger" in status["gate"]["blocker_reason"].lower()


def test_build_public_status_cli_runs_from_repo_root(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_public_status.py"

    result = subprocess.run(
        [sys.executable, str(script), "--repo-root", str(repo)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "docs/data/public_status.json changed=True" in result.stdout
