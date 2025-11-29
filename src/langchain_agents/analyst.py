"""LangChain-powered sentiment analyst."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from langchain_community.chat_models import ChatAnthropic

from langchain_agents.agents import build_price_action_agent

logger = logging.getLogger(__name__)


class LangChainSentimentAgent:
    """Thin wrapper around the LangChain price-action agent."""

    MODEL_PRICING = {
        "claude-3-5-haiku-20241022": 0.006,  # ~$0.006 per short call
        "gpt-4o-mini": 0.008,
        "claude-3-5-sonnet-20241022": 0.045,
    }

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "HYBRID_LLM_MODEL", "claude-3-5-haiku-20241022"
        )
        self.cost_override = os.getenv("HYBRID_LLM_COST")
        self._executor = None

    def _build_llm(self) -> ChatAnthropic:
        temperature = float(os.getenv("HYBRID_LLM_TEMPERATURE", "0.3"))
        logger.info("Initializing analyst LLM (%s, temp=%s)", self.model_name, temperature)
        return ChatAnthropic(model=self.model_name, temperature=temperature)

    def _get_executor(self):
        if self._executor is None:
            llm = self._build_llm()
            self._executor = build_price_action_agent(llm=llm)
        return self._executor

    def analyze_news(
        self, symbol: str, indicators: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Ask the LLM whether current headlines/technicals suggest a red flag.

        Returns:
            dict(score=float, cost=float, reason=str, model=str)
        """
        indicators = indicators or {}
        prompt = (
            "You are the analyst gate for an automated trading system. "
            "Given the technical context below, respond with JSON containing "
            "keys score (-1 to 1) and reason. Negative score means avoid the trade.\n\n"
            f"Ticker: {symbol}\n"
            f"Technical context: {json.dumps(indicators, default=str)[:800]}\n\n"
            "Respond strictly as JSON, e.g. {\"score\": 0.1, \"reason\": \"...\"}"
        )

        executor = self._get_executor()
        result = executor.invoke({"input": prompt})
        raw_output = result.get("output", "") if isinstance(result, dict) else str(result)

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response: %s", raw_output)
            parsed = {"score": 0.0, "reason": raw_output}

        score = float(parsed.get("score", 0.0))
        reason = parsed.get("reason", "No rationale provided.")

        if self.cost_override is not None:
            cost_estimate = float(self.cost_override)
        else:
            cost_estimate = self.MODEL_PRICING.get(self.model_name, 0.01)

        return {
            "score": score,
            "reason": reason,
            "cost": cost_estimate,
            "model": self.model_name,
        }

