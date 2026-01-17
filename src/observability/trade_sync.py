"""
Trade Sync - Sync trades to Vertex AI RAG and system_state.json.

ARCHITECTURE FIX Jan 17, 2026:
- BEFORE: Wrote to data/trades_{date}.json (caused Cloud Run mismatch)
- AFTER: Writes to data/system_state.json -> trade_history (single source of truth)

This module ensures EVERY trade is recorded to:
1. Vertex AI RAG - for Dialogflow queries and cloud backup
2. system_state.json - single source of truth, synced with Alpaca workflow

Data Flow (CANONICAL):
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  Alpaca API     │───>│ sync-system-state.yml│───>│system_state.json│
└─────────────────┘    └──────────────────────┘    │  └─trade_history │
                                                    └────────┬────────┘
┌─────────────────┐    ┌──────────────────────┐             │
│ Local Trades    │───>│   trade_sync.py      │─────────────┘
│ (manual/test)   │    │   (this module)      │
└─────────────────┘    └──────────────────────┘
                                │
                                v
                       ┌──────────────────────┐
                       │   Vertex AI RAG      │
                       └──────────────────────┘

Observability: Vertex AI RAG + system_state.json (Jan 17, 2026)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.rag.vertex_rag import get_vertex_rag

logger = logging.getLogger(__name__)

# Storage paths - SINGLE SOURCE OF TRUTH
DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
# DEPRECATED: trades_{date}.json files are no longer written
# Legacy files may still exist for historical data


class TradeSync:
    """
    Trade sync to Vertex AI RAG and system_state.json.

    ARCHITECTURE (Jan 17, 2026):
    - Writes to system_state.json -> trade_history (single source of truth)
    - Also syncs to Vertex AI RAG for semantic search
    - DEPRECATED: No longer writes to trades_{date}.json files
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def sync_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        strategy: str,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        order_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, bool]:
        """
        Sync a single trade to all systems.

        Returns dict with success status for each system.
        """
        results = {
            "vertex_rag": False,
            "system_state": False,
        }

        trade_data = {
            "id": order_id
            or f"local-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "symbol": symbol,
            "side": side,
            "qty": str(qty),
            "price": str(price),
            "notional": qty * price,
            "strategy": strategy,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "filled_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "source": "trade_sync.py",  # Track origin for debugging
        }

        # 1. Sync to Vertex AI RAG (for Dialogflow queries)
        results["vertex_rag"] = self._sync_to_vertex_rag(trade_data)

        # 2. Save to system_state.json -> trade_history (SINGLE SOURCE OF TRUTH)
        results["system_state"] = self._sync_to_system_state(trade_data)

        logger.info(
            f"Trade sync complete: {symbol} {side} | "
            f"VertexRAG={results['vertex_rag']}, SystemState={results['system_state']}"
        )

        return results

    def _sync_to_vertex_rag(self, trade_data: dict[str, Any]) -> bool:
        """Sync trade to Vertex AI RAG for Dialogflow queries."""
        try:
            vertex_rag = get_vertex_rag()
            if not vertex_rag.is_initialized:
                logger.debug("Vertex AI RAG not initialized - skipping")
                return False

            return vertex_rag.add_trade(
                symbol=trade_data["symbol"],
                side=trade_data["side"],
                qty=float(trade_data["qty"]),
                price=float(trade_data["price"]),
                strategy=trade_data["strategy"],
                pnl=trade_data.get("pnl"),
                pnl_pct=trade_data.get("pnl_pct"),
                timestamp=trade_data["filled_at"],
                metadata=trade_data.get("metadata"),
            )

        except Exception as e:
            logger.error(f"Failed to sync trade to Vertex AI RAG: {e}")
            return False

    def _sync_to_system_state(self, trade_data: dict[str, Any]) -> bool:
        """
        Save trade to system_state.json -> trade_history.

        This is the SINGLE SOURCE OF TRUTH for trade data.
        The Dialogflow webhook reads from this file (locally or via GitHub API).
        """
        try:
            # Load existing state
            state = {}
            if SYSTEM_STATE_FILE.exists():
                with open(SYSTEM_STATE_FILE) as f:
                    state = json.load(f)

            # Initialize trade_history if missing
            if "trade_history" not in state:
                state["trade_history"] = []

            # Add new trade at the beginning (most recent first)
            # Match Alpaca format for consistency
            trade_entry = {
                "id": trade_data["id"],
                "symbol": trade_data["symbol"],
                "side": trade_data["side"],
                "qty": trade_data["qty"],
                "price": trade_data["price"],
                "filled_at": trade_data["filled_at"],
            }
            state["trade_history"].insert(0, trade_entry)

            # Keep only last 100 trades to prevent unbounded growth
            state["trade_history"] = state["trade_history"][:100]

            # Update metadata
            state["last_updated"] = datetime.now(timezone.utc).isoformat() + "Z"
            state["trades_loaded"] = len(state["trade_history"])

            # Save
            with open(SYSTEM_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)

            logger.info(f"Trade saved to {SYSTEM_STATE_FILE} (trade_history)")
            return True

        except Exception as e:
            logger.error(f"Failed to save trade to system_state.json: {e}")
            return False

    def sync_trade_outcome(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        qty: float,
        side: str,
        strategy: str,
        holding_period_days: int = 0,
    ) -> dict[str, bool]:
        """
        Sync a completed trade with outcome (entry + exit).
        """
        # Calculate P/L
        if side.lower() == "buy":
            pnl = (exit_price - entry_price) * qty
        else:
            pnl = (entry_price - exit_price) * qty

        pnl_pct = (pnl / (entry_price * qty)) * 100 if entry_price > 0 else 0

        # Sync the exit trade
        results = self.sync_trade(
            symbol=symbol,
            side="sell" if side.lower() == "buy" else "buy",
            qty=qty,
            price=exit_price,
            strategy=strategy,
            pnl=pnl,
            pnl_pct=pnl_pct,
            metadata={
                "entry_price": entry_price,
                "exit_price": exit_price,
                "holding_period_days": holding_period_days,
                "trade_type": "close",
            },
        )

        return results

    def get_trade_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> list[dict]:
        """
        Query trade history from system_state.json (single source of truth).

        DEPRECATED: No longer reads from trades_*.json files.
        """
        trades = []
        try:
            if SYSTEM_STATE_FILE.exists():
                with open(SYSTEM_STATE_FILE) as f:
                    state = json.load(f)

                trade_history = state.get("trade_history", [])
                for trade in trade_history:
                    if symbol and trade.get("symbol") != symbol:
                        continue
                    trades.append(trade)
                    if len(trades) >= limit:
                        break

            return trades[:limit]

        except Exception as e:
            logger.error(f"Failed to query trade history: {e}")
            return []


# Singleton instance
_trade_sync: Optional[TradeSync] = None


def get_trade_sync() -> TradeSync:
    """Get singleton TradeSync instance."""
    global _trade_sync
    if _trade_sync is None:
        _trade_sync = TradeSync()
    return _trade_sync


def sync_trade(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    strategy: str,
    pnl: Optional[float] = None,
    **kwargs,
) -> dict[str, bool]:
    """Convenience function to sync a trade."""
    return get_trade_sync().sync_trade(
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        strategy=strategy,
        pnl=pnl,
        **kwargs,
    )
