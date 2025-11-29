"""LangChain-powered sentiment analyst."""

from __future__ import annotations

import json
import logging
from typing import Dict, Any

from langchain_agents.agents import build_price_action_agent

logger = logging.getLogger(__name__)


class LangChainSentimentAgent:
    """Thin wrapper around the LangChain price-action agent."""

    def __init__(self) -> None:
        self._executor = None

    def _get_executor(self):
        if self._executor is None:
            self._executor = build_price_action_agent()
        return self._executor

    def analyze_news(
        self, symbol: str, indicators: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Ask the LLM whether current headlines/technicals suggest a red flag.

        Returns:
            dict(score=float, cost=float, reason=str)
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

        # Rough cost estimate (Haiku). In production we would read usage metadata.
        cost_estimate = 0.01

        return {"score": score, "reason": reason, "cost": cost_estimate}

