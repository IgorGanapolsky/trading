from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/generate_profit_readiness_scorecard.py")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_scorecard_includes_expectancy_metrics_from_trades(tmp_path: Path) -> None:
    repo = tmp_path
    _write(
        repo / "data/system_state.json",
        {
            "paper_account": {
                "win_rate": 60.0,
                "win_rate_sample_size": 5,
                "starting_balance": 100000.0,
                "current_equity": 100100.0,
                "total_pl": 100.0,
            }
        },
    )
    _write(
        repo / "data/trades.json",
        {
            "trades": [
                {"outcome": "win", "realized_pnl": 120.0},
                {"outcome": "win", "realized_pnl": 30.0},
                {"outcome": "loss", "realized_pnl": -50.0},
            ]
        },
    )

    out = repo / "artifacts/devloop/profit_readiness_scorecard.md"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "--artifact-dir",
            str(repo / "artifacts/devloop"),
            "--out",
            str(out),
        ],
        check=True,
    )
    text = out.read_text(encoding="utf-8")

    assert "Profit Factor: 3.00 [PASS]" in text
    assert "Average Winner: $75.00 [PASS]" in text
    assert "Average Loser: $50.00 [PASS]" in text


def test_scorecard_expectancy_fallback_from_system_state(tmp_path: Path) -> None:
    repo = tmp_path
    _write(
        repo / "data/system_state.json",
        {
            "paper_account": {
                "win_rate": 100.0,
                "win_rate_sample_size": 1,
                "starting_balance": 100000.0,
                "current_equity": 100041.0,
                "total_pl": 41.0,
            },
            "strategy_milestones": {
                "strategy_families": {
                    "options_income": {
                        "metrics": {
                            "samples": 1,
                            "wins": 1,
                            "losses": 0,
                            "total_pnl": 41.0,
                        }
                    }
                }
            },
        },
    )

    out = repo / "artifacts/devloop/profit_readiness_scorecard.md"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "--artifact-dir",
            str(repo / "artifacts/devloop"),
            "--out",
            str(out),
        ],
        check=True,
    )
    text = out.read_text(encoding="utf-8")

    assert "Profit Factor: Inf [PASS]" in text
    assert "Average Winner: $41.00 [PASS]" in text
    assert "source=system_state.strategy_milestones" in text
