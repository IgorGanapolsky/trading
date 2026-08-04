"""
RAG-Backed Safety Guard - Step 6 of Strategy Upgrade.
Uses historical lessons to provide a soft veto or warning on current trade parameters.

Active family is spy_put_credit (IC new entries killed). Queries must not default to
iron-condor playbooks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RAGSafetyGuard:
    """Consults the RAG corpus for similar past incidents before entry.

    Prefer defended retrieve_for_trade (FTS5 + hybrid + ACL + OOD). Soft warning only —
    hard risk rejection remains TradeGateway.
    """

    def __init__(self) -> None:
        self.last_source = "none"
        self.last_meta: dict[str, Any] = {}

    def check_safety(
        self,
        ticker: str,
        vix: float,
        iv: float,
        *,
        strategy_family: str = "spy_put_credit",
    ) -> dict[str, Any]:
        """
        Query RAG for similar volatility / risk regimes and return risk assessment.
        """
        t = (ticker or "SPY").upper()
        # Active validation family: put-credit; residual IC only for exit-only inventory context
        if strategy_family in {"iron_condor", "ic", "ic_simple"}:
            query = (
                f"{t} residual iron condor exit risk at VIX {vix:.1f} and IV {iv:.1%}. "
                "inventory hygiene stop loss orphan legs"
            )
        else:
            query = (
                f"{t} put credit spread risk at VIX {vix:.1f} and IV {iv:.1%}. "
                "stop loss inventory sizing kill switch"
            )
            strategy_family = "spy_put_credit"

        try:
            from src.rag.retrieve_for_trade import retrieve_for_trade

            defended = retrieve_for_trade(
                query,
                top_k=3,
                strategy_family=strategy_family,
                use_llm_rerank=False,
                parent_expand=True,
            )
            self.last_source = "defended"
            self.last_meta = dict(defended.meta or {})
            results = defended.lessons
        except Exception as primary_exc:
            logger.warning("Defended safety RAG failed (%s); falling back to pipeline", primary_exc)
            try:
                from src.rag.rag_pipeline import get_trading_rag_pipeline

                results = get_trading_rag_pipeline().query(query=query, top_k=3, rerank=True)
                self.last_source = "pipeline"
                self.last_meta = {"fallback_from": str(primary_exc)}
            except Exception as e:
                logger.error("RAG safety check failed: %s", e)
                return {
                    "veto": False,
                    "warning": False,
                    "reason": f"Safety check error: {e}",
                    "source": "error",
                }

        if not results:
            return {
                "veto": False,
                "warning": False,
                "reason": "No similar historical data found.",
                "source": self.last_source,
            }

        warnings: list[str] = []
        for doc in results:
            content = (doc.get("content_snippet", "") or doc.get("content", "") or "").upper()
            severity = str(doc.get("severity", "")).upper()
            if (
                "FAILURE" in content
                or "LOSS" in content
                or "CRITICAL" in content
                or severity in ("CRITICAL", "HIGH")
            ):
                warnings.append(str(doc.get("id", "Unknown Lesson")))

        if warnings:
            return {
                "veto": False,  # Soft veto (warning); hard block is TradeGateway
                "warning": True,
                "reason": f"Historical parallels found in lessons: {', '.join(warnings)}",
                "lessons": warnings,
                "source": self.last_source,
                "strategy_family": strategy_family,
                "path": self.last_meta.get("path"),
            }

        return {
            "veto": False,
            "warning": False,
            "reason": "No immediate historical red flags.",
            "source": self.last_source,
            "strategy_family": strategy_family,
        }
