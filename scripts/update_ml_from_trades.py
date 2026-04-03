#!/usr/bin/env python3
"""
Update ML Models from Real Trade Data — Closes the Feedback Loop.

FIX Apr 3, 2026: The Thompson Sampler had stale priors (86/14 from
Tastytrade research) while real trades showed 24% win rate. Trade
outcomes in trade_trajectories.jsonl were never fed back to the model.

This script:
1. Reads canonical trades.json for real win/loss counts
2. Updates Thompson Sampler (trade_confidence_model.json) with empirical priors
3. Checks if win rate warrants trading (auto-blocks if < 50% over 30+ trades)
4. Generates post-mortem lessons from losing trades into RAG
5. Logs drift detection: model expected vs realized win rate

Run daily via cron or after sync_closed_positions.py.

Usage:
    python3 scripts/update_ml_from_trades.py
    python3 scripts/update_ml_from_trades.py --dry-run
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"
MODEL_FILE = PROJECT_ROOT / "models" / "ml" / "trade_confidence_model.json"
LESSONS_DIR = PROJECT_ROOT / "data" / "rag_knowledge" / "lessons_learned"
SYSTEM_STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"

# Thresholds
MIN_TRADES_FOR_GATE = 30
MIN_WIN_RATE_TO_TRADE = 50.0  # %
DRIFT_ALERT_THRESHOLD = 20.0  # % divergence between model and realized


def load_trades() -> dict:
    """Load canonical trades.json."""
    if not TRADES_FILE.exists():
        logger.error(f"Trades file not found: {TRADES_FILE}")
        return {"stats": {}, "trades": []}
    result: dict = json.loads(TRADES_FILE.read_text())
    return result


def load_model() -> dict:
    """Load current Thompson Sampler model."""
    if not MODEL_FILE.exists():
        return {
            "iron_condor": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "spy_specific": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "regime_adjustments": {"calm": 1.1, "trending": 0.9, "volatile": 0.8, "spike": 0.5},
        }
    result: dict = json.loads(MODEL_FILE.read_text())
    return result


def update_thompson_sampler(trades_data: dict, model: dict) -> dict:
    """Update Thompson Sampler with empirical win/loss from canonical ledger.

    Replaces stale Tastytrade priors with actual trade data.
    Uses alpha = wins + 1, beta = losses + 1 (Bayesian uniform prior).
    """
    stats = trades_data.get("stats", {})
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    total = stats.get("closed_trades", 0)
    win_rate = stats.get("win_rate_pct", 0)

    # Empirical priors: alpha = wins + 1, beta = losses + 1
    alpha = wins + 1
    beta_val = losses + 1

    old_alpha = model.get("iron_condor", {}).get("alpha", 0)
    old_beta = model.get("iron_condor", {}).get("beta", 0)
    old_expected = old_alpha / (old_alpha + old_beta) * 100 if (old_alpha + old_beta) > 0 else 0

    model["iron_condor"] = {
        "alpha": float(alpha),
        "beta": float(beta_val),
        "wins": wins,
        "losses": losses,
    }
    model["spy_specific"] = {
        "alpha": float(alpha),
        "beta": float(beta_val),
        "wins": wins,
        "losses": losses,
    }

    logger.info("=" * 60)
    logger.info("THOMPSON SAMPLER UPDATE")
    logger.info("=" * 60)
    logger.info(f"  Trades: {total} closed ({wins}W / {losses}L)")
    logger.info(f"  Win rate: {win_rate:.1f}%")
    logger.info(f"  Old priors: alpha={old_alpha}, beta={old_beta} (expected {old_expected:.1f}%)")
    logger.info(f"  New priors: alpha={alpha}, beta={beta_val} (expected {win_rate:.1f}%)")

    # Drift detection
    drift = abs(old_expected - win_rate)
    if drift > DRIFT_ALERT_THRESHOLD:
        logger.warning(f"  DRIFT ALERT: Model expected {old_expected:.1f}% but realized {win_rate:.1f}% ({drift:.1f}% drift)")

    logger.info("=" * 60)
    return model


def check_trading_gate(stats: dict) -> dict:
    """Check if trading should be allowed based on empirical performance."""
    total = stats.get("closed_trades", 0)
    win_rate = stats.get("win_rate_pct", 0)
    avg_win = stats.get("avg_win", 0) or 0
    avg_loss = stats.get("avg_loss", 0) or 0
    expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss) if total > 0 else 0

    gate = {
        "should_trade": total >= MIN_TRADES_FOR_GATE and win_rate >= MIN_WIN_RATE_TO_TRADE,
        "total_trades": total,
        "win_rate": win_rate,
        "expectancy_per_trade": round(expectancy, 2),
        "min_trades_met": total >= MIN_TRADES_FOR_GATE,
        "min_win_rate_met": win_rate >= MIN_WIN_RATE_TO_TRADE,
    }

    if not gate["should_trade"]:
        reasons = []
        if not gate["min_trades_met"]:
            reasons.append(f"Only {total}/{MIN_TRADES_FOR_GATE} trades")
        if not gate["min_win_rate_met"]:
            reasons.append(f"Win rate {win_rate:.1f}% < {MIN_WIN_RATE_TO_TRADE}%")
        gate["block_reason"] = "; ".join(reasons)
        logger.warning(f"  TRADING BLOCKED: {gate['block_reason']}")
    else:
        logger.info(f"  TRADING ALLOWED: {total} trades, {win_rate:.1f}% win rate, ${expectancy:.2f}/trade expectancy")

    return gate


def generate_loss_postmortems(trades_data: dict, max_lessons: int = 5) -> list[dict]:
    """Generate post-mortem lessons from the biggest losing trades.

    Only generates lessons for trades that don't already have one.
    """
    trades = trades_data.get("trades", [])
    losses = [t for t in trades if t.get("outcome") == "loss" and (t.get("realized_pnl", 0) or 0) < -20]
    losses.sort(key=lambda t: t.get("realized_pnl", 0) or 0)

    # Check existing lessons to avoid duplicates
    existing_ids = set()
    if LESSONS_DIR.exists():
        for f in LESSONS_DIR.glob("*.md"):
            existing_ids.add(f.stem)

    lessons = []
    for trade in losses[:max_lessons]:
        trade_id = trade.get("id", "unknown")
        lesson_id = f"postmortem_{trade_id[:40]}"
        if lesson_id in existing_ids:
            continue

        pnl = trade.get("realized_pnl", 0)
        entry = trade.get("entry_date", "unknown")
        exit_date = trade.get("exit_date", "unknown")
        entry_time = trade.get("entry_time", "")
        exit_time = trade.get("exit_time", "")
        signature = trade.get("signature", "unknown")

        # Calculate holding period
        holding = "unknown"
        if entry_time and exit_time:
            try:
                t1 = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                delta = t2 - t1
                hours = delta.total_seconds() / 3600
                holding = f"{hours:.1f}h" if hours < 24 else f"{delta.days}d"
            except (ValueError, TypeError):
                pass

        # Categorize root cause
        source = trade.get("source", "")
        if "ORPHAN" in source.upper() or "orphan" in str(trade.get("order_ids", {}).get("exit", [])):
            root_cause = "ORPHAN_CLEANUP: Position was incomplete/misgrouped and force-closed"
        elif holding != "unknown" and "h" in holding:
            h = float(holding.replace("h", ""))
            if h < 1:
                root_cause = f"PREMATURE_EXIT: Held only {holding} — no time for theta decay"
            elif h < 24:
                root_cause = f"EARLY_EXIT: Held {holding} — below 24h minimum"
            else:
                root_cause = f"MARKET_MOVE: Held {holding} — likely breached stop-loss"
        else:
            root_cause = "UNKNOWN: Insufficient data to determine root cause"

        lesson = {
            "id": lesson_id,
            "trade_id": trade_id,
            "pnl": pnl,
            "entry": entry,
            "exit": exit_date,
            "holding": holding,
            "signature": signature,
            "root_cause": root_cause,
        }
        lessons.append(lesson)

    return lessons


def write_postmortem_lessons(lessons: list[dict], dry_run: bool = False) -> int:
    """Write post-mortem lessons to RAG knowledge base."""
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    for lesson in lessons:
        filename = LESSONS_DIR / f"{lesson['id']}.md"
        if filename.exists():
            continue

        content = f"""# Post-Mortem: {lesson['signature']}

- **Trade ID**: {lesson['trade_id'][:60]}
- **P/L**: ${lesson['pnl']:.2f}
- **Entry**: {lesson['entry']}
- **Exit**: {lesson['exit']}
- **Holding Period**: {lesson['holding']}
- **Root Cause**: {lesson['root_cause']}

## Prevention

{_prevention_for_cause(lesson['root_cause'])}

## Generated

Auto-generated by `update_ml_from_trades.py` on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.
Severity: {"CRITICAL" if (lesson['pnl'] or 0) < -100 else "HIGH"}
"""
        if dry_run:
            logger.info(f"  [DRY RUN] Would write: {filename.name}")
        else:
            filename.write_text(content)
            logger.info(f"  Wrote lesson: {filename.name} (${lesson['pnl']:.2f})")
        written += 1

    return written


def _prevention_for_cause(root_cause: str) -> str:
    """Generate prevention recommendation based on root cause."""
    if "ORPHAN" in root_cause:
        return "Ensure all IC legs fill atomically via MLEG orders. 24h grace period before orphan cleanup."
    if "PREMATURE" in root_cause:
        return "Enforce 24h minimum holding period. Place GTC profit close order at entry."
    if "EARLY" in root_cause:
        return "Hold positions longer for theta decay. Minimum 24h hold enforced."
    if "MARKET_MOVE" in root_cause:
        return "Review stop-loss levels. Consider wider wings or lower delta for more cushion."
    return "Investigate trade logs for execution details."


def main(dry_run: bool = False):
    """Main feedback loop update."""
    logger.info("=" * 70)
    logger.info("ML FEEDBACK LOOP UPDATE")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)

    # 1. Load data
    trades_data = load_trades()
    model = load_model()
    stats = trades_data.get("stats", {})

    if not stats.get("closed_trades"):
        logger.warning("No closed trades found — nothing to update")
        return

    # 2. Update Thompson Sampler with real data
    model = update_thompson_sampler(trades_data, model)

    # 3. Check trading gate
    gate = check_trading_gate(stats)

    # 4. Generate post-mortem lessons
    lessons = generate_loss_postmortems(trades_data)
    logger.info(f"\nPost-mortem lessons to write: {len(lessons)}")

    # 5. Write everything
    if not dry_run:
        model["last_updated"] = datetime.now(timezone.utc).isoformat()
        model["feedback_source"] = "canonical_trades_json"
        model["gate"] = gate
        MODEL_FILE.write_text(json.dumps(model, indent=2))
        logger.info(f"Updated {MODEL_FILE}")

        # Enforce ML gate via trading halt file (hard gate)
        halt_file = PROJECT_ROOT / "data" / "TRADING_HALTED"
        if not gate["should_trade"]:
            halt_file.write_text(
                f"ML GATE BLOCKED: {gate.get('block_reason', 'unknown')}\n"
                f"Updated: {datetime.now(timezone.utc).isoformat()}\n"
                f"Win rate: {stats.get('win_rate_pct', 0):.1f}% | Trades: {stats.get('closed_trades', 0)}\n"
                f"Unblock: improve win rate above {MIN_WIN_RATE_TO_TRADE}% over {MIN_TRADES_FOR_GATE}+ trades"
            )
            logger.warning(f"  HALT FILE WRITTEN: {halt_file}")
        elif halt_file.exists():
            # Only remove halt if it was set by ML gate (not manual)
            content = halt_file.read_text()
            if "ML GATE BLOCKED" in content:
                halt_file.unlink()
                logger.info("  HALT FILE REMOVED: ML gate passed")

    written = write_postmortem_lessons(lessons, dry_run)
    logger.info(f"Post-mortem lessons written: {written}")

    # 6. Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info(f"  Thompson Sampler: alpha={model['iron_condor']['alpha']}, beta={model['iron_condor']['beta']}")
    logger.info(f"  Win rate: {stats.get('win_rate_pct', 0):.1f}%")
    logger.info(f"  Trading gate: {'OPEN' if gate['should_trade'] else 'BLOCKED'}")
    if not gate["should_trade"]:
        logger.info(f"  Block reason: {gate.get('block_reason', 'unknown')}")
    logger.info(f"  Post-mortems: {written} new lessons")
    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update ML models from trade data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
