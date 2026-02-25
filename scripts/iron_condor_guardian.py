#!/usr/bin/env python3
"""
Iron Condor Guardian - Enforces Phil Town Rule #1

MANDATORY EXITS:
1. Stop loss at 100% of credit received
2. Exit at 7 DTE (avoid gamma risk)
3. Take profit at 50% of max profit

This script should run every 30 minutes during market hours.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from src.core.trading_constants import IRON_CONDOR_STOP_LOSS_MULTIPLIER
from src.safety.mandatory_trade_gate import safe_submit_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
if not API_KEY or not SECRET_KEY:
    raise ValueError(
        "ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables are required. "
        "Never hardcode credentials."
    )
PAPER = True

# Phil Town Rule #1 Parameters
STOP_LOSS_MULTIPLIER = IRON_CONDOR_STOP_LOSS_MULTIPLIER
PROFIT_TAKE_PCT = 0.50  # 50% of max profit per CLAUDE.md exit rules
MIN_DTE = 7  # Exit at 7 DTE

# Track iron condor entry credits
IC_ENTRIES_FILE = Path(__file__).parent.parent / "data" / "ic_entries.json"
IC_TRADE_LOG = Path(__file__).parent.parent / "data" / "ic_trade_log.json"


def load_ic_entries() -> dict:
    """Load iron condor entry data."""
    if IC_ENTRIES_FILE.exists():
        with open(IC_ENTRIES_FILE) as f:
            return json.load(f)
    return {}


def save_ic_entries(entries: dict):
    """Save iron condor entry data."""
    IC_ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(IC_ENTRIES_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def get_dte(expiry_str: str) -> int:
    """Calculate days to expiration from OCC symbol."""
    # OCC format: SPY260220P00655000 -> expiry is 260220 (YYMMDD)
    expiry_part = expiry_str[3:9]  # Extract YYMMDD
    et = ZoneInfo("America/New_York")
    expiry_date = datetime.strptime(f"20{expiry_part}", "%Y%m%d").replace(tzinfo=et)
    today = datetime.now(et).replace(hour=0, minute=0, second=0, microsecond=0)
    return (expiry_date - today).days


def parse_ic_positions(positions) -> dict:
    """Group positions into iron condors by expiry."""
    ics = {}
    for pos in positions:
        symbol = pos.symbol
        if len(symbol) <= 10:  # Skip non-options
            continue

        # Extract expiry from OCC symbol
        expiry = symbol[3:9]  # YYMMDD

        if expiry not in ics:
            ics[expiry] = {"puts": [], "calls": [], "positions": []}

        qty = int(float(pos.qty))
        entry = float(pos.avg_entry_price)
        current = float(pos.current_price) if hasattr(pos, "current_price") else entry

        pos_data = {
            "symbol": symbol,
            "qty": qty,
            "entry": entry,
            "current": current,
            "type": "put" if "P" in symbol[9:10] else "call",
        }
        ics[expiry]["positions"].append(pos_data)

        if "P" in symbol[9:10]:
            ics[expiry]["puts"].append(pos_data)
        else:
            ics[expiry]["calls"].append(pos_data)

    return ics


def calculate_ic_pnl(ic_data: dict, entry_credit: float) -> tuple[float, float]:
    """Calculate current P/L for an iron condor.

    Returns: (current_value, pnl)
    """
    current_value = 0
    for pos in ic_data["positions"]:
        # Short positions: we received premium, now we'd pay to close
        # Long positions: we paid premium, now we'd receive to close
        if pos["qty"] < 0:  # Short
            current_value -= pos["current"] * abs(pos["qty"]) * 100
        else:  # Long
            current_value += pos["current"] * abs(pos["qty"]) * 100

    # P/L = entry_credit - current_value_to_close
    # If current_value is negative (costs to close), we profit
    pnl = entry_credit * 100 + current_value
    return current_value, pnl


def load_trade_log() -> dict:
    """Load or initialize the trade log."""
    if IC_TRADE_LOG.exists():
        with open(IC_TRADE_LOG) as f:
            return json.load(f)
    return {
        "trades": [],
        "stats": {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "avg_credit": 0,
            "avg_pnl": None,
            "total_pnl": 0,
        },
    }


def save_trade_log(trade_log: dict):
    """Save the trade log."""
    IC_TRADE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(IC_TRADE_LOG, "w") as f:
        json.dump(trade_log, f, indent=2)


def update_trade_log_on_exit(expiry: str, reason: str, pnl: float):
    """Log trade exit to RAG for full traceability."""
    import sys
    from datetime import timezone
    from pathlib import Path

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expiry_formatted = f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}"  # YYMMDD -> YYYY-MM-DD
    trade_id = f"trade_exit_{today}_{expiry}"

    outcome = "WIN" if pnl > 0 else "LOSS"

    lesson_content = f"""# Trade Exit: {today}

**Trade ID**: {trade_id}
**Date**: {today}
**Type**: Iron Condor Exit
**Outcome**: {outcome}
**Severity**: {"INFO" if pnl > 0 else "WARNING"}
**Category**: trade-exit

## Exit Details
- **Expiry**: {expiry_formatted}
- **Exit Reason**: {reason}
- **P/L**: ${pnl:+.2f}

## Phil Town Rule #1
{"✓ Capital protected - profitable exit" if pnl > 0 else "✓ Stop loss enforced - limited loss"}

## Guardian Rules Applied
- 50% profit target
- 100% stop loss
- 7 DTE exit
"""

    # Add to RAG
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        rag.add_lesson(trade_id, lesson_content)
        logger.info(f"Trade exit logged to RAG: {trade_id} - {outcome} ${pnl:+.2f}")
    except Exception as e:
        logger.error(f"Failed to log trade exit to RAG: {e}")


def close_iron_condor(client, ic_data: dict, reason: str, expiry: str, pnl: float):
    """Close all legs of an iron condor."""
    logger.warning(f"🚨 CLOSING IRON CONDOR: {reason}")

    for pos in ic_data["positions"]:
        side = OrderSide.BUY if pos["qty"] < 0 else OrderSide.SELL
        qty = abs(pos["qty"])

        try:
            order = safe_submit_order(
                client,
                MarketOrderRequest(
                    symbol=pos["symbol"],
                    qty=qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                ),
            )
            logger.info(f"  Closed {pos['symbol']}: {side.value} {qty} - {order.status}")
        except Exception as e:
            logger.error(f"  FAILED to close {pos['symbol']}: {e}")

    # Log the exit to trade log
    update_trade_log_on_exit(expiry, reason, pnl)


def run_guardian():
    """Main guardian loop - check all iron condors for exit conditions."""
    logger.info("=" * 60)
    logger.info("IRON CONDOR GUARDIAN - Phil Town Rule #1 Enforcement")
    logger.info("=" * 60)

    client = TradingClient(API_KEY, SECRET_KEY, paper=PAPER)
    positions = client.get_all_positions()

    if not positions:
        logger.info("No positions to guard.")
        return

    # Group into iron condors
    ics = parse_ic_positions(positions)
    entries = load_ic_entries()

    for expiry, ic_data in ics.items():
        logger.info(f"\nChecking IC expiry {expiry}:")

        # Calculate DTE
        sample_symbol = ic_data["positions"][0]["symbol"]
        dte = get_dte(sample_symbol)
        logger.info(f"  DTE: {dte}")

        # Get entry credit (or estimate from positions)
        entry_key = f"IC_{expiry}"
        if entry_key not in entries:
            # Estimate: sum of short premiums - sum of long premiums
            short_premium = sum(p["entry"] for p in ic_data["positions"] if p["qty"] < 0)
            long_premium = sum(p["entry"] for p in ic_data["positions"] if p["qty"] > 0)
            entry_credit = short_premium - long_premium
            entries[entry_key] = {
                "credit": entry_credit,
                "date": datetime.now().isoformat(),
            }
            save_ic_entries(entries)
            logger.info(f"  Estimated entry credit: ${entry_credit:.2f}")
        else:
            entry_credit = entries[entry_key]["credit"]
            logger.info(f"  Entry credit: ${entry_credit:.2f}")

        # Calculate current P/L
        current_value, pnl = calculate_ic_pnl(ic_data, entry_credit)
        max_profit = entry_credit * 100
        logger.info(f"  Current P/L: ${pnl:.2f} (max profit: ${max_profit:.2f})")

        # CHECK 1: DTE Exit (7 days)
        if dte <= MIN_DTE:
            close_iron_condor(client, ic_data, f"DTE={dte} <= {MIN_DTE} (gamma risk)", expiry, pnl)
            continue

        # CHECK 2: Stop Loss (100% of credit)
        stop_loss = entry_credit * STOP_LOSS_MULTIPLIER * 100
        if pnl < -stop_loss:
            close_iron_condor(
                client,
                ic_data,
                f"STOP LOSS: P/L ${pnl:.2f} < -${stop_loss:.2f}",
                expiry,
                pnl,
            )
            continue

        # CHECK 3: Profit Take (50% of max)
        profit_target = max_profit * PROFIT_TAKE_PCT
        if pnl >= profit_target:
            close_iron_condor(
                client,
                ic_data,
                f"PROFIT TARGET: P/L ${pnl:.2f} >= ${profit_target:.2f}",
                expiry,
                pnl,
            )
            continue

        logger.info(
            f"  ✅ No exit triggered. Stop: -${stop_loss:.2f}, Target: +${profit_target:.2f}"
        )

    logger.info("\n" + "=" * 60)
    logger.info("Guardian check complete.")


if __name__ == "__main__":
    run_guardian()
