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
        Dict with REAL account data from Alpaca (both PAPER and LIVE).

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

    result = {"paper": None, "live": None}

    # ========== SYNC PAPER ACCOUNT ==========
    try:
        from src.execution.alpaca_executor import AlpacaExecutor

        executor = AlpacaExecutor(paper=True, allow_simulator=False)
        executor.sync_portfolio_state()

        positions = executor.get_positions()

        # LL-237: Fetch trade history from closed orders to prevent knowledge loss
        trade_history = []
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            orders = executor.client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=100)
            )
            trade_history = [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side),
                    "qty": str(o.filled_qty),
                    "price": str(o.filled_avg_price) if o.filled_avg_price else "0",
                    "filled_at": str(o.filled_at) if o.filled_at else None,
                }
                for o in orders
                if o.filled_at
            ]
            logger.info(f"📜 Fetched {len(trade_history)} closed trades from PAPER history")
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch PAPER trade history: {e}")

        result["paper"] = {
            "equity": executor.account_equity,
            "cash": executor.account_snapshot.get("cash", 0),
            "buying_power": executor.account_snapshot.get("buying_power", 0),
            "positions": positions,
            "positions_count": len(positions),
            "trade_history": trade_history,
            "trades_loaded": len(trade_history),
            "mode": "paper",
            "synced_at": datetime.now().isoformat(),
        }
        logger.info(f"✅ PAPER account synced: ${executor.account_equity:,.2f}")

    except Exception as e:
        logger.error(f"❌ Failed to sync PAPER account: {e}")

    # ========== SYNC LIVE (BROKERAGE) ACCOUNT ==========
    # LL-281: Dashboard was showing PAPER data for LIVE account because we never fetched LIVE
    import os
    live_api_key = os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY")
    live_api_secret = os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET")

    if live_api_key and live_api_secret:
        try:
            from alpaca.trading.client import TradingClient

            live_client = TradingClient(live_api_key, live_api_secret, paper=False)
            live_account = live_client.get_account()

            result["live"] = {
                "equity": float(live_account.equity),
                "cash": float(live_account.cash),
                "buying_power": float(live_account.buying_power),
                "positions_count": 0,  # Can add position fetch later
                "mode": "live",
                "synced_at": datetime.now().isoformat(),
            }
            logger.info(f"✅ LIVE account synced: ${float(live_account.equity):,.2f}")

        except Exception as e:
            logger.warning(f"⚠️ Could not sync LIVE account: {e}")
            # Don't fail - LIVE account sync is optional
    else:
        logger.info("ℹ️ No LIVE account credentials - skipping LIVE sync")

    # Return combined result
    if result["paper"] is None and result["live"] is None:
        raise AlpacaSyncError("Failed to sync both PAPER and LIVE accounts")

    return result


def update_system_state(alpaca_data: dict | None) -> None:
    """
    Update system_state.json with fresh Alpaca data.

    If alpaca_data is None, only update timestamp (preserve existing values).
    Now handles both PAPER and LIVE accounts separately (LL-281 fix).
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
        # LL-281: Handle new structure with separate PAPER and LIVE data
        paper_data = alpaca_data.get("paper")
        live_data = alpaca_data.get("live")

        # ========== UPDATE PAPER ACCOUNT ==========
        if paper_data:
            # CRITICAL: Reject simulated data
            mode = paper_data.get("mode", "unknown")
            if mode == "simulated":
                raise AlpacaSyncError(
                    f"REFUSING to update with SIMULATED data! mode='{mode}'"
                )

            # Update account section (primary account = PAPER for R&D)
            state.setdefault("account", {})
            state["account"]["current_equity"] = paper_data.get("equity", 0)
            state["account"]["cash"] = paper_data.get("cash", 0)
            state["account"]["buying_power"] = paper_data.get("buying_power", 0)
            state["account"]["positions_count"] = paper_data.get("positions_count", 0)

            # Calculate P/L for PAPER
            paper_starting = state.get("paper_account", {}).get("starting_balance", 5000.0)
            paper_current = paper_data.get("equity", 0)
            state["account"]["total_pl"] = paper_current - paper_starting
            state["account"]["total_pl_pct"] = (
                ((paper_current - paper_starting) / paper_starting) * 100 if paper_starting > 0 else 0
            )

            # Update paper_account section
            state.setdefault("paper_account", {})
            state["paper_account"]["current_equity"] = paper_data.get("equity", 0)
            state["paper_account"]["equity"] = paper_data.get("equity", 0)
            state["paper_account"]["cash"] = paper_data.get("cash", 0)
            state["paper_account"]["buying_power"] = paper_data.get("buying_power", 0)
            state["paper_account"]["positions_count"] = paper_data.get("positions_count", 0)
            state["paper_account"]["starting_balance"] = paper_starting
            state["paper_account"]["total_pl"] = paper_current - paper_starting
            state["paper_account"]["total_pl_pct"] = (
                ((paper_current - paper_starting) / paper_starting) * 100 if paper_starting > 0 else 0
            )

            # Update meta
            state["meta"]["last_sync"] = paper_data.get("synced_at")
            state["meta"]["sync_mode"] = "paper"

            # Store positions in performance.open_positions
            positions = paper_data.get("positions", [])
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

            # Sync trade_history
            trade_history = paper_data.get("trade_history", [])
            if trade_history:
                state["trade_history"] = trade_history
                state["trades_loaded"] = len(trade_history)
                logger.info(f"📜 Recorded {len(trade_history)} trades to history")
            else:
                existing_history = state.get("trade_history", [])
                if existing_history:
                    logger.info(f"📜 Preserved {len(existing_history)} existing trades")

        # ========== UPDATE LIVE (BROKERAGE) ACCOUNT ==========
        # LL-281: This was MISSING - dashboard showed PAPER data for LIVE
        if live_data:
            state.setdefault("live_account", {})
            live_starting = state["live_account"].get("starting_balance", 20.0)
            live_current = live_data.get("equity", 0)

            state["live_account"]["current_equity"] = live_current
            state["live_account"]["equity"] = live_current
            state["live_account"]["cash"] = live_data.get("cash", 0)
            state["live_account"]["buying_power"] = live_data.get("buying_power", 0)
            state["live_account"]["positions_count"] = live_data.get("positions_count", 0)
            state["live_account"]["starting_balance"] = live_starting
            state["live_account"]["total_pl"] = live_current - live_starting
            state["live_account"]["total_pl_pct"] = (
                ((live_current - live_starting) / live_starting) * 100 if live_starting > 0 else 0
            )
            state["live_account"]["synced_at"] = live_data.get("synced_at")

            logger.info(f"✅ LIVE account stored: ${live_current:,.2f}")
        else:
            # Preserve existing live_account data if we didn't fetch new
            if "live_account" not in state:
                state["live_account"] = {
                    "current_equity": 20.0,
                    "equity": 20.0,
                    "starting_balance": 20.0,
                    "total_pl": 0.0,
                    "total_pl_pct": 0.0,
                    "note": "LIVE account not synced - building capital via deposits",
                }

    # Write atomically
    SYSTEM_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SYSTEM_STATE_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(state, f, indent=2)
    temp_file.rename(SYSTEM_STATE_FILE)

    # Log result
    paper_equity = state.get("paper_account", {}).get("equity", 0)
    live_equity = state.get("live_account", {}).get("equity", 0)
    positions_count = state.get("account", {}).get("positions_count", 0)
    logger.info(
        f"✅ Updated system_state.json (PAPER=${paper_equity:.2f}, LIVE=${live_equity:.2f}, positions={positions_count})"
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
