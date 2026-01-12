#!/usr/bin/env python3
"""
Sync Alpaca State - Refresh local data from live broker.

Created: Dec 28, 2025
Purpose: Prevent stale data by syncing from Alpaca before trading.

This script:
1. Fetches current account state from Alpaca
2. Updates data/system_state.json with fresh data
3. Returns non-zero exit code on failure

Run automatically via:
- .github/workflows/pre-market-sync.yml (scheduled)
- Session start hook (on-demand)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SYSTEM_STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"


class AlpacaSyncError(Exception):
    """Raised when Alpaca sync fails - NEVER fall back to simulated data."""

    pass


def sync_from_alpaca() -> dict:
    """
    Sync account state from Alpaca.

    Returns:
        Dict with REAL account data from Alpaca.

    Raises:
        AlpacaSyncError: If API keys missing or connection fails.
                         NEVER returns simulated/fake data.
    """
    logger.info("🔄 Syncing from Alpaca...")

    # Check for API keys - FAIL LOUDLY if missing
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, api_secret = get_alpaca_credentials()

    if not api_key or not api_secret:
        logger.warning("⚠️ No Alpaca API keys found - preserving existing data")
        # DO NOT overwrite real data with simulated values!
        # Return None to signal that we should only update timestamp, not values
        return None

    try:
        from src.execution.alpaca_executor import AlpacaExecutor

        executor = AlpacaExecutor(paper=True, allow_simulator=False)
        executor.sync_portfolio_state()

        positions = executor.get_positions()

        return {
            "equity": executor.account_equity,
            "cash": executor.account_snapshot.get("cash", 0),
            "buying_power": executor.account_snapshot.get("buying_power", 0),
            "positions": positions,
            "positions_count": len(positions),
            "mode": "paper" if executor.paper else "live",
            "synced_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Failed to sync from Alpaca: {e}")
        raise


def update_system_state(alpaca_data: dict | None) -> None:
    """
    Update system_state.json with fresh Alpaca data.

    If alpaca_data is None, only update timestamp (preserve existing values).
    """
    logger.info("📝 Updating system_state.json...")

    # Load existing state
    if SYSTEM_STATE_FILE.exists():
        with open(SYSTEM_STATE_FILE) as f:
            state = json.load(f)
    else:
        state = {}

    # Update meta timestamp regardless
    state.setdefault("meta", {})
    state["meta"]["last_updated"] = datetime.now().isoformat()

    if alpaca_data is None:
        # No API keys - only update timestamp, preserve existing data
        state["meta"]["last_sync"] = datetime.now().isoformat()
        state["meta"]["sync_mode"] = "skipped_no_keys"
        logger.info("⚠️ No API keys - preserving existing account values, only updating timestamp")
    else:
        # CRITICAL: Reject simulated data - this would overwrite real data with garbage
        mode = alpaca_data.get("mode", "unknown")
        if mode == "simulated":
            raise AlpacaSyncError(
                f"REFUSING to update system_state.json with SIMULATED data!\n"
                f"  Received mode='{mode}'\n"
                f"  This would overwrite real portfolio data with lies.\n"
                f"  Fix the Alpaca connection first."
            )

        # Full sync - update account section
        state.setdefault("account", {})
        state["account"]["current_equity"] = alpaca_data.get("equity", 0)
        state["account"]["cash"] = alpaca_data.get("cash", 0)
        state["account"]["buying_power"] = alpaca_data.get("buying_power", 0)
        state["account"]["positions_value"] = alpaca_data.get("equity", 0) - alpaca_data.get(
            "cash", 0
        )

        # Calculate P/L if starting balance exists
        starting = state["account"].get("starting_balance", 100000.0)
        current = alpaca_data.get("equity", 0)
        state["account"]["total_pl"] = current - starting
        state["account"]["total_pl_pct"] = (
            ((current - starting) / starting) * 100 if starting > 0 else 0
        )

        # Update meta
        state["meta"]["last_sync"] = alpaca_data.get("synced_at")
        state["meta"]["sync_mode"] = alpaca_data.get("mode", "unknown")

        # Store positions count
        state["account"]["positions_count"] = alpaca_data.get("positions_count", 0)

        # CRITICAL: Store actual positions in performance.open_positions
        # This is what the blog and verify_positions.py use to display positions
        positions = alpaca_data.get("positions", [])
        state.setdefault("performance", {})
        state["performance"]["open_positions"] = [
            {
                "symbol": p.get("symbol"),
                "quantity": p.get("qty") or p.get("quantity", 0),
                "entry_price": p.get("avg_entry_price", 0),
                "current_price": p.get("current_price", 0),
                "market_value": p.get("market_value", 0),
                "unrealized_pl": p.get("unrealized_pl", 0),
                "unrealized_pl_pct": p.get("unrealized_plpc", 0),
                "side": p.get("side", "long"),
            }
            for p in positions
            if p.get("symbol")
        ]

    # Write atomically
    SYSTEM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SYSTEM_STATE_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=2)
    temp_file.rename(SYSTEM_STATE_FILE)

    # Log result
    current_equity = state.get("account", {}).get("current_equity", 0)
    positions_count = state.get("account", {}).get("positions_count", 0)
    logger.info(
        f"✅ Updated system_state.json (equity=${current_equity:.2f}, positions={positions_count})"
    )


def main() -> int:
    """
    Main entry point.

    Returns:
        0 on success, 1 on failure
    """
    logger.info("=" * 60)
    logger.info("ALPACA STATE SYNC")
    logger.info("=" * 60)

    try:
        # Sync from Alpaca
        alpaca_data = sync_from_alpaca()

        # Update local state
        update_system_state(alpaca_data)

        logger.info("=" * 60)
        if alpaca_data is None:
            logger.info("⚠️ SYNC SKIPPED - No API keys")
            logger.info("   Existing data preserved, timestamp updated")
        else:
            logger.info("✅ SYNC COMPLETE")
            logger.info(f"   Equity: ${alpaca_data.get('equity', 0):,.2f}")
            logger.info(f"   Positions: {alpaca_data.get('positions_count', 0)}")
            logger.info(f"   Mode: {alpaca_data.get('mode', 'unknown')}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ SYNC FAILED: {e}")
        logger.error("   Trading should be BLOCKED until this is resolved.")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
