"""
Trade Sync - Sync trades to Vertex AI RAG and local JSON.

This module ensures EVERY trade is recorded to:
1. Vertex AI RAG - for Dialogflow queries and cloud backup
2. Local JSON files - for backup

Simplified: Jan 9, 2026 - Removed LangSmith (not essential for trading).
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.rag.vertex_rag import get_vertex_rag

logger = logging.getLogger(__name__)

# Storage paths
DATA_DIR = Path("data")
TRADES_DIR = DATA_DIR / "trades"
LESSONS_DIR = Path("rag_knowledge/lessons_learned")


class TradeSync:
    """
    Trade sync to Vertex AI RAG and local JSON.

    Every trade should go through this class to ensure proper tracking.
    """

    def __init__(self):
        TRADES_DIR.mkdir(parents=True, exist_ok=True)

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
            "local_json": False,
        }

        trade_data = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "notional": qty * price,
            "strategy": strategy,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "order_id": order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        # 1. Sync to Vertex AI RAG (for Dialogflow queries)
        results["vertex_rag"] = self._sync_to_vertex_rag(trade_data)

        # 2. Save to local JSON (backup)
        results["local_json"] = self._sync_to_local_json(trade_data)

        logger.info(
            f"Trade sync complete: {symbol} {side} | "
            f"VertexRAG={results['vertex_rag']}, JSON={results['local_json']}"
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
                qty=trade_data["qty"],
                price=trade_data["price"],
                strategy=trade_data["strategy"],
                pnl=trade_data.get("pnl"),
                pnl_pct=trade_data.get("pnl_pct"),
                timestamp=trade_data["timestamp"],
                metadata=trade_data.get("metadata"),
            )

        except Exception as e:
            logger.error(f"Failed to sync trade to Vertex AI RAG: {e}")
            return False

    def _sync_to_local_json(self, trade_data: dict[str, Any]) -> bool:
        """Save trade to local JSON file (backup)."""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trades_file = DATA_DIR / f"trades_{today}.json"

            # Load existing trades
            trades = []
            if trades_file.exists():
                with open(trades_file) as f:
                    trades = json.load(f)

            # Add new trade
            trades.append(trade_data)

            # Save
            with open(trades_file, "w") as f:
                json.dump(trades, f, indent=2)

            logger.debug(f"Trade saved to {trades_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save trade to JSON: {e}")
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

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Query trade history from local JSON files."""
        trades = []
        try:
            for trades_file in sorted(DATA_DIR.glob("trades_*.json"), reverse=True):
                if len(trades) >= limit:
                    break

                with open(trades_file) as f:
                    file_trades = json.load(f)
                    for trade in file_trades:
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
