#!/usr/bin/env python3
"""
Automated Profit-Taking Script

Implements CTO/CFO Decision #5: Automated profit-taking rules
- Partial profit-taking: Sell 50% at +3% profit
- Trail stop: Move stop-loss to breakeven at +2%
- Full exit: Sell remaining at +5% or stop-loss
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"

# Profit-taking thresholds
PARTIAL_PROFIT_THRESHOLD = 0.03  # 3%
TRAIL_STOP_THRESHOLD = 0.02  # 2% (move stop to breakeven)
FULL_EXIT_THRESHOLD = 0.05  # 5%


def get_alpaca_client():
    """Get Alpaca API client."""
    try:
        from src.core.alpaca_trader import AlpacaTrader

        return AlpacaTrader(paper=True)
    except Exception as e:
        logger.error(f"Failed to initialize Alpaca client: {e}")
        return None


def load_system_state() -> dict:
    """Load system state."""
    if not SYSTEM_STATE_FILE.exists():
        logger.error("System state file not found")
        return {}

    with open(SYSTEM_STATE_FILE) as f:
        return json.load(f)


def get_open_positions() -> list[dict]:
    """Get open positions from system state."""
    state = load_system_state()
    return state.get("performance", {}).get("open_positions", [])


def calculate_profit_pct(entry_price: float, current_price: float) -> float:
    """Calculate profit percentage."""
    return (current_price - entry_price) / entry_price


def should_partial_profit(position: dict) -> bool:
    """Check if position should trigger partial profit-taking."""
    entry_price = position.get("entry_price", 0)
    current_price = position.get("current_price", 0)
    unrealized_pl_pct = position.get("unrealized_pl_pct", 0)

    if entry_price == 0 or current_price == 0:
        return False

    return unrealized_pl_pct >= PARTIAL_PROFIT_THRESHOLD


def should_trail_stop(position: dict) -> bool:
    """Check if position should trigger trailing stop to breakeven."""
    unrealized_pl_pct = position.get("unrealized_pl_pct", 0)
    return unrealized_pl_pct >= TRAIL_STOP_THRESHOLD


def should_full_exit(position: dict) -> bool:
    """Check if position should trigger full exit."""
    unrealized_pl_pct = position.get("unrealized_pl_pct", 0)
    return unrealized_pl_pct >= FULL_EXIT_THRESHOLD


def execute_partial_profit(position: dict, trader) -> bool:
    """Execute partial profit-taking (sell 50%)."""
    symbol = position.get("symbol")
    quantity = position.get("quantity", 0)
    current_price = position.get("current_price", 0)

    if quantity == 0 or current_price == 0:
        logger.warning(f"{symbol}: Invalid quantity or price")
        return False

    # Sell 50% of position
    sell_quantity = quantity * 0.5

    try:
        logger.info(f"{symbol}: Executing partial profit-taking")
        logger.info(f"  Selling: {sell_quantity:.6f} shares (50% of {quantity:.6f})")
        logger.info(f"  Current price: ${current_price:.2f}")
        logger.info(f"  Profit: {position.get('unrealized_pl_pct', 0) * 100:.2f}%")

        # Execute sell order
        result = trader.execute_order(
            symbol=symbol,
            amount_usd=sell_quantity * current_price,
            side="sell",
            tier="T1_CORE",
        )

        logger.info(f"✅ Partial profit-taking executed: {result.get('id', 'N/A')}")
        return True

    except Exception as e:
        logger.error(f"{symbol}: Failed to execute partial profit-taking: {e}")
        return False


def update_stop_loss(position: dict, trader) -> bool:
    """Update stop-loss to breakeven (trailing stop)."""
    symbol = position.get("symbol")
    quantity = position.get("quantity", 0)
    entry_price = position.get("entry_price", 0)

    if quantity == 0 or entry_price == 0:
        logger.warning(f"{symbol}: Invalid quantity or entry price")
        return False

    try:
        logger.info(f"{symbol}: Moving stop-loss to breakeven")
        logger.info(f"  Entry price: ${entry_price:.2f}")
        logger.info(f"  Stop-loss: ${entry_price:.2f} (breakeven)")

        # Set stop-loss at entry price (breakeven)
        trader.set_stop_loss(symbol=symbol, qty=quantity, stop_price=entry_price)

        logger.info("✅ Stop-loss updated to breakeven")
        return True

    except Exception as e:
        logger.error(f"{symbol}: Failed to update stop-loss: {e}")
        return False


def execute_full_exit(position: dict, trader) -> bool:
    """Execute full exit (sell 100%)."""
    symbol = position.get("symbol")
    quantity = position.get("quantity", 0)
    current_price = position.get("current_price", 0)

    if quantity == 0 or current_price == 0:
        logger.warning(f"{symbol}: Invalid quantity or price")
        return False

    try:
        logger.info(f"{symbol}: Executing full exit")
        logger.info(f"  Selling: {quantity:.6f} shares (100%)")
        logger.info(f"  Current price: ${current_price:.2f}")
        logger.info(f"  Profit: {position.get('unrealized_pl_pct', 0) * 100:.2f}%")

        # Execute sell order
        result = trader.execute_order(
            symbol=symbol,
            amount_usd=quantity * current_price,
            side="sell",
            tier="T1_CORE",
        )

        logger.info(f"✅ Full exit executed: {result.get('id', 'N/A')}")
        return True

    except Exception as e:
        logger.error(f"{symbol}: Failed to execute full exit: {e}")
        return False


def process_positions():
    """Process all positions for profit-taking."""
    print("=" * 80)
    print("💰 AUTOMATED PROFIT-TAKING")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    positions = get_open_positions()

    if not positions:
        print("\n✅ No open positions")
        return

    trader = get_alpaca_client()
    if not trader:
        print("\n❌ Failed to initialize Alpaca client")
        return

    print(f"\n📊 Analyzing {len(positions)} positions...")

    actions_taken = []

    for position in positions:
        symbol = position.get("symbol")
        unrealized_pl_pct = position.get("unrealized_pl_pct", 0)
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", 0)

        print(f"\n{symbol}:")
        print(f"  Entry: ${entry_price:.2f}")
        print(f"  Current: ${current_price:.2f}")
        print(f"  P/L: {unrealized_pl_pct * 100:.2f}%")

        # Check profit-taking rules
        if should_full_exit(position):
            print(f"  🎯 Action: FULL EXIT (≥{FULL_EXIT_THRESHOLD * 100:.0f}% profit)")
            if execute_full_exit(position, trader):
                actions_taken.append(f"{symbol}: Full exit executed")
        elif should_partial_profit(position):
            print(
                f"  🎯 Action: PARTIAL PROFIT-TAKING (≥{PARTIAL_PROFIT_THRESHOLD * 100:.0f}% profit)"
            )
            if execute_partial_profit(position, trader):
                actions_taken.append(f"{symbol}: Partial profit-taking executed")
        elif should_trail_stop(position):
            print(
                f"  🎯 Action: TRAIL STOP TO BREAKEVEN (≥{TRAIL_STOP_THRESHOLD * 100:.0f}% profit)"
            )
            if update_stop_loss(position, trader):
                actions_taken.append(f"{symbol}: Stop-loss trailed to breakeven")
        else:
            print(f"  ✅ No action needed (profit: {unrealized_pl_pct * 100:.2f}%)")

    print("\n" + "=" * 80)
    if actions_taken:
        print("✅ ACTIONS TAKEN:")
        for action in actions_taken:
            print(f"  • {action}")
    else:
        print("✅ No profit-taking actions needed")
    print("=" * 80)


if __name__ == "__main__":
    try:
        process_positions()
    except Exception:
        logger.exception("Profit-taking script failed")
        sys.exit(1)
