#!/usr/bin/env python3
"""Diagnose why the trading system is miserable — evidence from the ledger.

Writes:
  - data/runtime/system_diagnosis_latest.json
  - rag_knowledge/lessons_learned/system_misery_diagnosis_current.md

Usage:
  python3 scripts/diagnose_system_misery.py
  python3 scripts/diagnose_system_misery.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.loss_forensics import build_system_diagnosis, diagnosis_to_markdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"
SYSTEM_STATE = PROJECT_ROOT / "data" / "system_state.json"
KILL_SWITCH = PROJECT_ROOT / "data" / "runtime" / "strategy_kill_switch.json"
OUT_JSON = PROJECT_ROOT / "data" / "runtime" / "system_diagnosis_latest.json"
OUT_LESSON = (
    PROJECT_ROOT / "rag_knowledge" / "lessons_learned" / "system_misery_diagnosis_current.md"
)
INVENTORY_AUDIT = PROJECT_ROOT / "data" / "audit" / "open_inventory_latest.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main(dry_run: bool = False) -> int:
    trades_data = _load_json(TRADES_FILE)
    if not trades_data.get("trades") and not trades_data.get("stats"):
        logger.error("No trades ledger at %s", TRADES_FILE)
        return 1

    state = _load_json(SYSTEM_STATE)
    paper = state.get("paper_account") or state.get("account") or {}
    equity = paper.get("current_equity") or paper.get("equity")
    starting = paper.get("starting_balance")

    kill = _load_json(KILL_SWITCH)
    active_family = str(kill.get("active_family") or "spy_put_credit")

    unclean = None
    audit = _load_json(INVENTORY_AUDIT)
    if audit:
        unclean = not bool(audit.get("clean", audit.get("is_clean", True)))

    diagnosis = build_system_diagnosis(
        trades_data,
        equity=float(equity) if equity is not None else None,
        starting_equity=float(starting) if starting is not None else None,
        active_family=active_family,
        unclean_inventory=unclean,
    )
    md = diagnosis_to_markdown(diagnosis)

    logger.info("HEADLINE: %s", diagnosis["headline"])
    logger.info(
        "Ledger: n=%s WR=%s%% PF=%s exp=$%s total=$%s",
        diagnosis["ledger"]["closed_trades"],
        diagnosis["ledger"]["win_rate_pct"],
        diagnosis["ledger"]["profit_factor"],
        diagnosis["ledger"]["expectancy_per_trade"],
        diagnosis["ledger"]["total_realized_pnl"],
    )
    for cause in diagnosis.get("primary_root_causes", [])[:5]:
        logger.info("[%s] %s", cause.get("severity"), cause.get("title"))

    if dry_run:
        logger.info("[DRY RUN] Would write %s", OUT_JSON)
        logger.info("[DRY RUN] Would write %s", OUT_LESSON)
        print(json.dumps(diagnosis, indent=2)[:4000])
        return 0

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(diagnosis, indent=2) + "\n")
    OUT_LESSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_LESSON.write_text(md)
    logger.info("Wrote %s", OUT_JSON)
    logger.info("Wrote %s", OUT_LESSON)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(main(dry_run=args.dry_run))
