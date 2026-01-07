#!/usr/bin/env python3
"""Sync today's trades to Vertex AI RAG for Dialogflow queries.

CEO Directive (Jan 6, 2026): "We are supposed to be recording every single
trade and every single lesson about each trade in our vertex rag database"

This script runs post-trade to ensure:
1. All trades are recorded in Vertex AI RAG corpus
2. Lessons can be queried via Dialogflow
3. ChromaDB backup is kept in sync

Usage:
    python3 scripts/sync_trades_to_rag.py
    python3 scripts/sync_trades_to_rag.py --date 2026-01-06
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_todays_trades(date_str: str | None = None) -> list[dict]:
    """Load trades from JSON file for given date."""
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    trades_file = Path(f"data/trades_{date_str}.json")
    if not trades_file.exists():
        logger.warning(f"No trades file found: {trades_file}")
        return []

    try:
        with open(trades_file) as f:
            trades = json.load(f)
        logger.info(f"Loaded {len(trades)} trades from {trades_file}")
        return trades
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error loading trades: {e}")
        return []


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
                doc_id = f"trade_{trade.get('symbol', 'UNK')}_{trade.get('timestamp', datetime.now().isoformat())}"

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


def sync_to_chromadb(trades: list[dict]) -> bool:
    """Sync trades to local ChromaDB for fast queries."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path="data/chromadb")
        collection = client.get_or_create_collection(
            name="trades",
            metadata={"description": "Trading history for RAG queries"},
        )

        synced = 0
        for trade in trades:
            try:
                doc_content = format_trade_document(trade)
                doc_id = f"trade_{trade.get('symbol', 'UNK')}_{trade.get('timestamp', datetime.now().isoformat())}"

                collection.upsert(
                    documents=[doc_content],
                    ids=[doc_id],
                    metadatas=[{
                        "type": "trade",
                        "symbol": str(trade.get("symbol", "")),
                        "date": str(trade.get("timestamp", ""))[:10],
                        "strategy": str(trade.get("strategy", "unknown")),
                        "pnl": str(trade.get("pnl", 0)),
                    }],
                )
                synced += 1
            except Exception as e:
                logger.error(f"ChromaDB upsert failed: {e}")

        logger.info(f"✅ Synced {synced}/{len(trades)} trades to ChromaDB")
        return synced > 0

    except ImportError:
        logger.warning("ChromaDB not available - skipping local sync")
        return False
    except Exception as e:
        logger.error(f"ChromaDB sync failed: {e}")
        return False


def format_trade_document(trade: dict) -> str:
    """Format a trade as a natural language document for RAG."""
    symbol = trade.get("symbol", "UNKNOWN")
    side = trade.get("side", "unknown")
    qty = trade.get("qty", 0)
    price = trade.get("price", 0)
    notional = trade.get("notional", 0)
    # Calculate price from notional if not provided
    if price == 0 and qty and notional:
        price = notional / qty
    strategy = trade.get("strategy", "unknown")
    # Handle multiple timestamp formats
    timestamp = trade.get("timestamp") or trade.get("time") or trade.get("date") or "unknown"
    pnl = trade.get("pnl")
    pnl_pct = trade.get("pnl_pct")

    # Extract date portion safely
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

    # Sync to both databases
    vertex_ok = sync_to_vertex_rag(trades)
    chroma_ok = sync_to_chromadb(trades)

    if vertex_ok or chroma_ok:
        logger.info("✅ RAG sync completed successfully")
        return 0
    else:
        logger.warning("⚠️ RAG sync partially failed - trades backed up in JSON")
        return 1


if __name__ == "__main__":
    sys.exit(main())
