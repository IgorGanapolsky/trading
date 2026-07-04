#!/usr/bin/env python3
"""Build the It Today Media contest submission packet from local repo evidence."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTEST_DIR = ROOT / "contest" / "itstoday-media"
PAGES_DIR = ROOT / "docs" / "contest" / "itstoday-media"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def build_project_proof() -> dict[str, Any]:
    state = load_json(ROOT / "data" / "system_state.json", {})
    trades = load_json(ROOT / "data" / "trades.json", {})
    params = load_json(ROOT / "data" / "strategy_params.json", {})

    paper = state.get("paper_account", {}) if isinstance(state, dict) else {}
    trade_stats = trades.get("stats", {}) if isinstance(trades, dict) else {}
    strategy_params = params.get("params", {}) if isinstance(params, dict) else {}

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_repo": "IgorGanapolsky/trading",
        "contest_positioning": (
            "The demo adapts this repo's strongest proven pattern: risk gates, audit trails, "
            "and stop-loss discipline. It does not claim the trading strategy is profitable."
        ),
        "trading_truth": {
            "paper_equity": paper.get("equity"),
            "paper_total_pl": paper.get("total_pl"),
            "paper_total_pl_pct": paper.get("total_pl_pct"),
            "positions_count": paper.get("positions_count"),
            "closed_trades": trade_stats.get("closed_trades"),
            "win_rate_pct": trade_stats.get("win_rate_pct"),
            "profit_factor": trade_stats.get("profit_factor"),
            "expectancy": trade_stats.get("expectancy"),
            "total_realized_pnl": trade_stats.get("total_realized_pnl"),
        },
        "strategy_guardrails": {
            "target_delta": strategy_params.get("target_delta"),
            "min_dte": strategy_params.get("min_dte"),
            "max_dte": strategy_params.get("max_dte"),
            "profit_target": strategy_params.get("profit_target"),
            "stop_loss": strategy_params.get("stop_loss"),
            "exit_dte": strategy_params.get("exit_dte"),
        },
        "demo_files": [
            "contest/itstoday-media/index.html",
            "contest/itstoday-media/src/profitGate.js",
            "contest/itstoday-media/src/profitGate.test.js",
            "contest/itstoday-media/README.md",
        ],
    }


def build_registration_answer() -> str:
    return """# Registration Answer

What AI marketing problem would you tackle, and why?

I would build Profit Gate: an AI media-buying decision agent that turns offer economics, tracking readiness, and channel fit into a launch/test/hold decision before spend goes live. Media buyers move fast, but bad tests burn budget when payout math, lead quality, tracking, or compliance are weak. Profit Gate imports the risk-control pattern from my autonomous trading project: calculate break-even CPC, cap test spend, declare stop-loss rules, generate channel-specific creative angles, and export an audit-ready brief. It helps a lean team kill bad campaigns earlier, scale strong ones faster, and keep every test tied to measurable economics.
"""


def main() -> None:
    data_dir = CONTEST_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    proof = build_project_proof()
    (data_dir / "trading_project_proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (CONTEST_DIR / "registration_answer.md").write_text(
        build_registration_answer(),
        encoding="utf-8",
    )

    if PAGES_DIR.exists():
        shutil.rmtree(PAGES_DIR)
    shutil.copytree(
        CONTEST_DIR,
        PAGES_DIR,
        ignore=shutil.ignore_patterns("README.md", "*.test.js"),
    )

    print(
        json.dumps(
            {
                "wrote": 2,
                "contest_dir": str(CONTEST_DIR),
                "pages_dir": str(PAGES_DIR),
                "pages_url_after_main_deploy": (
                    "https://igorganapolsky.github.io/trading/contest/itstoday-media/"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
