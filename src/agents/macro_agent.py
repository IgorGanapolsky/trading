"""
Macroeconomic Agent

This agent analyzes the RAG store for forward-looking macroeconomic context
to determine if the overall environment is Dovish, Hawkish, or Neutral.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from src.rag.sentiment_store import SentimentRAGStore

# Optional LangChain agent - may have been removed in cleanup
try:
    from src.langchain_agents.analyst import LangChainSentimentAgent
except ImportError:
    LangChainSentimentAgent = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

MacroContextState = Literal["DOVISH", "HAWKISH", "NEUTRAL", "UNKNOWN"]


class MacroeconomicAgent:
    """
    Determines the macroeconomic context by querying the RAG store
    for forward-looking sentiment.
    """

    def __init__(
        self,
        cache_ttl_hours: int = 12,
        cache_path: str | Path = "data/cache/macro_context.json",
    ):
        # RAG store is optional - trading can proceed without it
        try:
            self.rag_store = SentimentRAGStore()
        except ImportError as e:
            logger.warning(f"RAG store unavailable (sentence-transformers not installed): {e}")
            self.rag_store = None
        except Exception as e:
            logger.warning(f"RAG store initialization failed: {e}")
            self.rag_store = None

        # LLM agent is optional - trading can proceed without it
        if LangChainSentimentAgent is not None:
            try:
                self.llm_agent = LangChainSentimentAgent()
            except Exception as e:
                logger.warning(f"LangChain agent initialization failed: {e}")
                self.llm_agent = None
        else:
            logger.warning("LangChain agent unavailable (module removed)")
            self.llm_agent = None
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(exist_ok=True)

    def _load_from_cache(self) -> dict[str, Any] | None:
        """Load the macro context from a local cache if it's recent."""
        if not self.cache_path.exists():
            return None

        try:
            cached_data = json.loads(self.cache_path.read_text())
            cached_timestamp = datetime.fromisoformat(cached_data["timestamp"])
            if datetime.utcnow() - cached_timestamp < self.cache_ttl:
                logger.info("Using cached macroeconomic context.")
                return cached_data
        except Exception as e:
            logger.warning("Could not load macro context from cache: %s", e)

        return None

    def _save_to_cache(self, context: dict[str, Any]) -> None:
        """Save the determined macro context to the cache."""
        try:
            context["timestamp"] = datetime.utcnow().isoformat()
            self.cache_path.write_text(json.dumps(context, indent=2))
        except Exception as e:
            logger.error("Failed to save macro context to cache: %s", e)

    def get_macro_context(self) -> dict[str, Any]:
        """
        Determine the current macroeconomic context.

        Returns:
            A dictionary containing the state, reason, and supporting documents.
        """
        # 1. Check cache first
        cached_context = self._load_from_cache()
        if cached_context:
            return cached_context

        logger.info("Performing fresh macroeconomic context analysis...")

        # 2. Check if LLM agent is available
        if self.llm_agent is None:
            logger.info("LLM agent unavailable - returning NEUTRAL macro context")
            return {
                "state": "NEUTRAL",
                "reason": "LLM agent disabled (langchain_agents module removed)",
            }

        # 3. Query RAG store for relevant documents
        # Skip RAG if not available (sentence-transformers not installed)
        if self.rag_store is None:
            logger.info("RAG store unavailable - returning NEUTRAL macro context")
            return {
                "state": "NEUTRAL",
                "reason": "RAG features disabled (sentence-transformers not installed)",
            }

        try:
            query = (
                "forward-looking macroeconomic outlook, "
                "interest rate cut or hike expectations, "
                "inflation forecast, recession risk, "
                "market sentiment for the next 6-12 months"
            )
            retrieved_docs = self.rag_store.query(query=query, top_k=10)
            if not retrieved_docs:
                logger.warning("No documents found in RAG store for macro analysis.")
                return {"state": "UNKNOWN", "reason": "No documents found."}
        except Exception as e:
            logger.error("Failed to query RAG store for macro context: %s", e)
            return {"state": "UNKNOWN", "reason": f"RAG query failed: {e}"}

        # 3. Use LLM to analyze retrieved documents
        # Format documents for the prompt
        doc_texts = [
            f"- {doc.get('metadata', {}).get('title', 'Untitled')}: {doc.get('text', '')[:300]}..."
            for doc in retrieved_docs
        ]
        context_str = "\n".join(doc_texts)

        prompt = f"""
As a Chief Economist, analyze the following retrieved intelligence briefings to determine the overall forward-looking macroeconomic sentiment.
The key question is whether the environment is becoming more accommodative (Dovish) or more restrictive (Hawkish).

Classify the sentiment into one of three states: DOVISH, HAWKISH, or NEUTRAL.

- DOVISH implies expected interest rate cuts, quantitative easing, pro-growth policies, or a general loosening of financial conditions.
- HAWKISH implies expected interest rate hikes, quantitative tightening, inflation-fighting policies, or a general tightening of financial conditions.
- NEUTRAL implies a mixed, uncertain, or stable outlook.

Retrieved Briefings:
{context_str}

Based on the briefings, provide your analysis strictly in the following JSON format:
{{"state": "<DOVISH|HAWKISH|NEUTRAL>", "reason": "<Brief, evidence-based rationale>", "confidence": <0.0 to 1.0>}}
"""
        try:
            llm_result = self.llm_agent.analyze_news("MACRO_CONTEXT", {"prompt": prompt})
            # The result from analyze_news is a dict with 'score', 'reason', etc.
            # We need to adapt this to our DOVISH/HAWKISH state.
            score = llm_result.get("score", 0.0)
            if score > 0.3:
                state: MacroContextState = "DOVISH"
            elif score < -0.3:
                state: MacroContextState = "HAWKISH"
            else:
                state: MacroContextState = "NEUTRAL"

            final_context = {
                "state": state,
                "reason": llm_result.get("reason", "No rationale provided."),
                "confidence": abs(score),
                "retrieved_doc_count": len(retrieved_docs),
                "llm_model": llm_result.get("model"),
            }

        except Exception as e:
            logger.error("LLM analysis for macro context failed: %s", e)
            return {"state": "UNKNOWN", "reason": f"LLM analysis failed: {e}"}

        # 4. Save to cache and return
        self._save_to_cache(final_context)
        return final_context
