#!/usr/bin/env python3
"""Sync today's trades to Vertex AI RAG for Dialogflow queries.

CEO Directive (Jan 6, 2026): "We are supposed to be recording every single
trade and every single lesson about each trade in our vertex rag database"

This script runs post-trade to ensure:
1. All trades are recorded in Vertex AI RAG corpus
2. Lessons can be queried via Dialogflow
3. Local JSON backup is maintained (ChromaDB deprecated Jan 7, 2026)

Usage:
    python3 scripts/sync_trades_to_rag.py
    python3 scripts/sync_trades_to_rag.py --date 2026-01-06
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_todays_trades(date_str: str | None = None) -> list[dict]:
    """Load trades from ALL trade files for given date.

    FIX (Jan 12, 2026): Now looks for MULTIPLE file formats:
    - data/trades_YYYY-MM-DD.json (autonomous_trader, rule_one_trader)
    - data/options_trades_YYYYMMDD.json (execute_options_trade.py)

    ROOT CAUSE: execute_options_trade.py saves to options_trades_YYYYMMDD.json
    but this function only looked for trades_YYYY-MM-DD.json.
    Result: OPTIONS TRADES NEVER SYNCED TO RAG = no learning = same mistakes.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Also create YYYYMMDD format for options trades
    date_no_hyphens = date_str.replace("-", "")

    all_trades = []

    # Check all possible trade file formats
    trade_files = [
        Path(f"data/trades_{date_str}.json"),  # Standard format
        Path(f"data/options_trades_{date_no_hyphens}.json"),  # Options format (CRITICAL FIX!)
    ]

    for trades_file in trade_files:
        if trades_file.exists():
            try:
                with open(trades_file) as f:
                    data = json.load(f)

                # Handle both list and single trade formats
                if isinstance(data, list):
                    trades = data
                elif isinstance(data, dict):
                    trades = [data]
                else:
                    trades = []

                logger.info(f"✅ Loaded {len(trades)} trades from {trades_file}")
                all_trades.extend(trades)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error loading {trades_file}: {e}")

    if not all_trades:
        logger.warning(f"No trades found. Checked: {[str(f) for f in trade_files]}")

    return all_trades


def sync_to_vertex_rag(trades: list[dict]) -> bool:
    """Sync trades to Vertex AI RAG corpus."""
    try:
        from src.rag.vertex_rag import VertexRAG

        rag = VertexRAG()
        if not rag._initialized:
            logger.warning("Vertex AI RAG not initialized - check credentials")
            return False

        synced = 0
        for trade in trades:
            try:
                # Format trade as document for RAG
                doc_content = format_trade_document(trade)
                timestamp_val = trade.get("timestamp", datetime.now().isoformat())
                doc_id = f"trade_{trade.get('symbol', 'UNK')}_{timestamp_val}"

                # Add to RAG corpus
                rag.add_document(
                    content=doc_content,
                    metadata={
                        "type": "trade",
                        "symbol": trade.get("symbol"),
                        "date": trade.get("timestamp", "")[:10],
                        "strategy": trade.get("strategy", "unknown"),
                    },
                    doc_id=doc_id,
                )
                synced += 1
            except Exception as e:
                logger.error(f"Failed to sync trade: {e}")

        logger.info(f"✅ Synced {synced}/{len(trades)} trades to Vertex AI RAG")
        return synced > 0

    except ImportError:
        logger.warning("Vertex AI RAG not available - skipping cloud sync")
        return False
    except Exception as e:
        logger.error(f"Vertex AI sync failed: {e}")
        return False


def sync_to_local_json(trades: list[dict]) -> bool:
    """Backup trades to local JSON file.

    NOTE: ChromaDB was deprecated Jan 7, 2026 per CLAUDE.md.
    Local JSON is now the primary local backup mechanism.
    """
    try:
        backup_file = Path("data/trades_backup.json")

        # Load existing backups if present
        existing = []
        if backup_file.exists():
            try:
                with open(backup_file) as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = []

        # Add new trades
        synced = 0
        for trade in trades:
            # Create unique ID
            timestamp_val = trade.get("timestamp", datetime.now().isoformat())
            doc_id = f"trade_{trade.get('symbol', 'UNK')}_{timestamp_val}"

            # Check if already exists
            if not any(t.get("id") == doc_id for t in existing):
                trade_record = {
                    "id": doc_id,
                    "trade": trade,
                    "synced_at": datetime.now().isoformat(),
                }
                existing.append(trade_record)
                synced += 1

        # Save backup
        with open(backup_file, "w") as f:
            json.dump(existing, f, indent=2)

        logger.info(f"✅ Backed up {synced}/{len(trades)} trades to local JSON")
        return synced > 0

    except Exception as e:
        logger.error(f"Local JSON backup failed: {e}")
        return False


def format_trade_document(trade: dict) -> str:
    """Format a trade as a natural language document for RAG.

    FIX (Jan 12, 2026): Now handles OPTIONS trade format from execute_options_trade.py
    which has nested 'result' structure with premium, strike, expiry fields.
    """
    # Handle nested options trade format from execute_options_trade.py
    result = trade.get("result", {})
    if result and result.get("status"):
        # Options trade format
        symbol = trade.get("symbol", "UNKNOWN")
        strategy = trade.get("strategy", "cash_secured_put")
        timestamp = trade.get("timestamp", "unknown")
        status = result.get("status", "unknown")
        order_id = result.get("order_id", "unknown")
        premium = result.get("premium", 0)
        strike = result.get("strike", 0)
        expiry = result.get("expiry", "unknown")

        date_str = timestamp[:10] if len(str(timestamp)) >= 10 else str(timestamp)

        return f"""Options Trade Record: {symbol}
Date: {date_str}
Strategy: {strategy}
Status: {status}
Order ID: {order_id}
Strike: ${strike}
Expiry: {expiry}
Premium Collected: ${premium}
"""

    # Standard equity trade format
    symbol = trade.get("symbol", "UNKNOWN")
    side = trade.get("side", "unknown")
    qty = trade.get("qty", 0)
    price = trade.get("price", 0)
    notional = trade.get("notional", 0)
    if price == 0 and qty and notional:
        price = notional / qty
    strategy = trade.get("strategy", "unknown")
    timestamp = trade.get("timestamp") or trade.get("time") or trade.get("date") or "unknown"
    pnl = trade.get("pnl")
    pnl_pct = trade.get("pnl_pct")

    date_str = timestamp[:10] if len(str(timestamp)) >= 10 else str(timestamp)

    doc = f"""Trade Record: {symbol}
Date: {date_str}
Action: {side.upper()} {qty} shares at ${price:.2f}
Notional Value: ${notional:.2f}
Strategy: {strategy}
"""

    if pnl is not None:
        doc += f"P/L: ${pnl:.2f} ({pnl_pct:.2f}%)\n"

    return doc


def main():
    """Main entry point for RAG sync."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync trades to RAG databases")
    parser.add_argument("--date", help="Date to sync (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("POST-TRADE RAG SYNC")
    logger.info("=" * 60)

    # Load trades
    trades = load_todays_trades(args.date)
    if not trades:
        logger.info("No trades to sync")
        return 0

    # Sync to Vertex AI RAG (cloud) and local JSON backup
    vertex_ok = sync_to_vertex_rag(trades)
    local_ok = sync_to_local_json(trades)

    if vertex_ok or local_ok:
        logger.info("✅ RAG sync completed successfully")
        return 0
    else:
        logger.warning("⚠️ RAG sync failed - check logs")
        return 1


if __name__ == "__main__":
    sys.exit(main())
