#!/usr/bin/env python3
"""
Sync Trades FROM Alpaca - Create local trade files from broker activity.

Created: Jan 15, 2026
Purpose: Fix dashboard showing 0 trades when Dialogflow shows 9 trades.

ROOT CAUSE: Trading scripts execute on Alpaca but don't create local trade files.
The dashboard reads from local files which don't exist for today.
Dialogflow queries Alpaca directly and shows accurate data.

SOLUTION: This script fetches today's fills from Alpaca and creates
data/trades_{date}.json so the dashboard shows accurate trade counts.

Usage:
    python3 scripts/sync_trades_from_alpaca.py
    python3 scripts/sync_trades_from_alpaca.py --date 2026-01-15
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "data"


def get_alpaca_credentials() -> tuple[str, str]:
    """Get Alpaca API credentials from environment."""
    # Try paper trading credentials first (per CLAUDE.md priority)
    api_key = os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY", "")
    api_secret = os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET", "")

    if not api_key or not api_secret:
        # Fallback to standard names
        api_key = os.environ.get("ALPACA_API_KEY", "")
        api_secret = os.environ.get("ALPACA_SECRET_KEY", "")

    return api_key, api_secret


def fetch_todays_fills(date_str: str | None = None) -> list[dict]:
    """
    Fetch today's fill activities from Alpaca API.

    This is the same approach used by Dialogflow webhook (which shows accurate data).

    Args:
        date_str: Date in YYYY-MM-DD format, defaults to today (US Eastern)

    Returns:
        List of fill activities
    """
    api_key, api_secret = get_alpaca_credentials()

    if not api_key or not api_secret:
        logger.warning("No Alpaca credentials available")
        return []

    # Get date in US Eastern timezone
    if date_str is None:
        try:
            from zoneinfo import ZoneInfo

            date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except ImportError:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # Query Alpaca account activities for fills
        activities_url = (
            f"https://paper-api.alpaca.markets/v2/account/activities/FILL?date={date_str}"
        )
        req = urllib.request.Request(
            activities_url,
            headers={
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )
        ssl_context = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            activities = json.loads(response.read().decode("utf-8"))

        logger.info(f"Fetched {len(activities)} fills from Alpaca for {date_str}")
        return activities

    except Exception as e:
        logger.error(f"Failed to fetch fills from Alpaca: {e}")
        return []


def convert_fill_to_trade(fill: dict) -> dict:
    """
    Convert Alpaca fill activity to trade record format.

    This matches the format expected by dashboard and sync_trades_to_rag.py.
    """
    return {
        "symbol": fill.get("symbol", "UNKNOWN"),
        "side": fill.get("side", "buy"),
        "qty": float(fill.get("qty", 0)),
        "price": float(fill.get("price", 0)),
        "notional": float(fill.get("qty", 0)) * float(fill.get("price", 0)),
        "strategy": "alpaca_sync",  # Indicates this was synced from Alpaca
        "order_id": fill.get("order_id"),
        "activity_type": fill.get("activity_type", "FILL"),
        "timestamp": fill.get("transaction_time", datetime.now(timezone.utc).isoformat()),
        "source": "alpaca_api_sync",
    }


def save_trades_to_json(trades: list[dict], date_str: str) -> bool:
    """
    Save trades to local JSON file.

    Creates data/trades_{date}.json in the format expected by dashboard.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        trades_file = DATA_DIR / f"trades_{date_str}.json"

        # Load existing trades if file exists
        existing_trades = []
        if trades_file.exists():
            try:
                with open(trades_file) as f:
                    existing_trades = json.load(f)
                if not isinstance(existing_trades, list):
                    existing_trades = [existing_trades]
            except (json.JSONDecodeError, OSError):
                existing_trades = []

        # Get existing order IDs to avoid duplicates
        existing_order_ids = {t.get("order_id") for t in existing_trades if t.get("order_id")}

        # Add new trades (avoid duplicates)
        new_count = 0
        for trade in trades:
            order_id = trade.get("order_id")
            if order_id and order_id not in existing_order_ids:
                existing_trades.append(trade)
                existing_order_ids.add(order_id)
                new_count += 1
            elif not order_id:
                # No order_id - add anyway (might be manual or older format)
                existing_trades.append(trade)
                new_count += 1

        # Save
        with open(trades_file, "w") as f:
            json.dump(existing_trades, f, indent=2)

        logger.info(
            f"Saved {new_count} new trades to {trades_file} (total: {len(existing_trades)})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to save trades to JSON: {e}")
        return False


def update_system_state_trades(trade_count: int, date_str: str) -> bool:
    """
    Update system_state.json with trade count for dashboard.

    Ensures dashboard shows accurate trade count without requiring full sync.
    """
    try:
        state_file = DATA_DIR / "system_state.json"

        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
        else:
            state = {}

        # Update trades section
        state.setdefault("trades", {})
        state["trades"]["last_trade_date"] = date_str
        state["trades"]["today_trades"] = trade_count
        state["trades"]["total_trades_today"] = trade_count
        state["trades"]["last_trade_symbol"] = "SYNCED"  # Indicates synced from Alpaca

        # Update meta
        state.setdefault("meta", {})
        state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        state["meta"]["trade_sync"] = "alpaca_api"

        # Write atomically
        temp_file = state_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(state, f, indent=2)
        temp_file.rename(state_file)

        logger.info(f"Updated system_state.json: today_trades={trade_count}")
        return True

    except Exception as e:
        logger.error(f"Failed to update system_state.json: {e}")
        return False


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync trades from Alpaca to local files")
    parser.add_argument("--date", help="Date to sync (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SYNC TRADES FROM ALPACA")
    logger.info("=" * 60)

    # Get date
    if args.date:
        date_str = args.date
    else:
        try:
            from zoneinfo import ZoneInfo

            date_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except ImportError:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Syncing trades for: {date_str}")

    # Fetch fills from Alpaca
    fills = fetch_todays_fills(date_str)

    if not fills:
        logger.info("No fills found for today")
        # Still update system state to reflect 0 trades
        update_system_state_trades(0, date_str)
        return 0

    # Convert to trade format
    trades = [convert_fill_to_trade(fill) for fill in fills]

    # Save to local JSON
    json_ok = save_trades_to_json(trades, date_str)

    # Update system state
    state_ok = update_system_state_trades(len(trades), date_str)

    logger.info("=" * 60)
    if json_ok and state_ok:
        logger.info(f"✅ SYNC COMPLETE: {len(trades)} trades from Alpaca")
        logger.info(f"   Date: {date_str}")
        logger.info(f"   Trades file: data/trades_{date_str}.json")
        logger.info("   System state: updated")
    else:
        logger.warning("⚠️ SYNC PARTIAL - check logs")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
