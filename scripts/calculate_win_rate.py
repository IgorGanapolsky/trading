#!/usr/bin/env python3
"""Calculate and display win rate statistics from trades.json.

CEO Directive (Jan 14, 2026): Track every paper trade with win rate metrics.
Required per CLAUDE.md: win rate %, avg win, avg loss, profit factor.

Usage:
    python3 scripts/calculate_win_rate.py
    python3 scripts/calculate_win_rate.py --update  # Update stats in trades.json
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TRADES_FILE = Path("data/trades.json")


def load_trades() -> dict:
    """Load trades from master ledger."""
    if not TRADES_FILE.exists():
        logger.error(f"Trades file not found: {TRADES_FILE}")
        return {"trades": [], "stats": {}}

    with open(TRADES_FILE) as f:
        return json.load(f)


def calculate_stats(trades: list[dict]) -> dict:
    """Calculate win rate statistics from closed trades."""
    closed = [t for t in trades if t.get("status") == "closed"]
    open_trades = [t for t in trades if t.get("status") == "open"]

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
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def display_stats(stats: dict) -> None:
    """Display win rate statistics."""
    logger.info("=" * 50)
    logger.info("WIN RATE TRACKING - Per CLAUDE.md Mandate")
    logger.info("=" * 50)
    logger.info(f"Total Trades: {stats['total_trades']}")
    logger.info(f"  Open: {stats['open_trades']}")
    logger.info(f"  Closed: {stats['closed_trades']}")
    logger.info("")

    if stats["closed_trades"] == 0:
        logger.info("No closed trades yet - win rate cannot be calculated")
        logger.info("CLAUDE.md requires 30+ trades for statistical validity")
        return

    logger.info(f"Wins: {stats['wins']}")
    logger.info(f"Losses: {stats['losses']}")
    logger.info(f"Breakeven: {stats['breakeven']}")
    logger.info("")
    logger.info(f"Win Rate: {stats['win_rate_pct']}%")
    logger.info(f"Avg Win: ${stats['avg_win']}")
    logger.info(f"Avg Loss: ${stats['avg_loss']}")
    logger.info(f"Profit Factor: {stats['profit_factor']}")
    logger.info(f"Total P/L: ${stats['total_pnl']}")
    logger.info("")

    # CLAUDE.md decision point check
    if stats["closed_trades"] >= 30:
        if stats["win_rate_pct"] and stats["win_rate_pct"] < 60:
            logger.warning("⚠️  WIN RATE <60% - Per CLAUDE.md: Reassess strategy!")
        else:
            logger.info("✅ Win rate meets 60% threshold")
    else:
        remaining = 30 - stats["closed_trades"]
        logger.info(f"Need {remaining} more closed trades for statistical validity")


def update_trades_file(data: dict, stats: dict) -> None:
    """Update trades.json with new statistics."""
    data["stats"] = stats
    with open(TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"✅ Updated {TRADES_FILE}")


def close_trade(trade_id: str, exit_price: float, exit_date: str = None) -> bool:
    """Close a trade and calculate outcome.

    Usage:
        python3 -c "from scripts.calculate_win_rate import close_trade; close_trade('SOFI_STOCK_20260113', 28.50)"
    """
    data = load_trades()
    trades = data.get("trades", [])

    for trade in trades:
        if trade.get("id") == trade_id:
            if trade.get("status") == "closed":
                logger.warning(f"Trade {trade_id} already closed")
                return False

            entry_price = trade.get("entry_price", 0)
            qty = trade.get("qty", 1)
            side = trade.get("side", "buy")

            # Calculate P/L based on side
            if side == "buy":
                pnl = (exit_price - entry_price) * qty
            else:  # sell (short)
                pnl = (entry_price - exit_price) * qty

            # For options, multiply by 100 (contract size)
            if trade.get("type") == "option":
                pnl *= 100

            # Determine outcome
            if pnl > 0.01:
                outcome = "win"
            elif pnl < -0.01:
                outcome = "loss"
            else:
                outcome = "breakeven"

            # Update trade
            trade["status"] = "closed"
            trade["exit_price"] = exit_price
            trade["exit_date"] = exit_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trade["realized_pnl"] = round(pnl, 2)
            trade["unrealized_pnl"] = None
            trade["outcome"] = outcome

            # Recalculate stats
            stats = calculate_stats(trades)
            update_trades_file(data, stats)

            logger.info(f"✅ Closed {trade_id}: ${pnl:.2f} ({outcome})")
            return True

    logger.error(f"Trade {trade_id} not found")
    return False


def add_trade(
    trade_id: str,
    symbol: str,
    trade_type: str,
    side: str,
    qty: float,
    entry_price: float,
    strategy: str,
    entry_date: str = None,
    **kwargs,
) -> bool:
    """Add a new trade to the ledger.

    Args:
        trade_id: Unique identifier for the trade
        symbol: Ticker symbol (e.g., SOFI, SOFI260206P00024000)
        trade_type: 'stock' or 'option'
        side: 'buy' or 'sell'
        qty: Number of shares or contracts
        entry_price: Entry price per share/contract
        strategy: Strategy name (e.g., phil_town_csp, cash_secured_put)
        entry_date: Date of entry (defaults to today)
        **kwargs: Additional fields (strike, expiration, notes, etc.)
    """
    data = load_trades()
    trades = data.get("trades", [])

    # Check for duplicate
    if any(t.get("id") == trade_id for t in trades):
        logger.warning(f"Trade {trade_id} already exists")
        return False

    trade = {
        "id": trade_id,
        "symbol": symbol,
        "type": trade_type,
        "side": side,
        "qty": qty,
        "entry_date": entry_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "entry_price": entry_price,
        "exit_date": None,
        "exit_price": None,
        "current_price": entry_price,
        "status": "open",
        "unrealized_pnl": 0.0,
        "realized_pnl": None,
        "outcome": None,
        "strategy": strategy,
    }

    # Add optional fields
    for key, value in kwargs.items():
        if key not in trade:
            trade[key] = value

    trades.append(trade)
    stats = calculate_stats(trades)
    update_trades_file(data, stats)

    logger.info(f"✅ Added trade {trade_id}")
    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Calculate win rate statistics")
    parser.add_argument("--update", action="store_true", help="Update stats in trades.json")
    args = parser.parse_args()

    data = load_trades()
    trades = data.get("trades", [])
    stats = calculate_stats(trades)

    display_stats(stats)

    if args.update:
        update_trades_file(data, stats)

    return 0


if __name__ == "__main__":
    sys.exit(main())
