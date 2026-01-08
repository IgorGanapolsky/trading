"""
Unified Trade Sync - Sync trades to LangSmith, Vertex AI RAG, and local JSON.

This module ensures EVERY trade is recorded to:
1. LangSmith (smith.langchain.com) - for observability and ML training
2. Vertex AI RAG - for Dialogflow queries and cloud backup
3. Local JSON files - for backup

Created: Jan 5, 2026 - Fix for operational gap where trades only went to JSON files.
Updated: Jan 8, 2026 - Removed ChromaDB (deprecated per CLAUDE.md Jan 7, 2026)
"""

import json
import logging
import os
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
    Unified trade sync to LangSmith, Vertex AI RAG, and local JSON.

    Every trade should go through this class to ensure proper tracking.
    """

    def __init__(self):
        self._langsmith_client = None
        self._init_langsmith()

        TRADES_DIR.mkdir(parents=True, exist_ok=True)

    def _init_langsmith(self):
        """Initialize LangSmith client."""
        api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
        if not api_key:
            logger.warning("LangSmith API key not set - trade sync to LangSmith disabled")
            return

        try:
            from langsmith import Client

            self._langsmith_client = Client(api_key=api_key)
            self._project_name = os.getenv("LANGCHAIN_PROJECT", "igor-trading-system")
            logger.info(f"LangSmith client initialized for project: {self._project_name}")
        except ImportError:
            logger.warning("langsmith package not installed")
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith: {e}")

    def sync_trade(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
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
            "langsmith": False,
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

        # 1. Sync to LangSmith
        results["langsmith"] = self._sync_to_langsmith(trade_data)

        # 2. Sync to Vertex AI RAG (for Dialogflow queries)
        results["vertex_rag"] = self._sync_to_vertex_rag(trade_data)

        # 3. Save to local JSON (backup)
        results["local_json"] = self._sync_to_local_json(trade_data)

        logger.info(
            f"Trade sync complete: {symbol} {side} | "
            f"LangSmith={results['langsmith']}, "
            f"VertexRAG={results['vertex_rag']}, JSON={results['local_json']}"
        )

        return results

    def _sync_to_langsmith(self, trade_data: dict[str, Any]) -> bool:
        """Sync trade to LangSmith as a run."""
        if not self._langsmith_client:
            return False

        try:
            import uuid

            run_name = f"trade_{trade_data['symbol']}_{trade_data['side']}"

            # Determine if this was a winning or losing trade
            pnl = trade_data.get("pnl", 0) or 0
            outcome = "win" if pnl > 0 else ("loss" if pnl < 0 else "neutral")

            self._langsmith_client.create_run(
                name=run_name,
                run_type="chain",
                inputs={
                    "symbol": trade_data["symbol"],
                    "side": trade_data["side"],
                    "qty": trade_data["qty"],
                    "strategy": trade_data["strategy"],
                },
                outputs={
                    "price": trade_data["price"],
                    "notional": trade_data["notional"],
                    "pnl": pnl,
                    "pnl_pct": trade_data.get("pnl_pct", 0),
                    "outcome": outcome,
                },
                extra={
                    "order_id": trade_data.get("order_id"),
                    "metadata": trade_data.get("metadata", {}),
                    "environment": os.getenv("ENVIRONMENT", "production"),
                },
                project_name=self._project_name,
                id=str(uuid.uuid4()),
                start_time=datetime.fromisoformat(trade_data["timestamp"].replace("Z", "+00:00")),
                end_time=datetime.now(timezone.utc),
                tags=["trade", outcome, trade_data["strategy"], trade_data["symbol"]],
            )

            logger.debug(f"Trade synced to LangSmith: {run_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync trade to LangSmith: {e}")
            return False

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

        This creates a lesson learned from the trade.
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

        # Create a lesson learned if significant
        if abs(pnl) > 10 or abs(pnl_pct) > 5:
            self._create_trade_lesson(
                symbol=symbol,
                strategy=strategy,
                pnl=pnl,
                pnl_pct=pnl_pct,
                entry_price=entry_price,
                exit_price=exit_price,
                holding_period_days=holding_period_days,
            )

        return results

    def _create_trade_lesson(
        self,
        symbol: str,
        strategy: str,
        pnl: float,
        pnl_pct: float,
        entry_price: float,
        exit_price: float,
        holding_period_days: int,
    ):
        """Create a lesson learned from a significant trade."""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            outcome = "WIN" if pnl > 0 else "LOSS"

            lesson_content = f"""# Trade Lesson: {symbol} {outcome} (${pnl:.2f})

## Trade Details
- **Symbol**: {symbol}
- **Strategy**: {strategy}
- **Entry Price**: ${entry_price:.2f}
- **Exit Price**: ${exit_price:.2f}
- **P/L**: ${pnl:.2f} ({pnl_pct:.2f}%)
- **Holding Period**: {holding_period_days} days
- **Date**: {today}

## Outcome
{"Profitable trade" if pnl > 0 else "Loss - review strategy"}

## Notes
Auto-generated lesson from trade sync system.
"""

            # Save locally
            lesson_id = f"trade_{symbol.lower()}_{today.replace('-', '')}"
            lesson_file = LESSONS_DIR / f"{lesson_id}.md"

            LESSONS_DIR.mkdir(parents=True, exist_ok=True)
            with open(lesson_file, "w") as f:
                f.write(lesson_content)

            logger.info(f"Created trade lesson: {lesson_file}")

            # Sync to Vertex AI RAG for Dialogflow queries
            try:
                vertex_rag = get_vertex_rag()
                if vertex_rag.is_initialized:
                    vertex_rag.add_lesson(
                        lesson_id=lesson_id,
                        title=f"Trade Lesson: {symbol} {outcome}",
                        content=lesson_content,
                        severity="HIGH" if abs(pnl) > 50 else "MEDIUM",
                        category="trade_lesson",
                    )
                    logger.info(f"Trade lesson synced to Vertex AI RAG: {lesson_id}")
            except Exception as vertex_err:
                logger.warning(f"Could not sync lesson to Vertex AI RAG: {vertex_err}")

        except Exception as e:
            logger.error(f"Failed to create trade lesson: {e}")

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 100) -> list[dict]:
        """
        Query trade history from local JSON files.

        For cloud queries, use Vertex AI RAG via Dialogflow.
        """
        trades = []
        try:
            # Get trades from recent JSON files
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
