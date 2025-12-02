"""LangChain-powered sentiment analyst."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_agents.agents import build_price_action_agent
from langchain_community.chat_models import ChatAnthropic

logger = logging.getLogger(__name__)


class LangChainSentimentAgent:
    """Thin wrapper around the LangChain price-action agent."""

    MODEL_PRICING = {
        "claude-3-5-haiku-20241022": 0.006,  # ~$0.006 per short call
        "gpt-4o-mini": 0.008,
        "claude-3-5-sonnet-20241022": 0.045,
    }

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("HYBRID_LLM_MODEL", "claude-3-5-haiku-20241022")
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

    def analyze_news(self, symbol: str, indicators: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Ask the LLM whether current headlines/technicals suggest a red flag.

        Returns:
            dict(score=float, cost=float, reason=str, model=str)
        """
        indicators = indicators or {}
        # Goldilocks Prompt: Sentiment gate with clear scoring examples
        prompt = (
            f"""Analyst gate for {symbol}. Score sentiment -1 (strong avoid) to +1 (strong proceed).

TECHNICAL CONTEXT:
{json.dumps(indicators, default=str)[:600]}

SCORING PRINCIPLES:
- Negative news (lawsuits, downgrades, misses): -0.3 to -1.0
- Neutral/mixed signals: -0.2 to +0.2
- Positive catalysts (upgrades, beats, expansion): +0.3 to +1.0
- When uncertain, bias toward 0 (neutral) not extremes

EXAMPLES:
{{"score": 0.7, "reason": "Analyst upgrade to Buy, strong earnings beat, sector tailwinds"}}
{{"score": -0.5, "reason": "SEC investigation announced, insider selling detected"}}
{{"score": 0.1, "reason": "No material news, technicals slightly positive but low conviction"}}
{{"score": -0.8, "reason": "Earnings miss + guidance cut + CEO resignation - multiple red flags"}}

Respond strictly as JSON:
{{"score": <-1 to 1>, "reason": "<brief rationale>"}}"""
            ""
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
