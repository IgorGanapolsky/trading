"""
High-level integration utilities for orchestrating trades with the Go ADK service.

This module bridges the Python trading stack with the ADK-Go orchestrator by:

- Gathering rich context (account snapshots, allocations, RAG sentiment) before
  delegating to the Go service.
- Selecting the most confident actionable recommendation across a basket of
  symbols.
- Providing structured results that the main orchestrator can execute or fall
  back from when necessary.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Any

try:
    from rag_store import SentimentSQLiteStore  # type: ignore
except Exception:  # noqa: BLE001
    SentimentSQLiteStore = None  # type: ignore

from src.orchestration.adk_client import (
    ADKClientConfig,
    ADKOrchestratorClient,
)

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL_UNIVERSE = ("SPY", "QQQ", "VOO")


@dataclass
class ADKDecision:
    """Structured response from the ADK orchestrator."""

    symbol: str
    action: str
    confidence: float
    position_size: float
    risk: dict[str, Any]
    execution: dict[str, Any]
    sentiment: dict[str, Any]
    raw: dict[str, Any]


class ADKTradeAdapter:
    """
    Convenience wrapper around `ADKOrchestratorClient` with RAG enrichment.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        base_url: str | None = None,
        app_name: str | None = None,
        root_agent_name: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.enabled = enabled
        if not enabled:
            self.client: ADKOrchestratorClient | None = None
        else:
            config = ADKClientConfig(
                base_url=base_url or os.getenv("ADK_BASE_URL", "http://127.0.0.1:8080/api"),
                app_name=app_name or os.getenv("ADK_APP_NAME", "trading_orchestrator"),
                root_agent_name=root_agent_name
                or os.getenv("ADK_ROOT_AGENT", "trading_orchestrator_root_agent"),
                user_id=user_id or os.getenv("ADK_USER_ID", "python-stack"),
                request_timeout=float(os.getenv("ADK_REQUEST_TIMEOUT", "90")),
            )
            self.client = ADKOrchestratorClient(config=config)

        # RAG sentiment store (optional; lazy init)
        self._sentiment_store: Any | None = None

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def evaluate(
        self,
        *,
        symbols: Sequence[str],
        context: dict[str, Any] | None = None,
    ) -> ADKDecision | None:
        """
        Run the ADK orchestrator across a universe of symbols and return the
        most confident actionable decision.
        """
        if not self.enabled or not self.client:
            logger.debug("ADKTradeAdapter disabled - skipping evaluation")
            return None

        if not symbols:
            symbols = DEFAULT_SYMBOL_UNIVERSE

        context_base = context.copy() if context else {}
        best: ADKDecision | None = None

        for symbol in symbols:
            enriched_ctx = {
                **context_base,
                "rag_sentiment": self._load_sentiment(symbol),
            }

            try:
                result = self.client.run_structured(
                    symbol=symbol,
                    context=enriched_ctx,
                    require_json=False,
                )
            except Exception as exc:
                # More detailed error logging
                import traceback

                logger.error(
                    "ADK run failed for %s: %s\n%s",
                    symbol,
                    exc,
                    traceback.format_exc(),
                )
                # Don't silently continue - log and continue to next symbol
                continue

            if not result:
                logger.info("ADK returned empty result for %s", symbol)
                continue

            decision = self._decision_from_payload(symbol, result)
            if not decision:
                continue

            if best is None or decision.confidence > best.confidence:
                best = decision

        if best:
            logger.info(
                "ADK selected %s action=%s confidence=%.2f%% position_size=%.2f risk=%s",
                best.symbol,
                best.action,
                best.confidence * 100,
                best.position_size,
                best.risk.get("decision", "UNKNOWN"),
            )
        else:
            logger.warning(
                "ADK provided no actionable decisions for symbols %s; will fall back to Python strategies",
                symbols,
            )

        return best

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _load_sentiment(self, symbol: str) -> dict[str, Any]:
        """
        Retrieve the latest sentiment snapshots for a symbol from the SQLite store.
        """
        if SentimentSQLiteStore is None:
            return {}

        try:
            store = self._sentiment_store or SentimentSQLiteStore()
            self._sentiment_store = store
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sentiment store unavailable: %s", exc)
            return {}

        try:
            rows = list(store.fetch_latest_by_ticker(symbol, limit=10))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load sentiment for %s: %s", symbol, exc)
            return {}

        if not rows:
            return {}

        scores = [row["score"] for row in rows if row["score"] is not None]
        confidence = [row["confidence"] for row in rows if row["confidence"]]
        regime = next((row["market_regime"] for row in rows if row["market_regime"]), None)

        return {
            "samples": [dict(row) for row in rows[:5]],
            "average_score": mean(scores) if scores else None,
            "latest_score": rows[0]["score"],
            "confidence_mode": confidence[0] if confidence else None,
            "market_regime": regime,
        }

    def _decision_from_payload(self, symbol: str, payload: dict[str, Any]) -> ADKDecision | None:
        trade_summary = payload.get("trade_summary") or {}
        action = trade_summary.get("action", "HOLD").upper()
        if action not in {"BUY", "SELL"}:
            logger.debug("ADK for %s suggested %s - ignoring", symbol, action)
            return None

        risk = payload.get("risk") or {}
        risk_decision = str(risk.get("decision", "")).upper()
        if risk_decision and risk_decision not in {"APPROVE", "REVIEW"}:
            logger.info("ADK risk module rejected %s (%s)", symbol, risk_decision)
            return None

        confidence = float(trade_summary.get("confidence", 0.0) or 0.0)
        position_size = float(
            risk.get("position_size")
            or risk.get("positionSize")
            or trade_summary.get("position_size")
            or 0.0
        )

        execution = payload.get("execution") or {}
        sentiment = payload.get("sentiment") or {}

        return ADKDecision(
            symbol=symbol,
            action=action,
            confidence=confidence,
            position_size=position_size,
            risk=risk,
            execution=execution,
            sentiment=sentiment,
            raw=payload,
        )


def summarize_adk_decision(decision: ADKDecision) -> dict[str, Any]:
    """
    Convert an ADKDecision into a serialisable summary for logging/metrics.
    """
    return {
        "symbol": decision.symbol,
        "action": decision.action,
        "confidence": decision.confidence,
        "position_size": decision.position_size,
        "risk": decision.risk,
        "execution": decision.execution,
        "sentiment": decision.sentiment,
    }
