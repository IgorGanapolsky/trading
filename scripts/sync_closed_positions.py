#!/usr/bin/env python3
"""
Sync Closed Positions - Auto-detect and record closed trades for win rate tracking.

CEO Directive: "I want our system to be self-healing"

BUG FOUND (Jan 18, 2026): Win rate showed 0% because:
1. Trades executed on Alpaca but never recorded in trades.json
2. No automatic detection of closed positions (matching BUY + SELL)
3. trades.json only had 3 manually added entries that were never closed

This script:
1. Reads trade history from system_state.json (synced from Alpaca)
2. Identifies closed positions (matching BUY + SELL pairs)
3. Calculates P/L for each closed position
4. Updates trades.json with closed trades and win rate stats

Usage:
    python3 scripts/sync_closed_positions.py
    python3 scripts/sync_closed_positions.py --dry-run  # Preview without saving
"""

import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
TRADES_FILE = DATA_DIR / "trades.json"


def load_system_state() -> dict:
    """Load system state with trade history from Alpaca."""
    if not SYSTEM_STATE_FILE.exists():
        logger.error(f"System state file not found: {SYSTEM_STATE_FILE}")
        return {}
    with open(SYSTEM_STATE_FILE) as f:
        return json.load(f)


def load_trades_ledger() -> dict:
    """Load the master trades ledger."""
    if not TRADES_FILE.exists():
        return {
            "meta": {
                "version": "1.0",
                "created": datetime.now(timezone.utc).isoformat(),
                "purpose": "Master ledger for win rate tracking per CLAUDE.md",
            },
            "stats": {},
            "trades": [],
        }
    with open(TRADES_FILE) as f:
        return json.load(f)


def identify_closed_positions(trade_history: list[dict]) -> list[dict]:
    """
    Identify closed positions from trade history.

    A position is closed when there's matching BUY and SELL activity.
    """
    # Group trades by symbol
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for t in trade_history:
        sym = t.get("symbol")
        if sym and sym != "None":  # Skip null symbols
            by_symbol[sym].append(t)

    closed_positions = []

    for symbol, trades in by_symbol.items():
        buys = [t for t in trades if "BUY" in str(t.get("side", ""))]
        sells = [t for t in trades if "SELL" in str(t.get("side", ""))]

        if not buys or not sells:
            continue  # Not a closed position

        # Calculate totals
        buy_qty = sum(float(t.get("qty", 0)) for t in buys)
        sell_qty = sum(float(t.get("qty", 0)) for t in sells)
        total_buy = sum(float(t.get("qty", 0)) * float(t.get("price", 0)) for t in buys)
        total_sell = sum(float(t.get("qty", 0)) * float(t.get("price", 0)) for t in sells)

        # Determine if this is an options contract (longer symbol = option)
        is_option = len(symbol) > 10
        multiplier = 100 if is_option else 1

        # Determine position type from first trade
        first_trade = min(trades, key=lambda x: x.get("filled_at", "9999"))
        first_side = str(first_trade.get("side", ""))
        is_short_first = "SELL" in first_side

        # Calculate P/L
        # For options: (sell price - buy price) * 100
        raw_pl = total_sell - total_buy
        pl = raw_pl * multiplier

        # Determine outcome
        if pl > 0.01:
            outcome = "win"
        elif pl < -0.01:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # Get dates
        entry_date = min(t.get("filled_at", "")[:10] for t in trades if t.get("filled_at"))
        exit_date = max(t.get("filled_at", "")[:10] for t in trades if t.get("filled_at"))

        closed_positions.append(
            {
                "id": f"closed_{symbol}_{entry_date.replace('-', '')}",
                "symbol": symbol,
                "type": "option" if is_option else "stock",
                "side": "short" if is_short_first else "long",
                "qty": min(buy_qty, sell_qty),  # Closed quantity
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_cost": total_buy,
                "exit_proceeds": total_sell,
                "status": "closed",
                "realized_pnl": round(pl, 2),
                "outcome": outcome,
                "multiplier": multiplier,
                "strategy": "alpaca_synced",
                "trades": {
                    "buys": len(buys),
                    "sells": len(sells),
                    "buy_qty": buy_qty,
                    "sell_qty": sell_qty,
                },
            }
        )

    return closed_positions


def calculate_stats(trades: list[dict], paper_phase_start: str | None = None) -> dict:
    """Calculate win rate statistics from closed trades."""
    closed = [t for t in trades if t.get("status") == "closed"]
    open_trades = [t for t in trades if t.get("status") == "open"]

    # Calculate paper phase days
    paper_phase_days = 0
    if paper_phase_start:
        try:
            start_date = datetime.fromisoformat(paper_phase_start).date()
            paper_phase_days = (datetime.now(timezone.utc).date() - start_date).days
        except (ValueError, TypeError):
            pass

    if not closed:
        return {
            "total_trades": len(trades),
            "closed_trades": 0,
            "open_trades": len(open_trades),
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate_pct": None,
            "avg_win": None,
            "avg_loss": None,
            "profit_factor": None,
            "total_pnl": 0.0,
            "paper_phase_start": paper_phase_start,
            "paper_phase_days": paper_phase_days,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    wins = [t for t in closed if t.get("outcome") == "win"]
    losses = [t for t in closed if t.get("outcome") == "loss"]
    breakeven = [t for t in closed if t.get("outcome") == "breakeven"]

    win_amounts = [t.get("realized_pnl", 0) for t in wins if t.get("realized_pnl")]
    loss_amounts = [abs(t.get("realized_pnl", 0)) for t in losses if t.get("realized_pnl")]

    total_wins = sum(win_amounts) if win_amounts else 0
    total_losses = sum(loss_amounts) if loss_amounts else 0

    return {
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_win": round(total_wins / len(wins), 2) if wins else None,
        "avg_loss": round(total_losses / len(losses), 2) if losses else None,
        "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else None,
        "total_pnl": round(total_wins - total_losses, 2),
        "paper_phase_start": paper_phase_start,
        "paper_phase_days": paper_phase_days,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def sync_closed_positions(dry_run: bool = False) -> dict:
    """
    Main sync function - identify closed positions and update trades.json.

    Returns:
        dict with sync results
    """
    logger.info("=" * 60)
    logger.info("SYNC CLOSED POSITIONS - Auto Win Rate Calculation")
    logger.info("=" * 60)

    # Load data
    system_state = load_system_state()
    trade_history = system_state.get("trade_history", [])

    if not trade_history:
        logger.warning("No trade history found in system_state.json")
        return {"success": False, "error": "No trade history"}

    logger.info(f"Found {len(trade_history)} trades in history")

    # Identify closed positions
    closed_positions = identify_closed_positions(trade_history)
    logger.info(f"Identified {len(closed_positions)} closed positions")

    if not closed_positions:
        logger.info("No closed positions found")
        return {"success": True, "closed_count": 0}

    # Print summary
    wins = sum(1 for p in closed_positions if p["outcome"] == "win")
    losses = sum(1 for p in closed_positions if p["outcome"] == "loss")
    total_pnl = sum(p["realized_pnl"] for p in closed_positions)

    logger.info("")
    logger.info("=== CLOSED POSITIONS ===")
    for pos in closed_positions:
        outcome_emoji = (
            "✅" if pos["outcome"] == "win" else "❌" if pos["outcome"] == "loss" else "➖"
        )
        logger.info(
            f"  {outcome_emoji} {pos['symbol']}: ${pos['realized_pnl']:+.2f} ({pos['outcome']})"
        )

    logger.info("")
    logger.info("=== SUMMARY ===")
    logger.info(f"  Closed positions: {len(closed_positions)}")
    logger.info(f"  Wins: {wins}, Losses: {losses}")
    logger.info(f"  Total P/L: ${total_pnl:.2f}")
    if closed_positions:
        logger.info(f"  Win Rate: {wins / len(closed_positions) * 100:.1f}%")

    if dry_run:
        logger.info("")
        logger.info("DRY RUN - No changes saved")
        return {
            "success": True,
            "dry_run": True,
            "closed_count": len(closed_positions),
            "wins": wins,
            "losses": losses,
            "total_pnl": total_pnl,
        }

    # Load existing trades ledger
    ledger = load_trades_ledger()
    existing_ids = {t.get("id") for t in ledger.get("trades", [])}

    # Add closed positions (avoid duplicates)
    new_count = 0
    for pos in closed_positions:
        if pos["id"] not in existing_ids:
            ledger.setdefault("trades", []).append(pos)
            new_count += 1

    # Calculate stats
    paper_phase_start = ledger.get("meta", {}).get("paper_phase_start") or ledger.get(
        "stats", {}
    ).get("paper_phase_start", "2026-01-15")
    stats = calculate_stats(ledger.get("trades", []), paper_phase_start)
    ledger["stats"] = stats

    # Update metadata
    ledger.setdefault("meta", {})
    ledger["meta"]["last_sync"] = datetime.now(timezone.utc).isoformat()
    ledger["meta"]["sync_source"] = "sync_closed_positions.py"

    # Save
    with open(TRADES_FILE, "w") as f:
        json.dump(ledger, f, indent=2)

    logger.info("")
    logger.info(f"✅ Saved {new_count} new closed positions to {TRADES_FILE}")
    logger.info(f"   Total trades in ledger: {len(ledger.get('trades', []))}")
    logger.info(f"   Win Rate: {stats.get('win_rate_pct', 'N/A')}%")

    return {
        "success": True,
        "new_count": new_count,
        "total_trades": len(ledger.get("trades", [])),
        "stats": stats,
    }


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync closed positions for win rate tracking")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    result = sync_closed_positions(dry_run=args.dry_run)

    if result.get("success"):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
