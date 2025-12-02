"""LangChain-powered sentiment analyst with VADER fallback and ensemble blending."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_vader_analyzer = None
_langchain_available = None


def _get_vader():
    """Lazy load VADER sentiment analyzer."""
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader_analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
        except ImportError:
            logger.warning("vaderSentiment not available, VADER fallback disabled")
            _vader_analyzer = False
    return _vader_analyzer if _vader_analyzer else None


def _check_langchain():
    """Check if LangChain is available."""
    global _langchain_available
    if _langchain_available is None:
        try:
            from langchain_agents.agents import build_price_action_agent
            from langchain_community.chat_models import ChatAnthropic
            _langchain_available = True
        except ImportError:
            logger.warning("LangChain not available, LLM sentiment disabled")
            _langchain_available = False
    return _langchain_available


class LangChainSentimentAgent:
    """
    Robust sentiment analyst with VADER fallback and ensemble blending.

    Features:
    - Primary: LLM-based sentiment via LangChain (Claude/GPT)
    - Fallback: VADER lexicon-based sentiment when API fails
    - Blending: 65% LLM + 35% VADER for robustness
    - Regime boost: Adjusts weights based on market regime
    """

    MODEL_PRICING = {
        "claude-3-5-haiku-20241022": 0.006,  # ~$0.006 per short call
        "gpt-4o-mini": 0.008,
        "claude-3-5-sonnet-20241022": 0.045,
    }

    # Blending weights
    LLM_WEIGHT = float(os.getenv("SENTIMENT_LLM_WEIGHT", "0.65"))
    VADER_WEIGHT = float(os.getenv("SENTIMENT_VADER_WEIGHT", "0.35"))

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("HYBRID_LLM_MODEL", "claude-3-5-haiku-20241022")
        self.cost_override = os.getenv("HYBRID_LLM_COST")
        self._executor = None
        self._api_failures = 0
        self._max_api_failures = int(os.getenv("MAX_API_FAILURES_BEFORE_FALLBACK", "3"))

    def _build_llm(self):
        """Build LangChain LLM if available."""
        if not _check_langchain():
            return None

        from langchain_community.chat_models import ChatAnthropic

        temperature = float(os.getenv("HYBRID_LLM_TEMPERATURE", "0.3"))
        logger.info("Initializing analyst LLM (%s, temp=%s)", self.model_name, temperature)
        return ChatAnthropic(model=self.model_name, temperature=temperature)

    def _get_executor(self):
        """Get or create the LangChain executor."""
        if self._executor is None and _check_langchain():
            from langchain_agents.agents import build_price_action_agent
            llm = self._build_llm()
            if llm:
                self._executor = build_price_action_agent(llm=llm)
        return self._executor

    def _analyze_with_vader(self, texts: list[str]) -> float:
        """
        Analyze sentiment using VADER lexicon.

        VADER is fast, free, and works well for social media/news headlines.
        Returns compound score in range [-1, 1].
        """
        analyzer = _get_vader()
        if not analyzer or not texts:
            return 0.0

        scores = []
        for text in texts:
            if text and isinstance(text, str):
                try:
                    result = analyzer.polarity_scores(text)
                    scores.append(result["compound"])
                except Exception as exc:
                    logger.debug("VADER analysis failed for text: %s", exc)

        if not scores:
            return 0.0

        return float(np.mean(scores))

    def _extract_texts_from_indicators(self, indicators: dict[str, Any]) -> list[str]:
        """Extract text content from indicators for VADER analysis."""
        texts = []

        # Extract from various indicator fields
        for key in ["news_headlines", "headlines", "tweets", "reddit_titles", "tiktok_captions"]:
            if key in indicators and indicators[key]:
                if isinstance(indicators[key], list):
                    texts.extend([str(t) for t in indicators[key] if t])
                elif isinstance(indicators[key], str):
                    texts.append(indicators[key])

        # Also use reason field if present
        if "reason" in indicators and indicators["reason"]:
            texts.append(str(indicators["reason"]))

        return texts

    def analyze_news(
        self,
        symbol: str,
        indicators: dict[str, Any] | None = None,
        regime_id: int = 0,
    ) -> dict[str, Any]:
        """
        Analyze sentiment with LLM primary and VADER fallback.

        Blends scores: 65% LLM + 35% VADER by default.
        In high-volatility regimes, increases VADER weight for stability.

        Args:
            symbol: Stock symbol to analyze
            indicators: Technical indicators and news context
            regime_id: Current regime (0=calm, 1=trend, 2=vol, 3=spike)

        Returns:
            dict(score=float, cost=float, reason=str, model=str, sources=list)
        """
        indicators = indicators or {}
        llm_score = None
        vader_score = None
        reason = "No analysis performed"
        sources = []
        cost = 0.0

        # Extract texts for VADER analysis
        texts = self._extract_texts_from_indicators(indicators)

        # Try VADER first (fast, always available)
        if texts:
            vader_score = self._analyze_with_vader(texts)
            sources.append("vader")
            logger.debug("VADER score for %s: %.3f", symbol, vader_score)

        # Try LLM if not in failover mode
        if self._api_failures < self._max_api_failures:
            try:
                executor = self._get_executor()
                if executor:
                    llm_result = self._call_llm(symbol, indicators)
                    llm_score = llm_result.get("score", 0.0)
                    reason = llm_result.get("reason", "LLM analysis")
                    cost = llm_result.get("cost", 0.0)
                    sources.append("llm")
                    self._api_failures = 0  # Reset on success
                    logger.debug("LLM score for %s: %.3f", symbol, llm_score)
            except Exception as exc:
                self._api_failures += 1
                logger.warning(
                    "LLM API failed for %s (failure %d/%d): %s",
                    symbol,
                    self._api_failures,
                    self._max_api_failures,
                    exc,
                )
        else:
            logger.info("LLM API in cooldown, using VADER-only for %s", symbol)

        # Blend scores with regime adjustment
        final_score = self._blend_scores(llm_score, vader_score, regime_id)

        # Generate reason if only VADER was used
        if llm_score is None and vader_score is not None:
            reason = f"VADER sentiment analysis (LLM unavailable): {self._score_to_label(vader_score)}"

        return {
            "score": round(final_score, 3),
            "reason": reason,
            "cost": cost,
            "model": self.model_name if llm_score is not None else "vader",
            "sources": sources,
            "llm_score": llm_score,
            "vader_score": vader_score,
            "regime_id": regime_id,
        }

    def _call_llm(self, symbol: str, indicators: dict[str, Any]) -> dict[str, Any]:
        """Make the actual LLM API call."""
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
        }

    def _blend_scores(
        self,
        llm_score: float | None,
        vader_score: float | None,
        regime_id: int,
    ) -> float:
        """
        Blend LLM and VADER scores with regime adjustment.

        In volatile regimes (2, 3), increase VADER weight for stability
        since VADER is deterministic and less prone to hallucination.
        """
        # Adjust weights based on regime
        llm_weight = self.LLM_WEIGHT
        vader_weight = self.VADER_WEIGHT

        if regime_id >= 2:  # volatile or spike
            # Shift toward VADER in high-vol regimes
            llm_weight = 0.50
            vader_weight = 0.50
        elif regime_id == 1:  # trending
            # Slight boost to LLM in trending markets
            llm_weight = 0.70
            vader_weight = 0.30

        # Handle missing scores
        if llm_score is None and vader_score is None:
            return 0.0
        if llm_score is None:
            return vader_score
        if vader_score is None:
            return llm_score

        # Weighted blend
        blended = llm_weight * llm_score + vader_weight * vader_score

        # Apply regime boost (0.1 per regime level for bullish signals)
        if regime_id > 0 and blended > 0:
            blended *= 1 + (0.1 * regime_id)
            blended = min(1.0, blended)

        return blended

    @staticmethod
    def _score_to_label(score: float) -> str:
        """Convert numeric score to human-readable label."""
        if score >= 0.5:
            return "strongly bullish"
        if score >= 0.2:
            return "bullish"
        if score >= -0.2:
            return "neutral"
        if score >= -0.5:
            return "bearish"
        return "strongly bearish"

    def robust_ensemble(
        self,
        sources: dict[str, list[str]],
        regime_id: int = 0,
    ) -> float:
        """
        Analyze sentiment from multiple sources with VADER + LLM blend.

        Args:
            sources: Dict mapping source names to lists of texts
                     e.g., {'reddit': [...], 'tiktok': [...], 'bogleheads': [...]}
            regime_id: Current market regime (0-3)

        Returns:
            Blended sentiment score in [-1, 1]
        """
        scores = []

        for src_name, texts in sources.items():
            if not texts:
                continue

            # Get VADER score for this source
            vader_score = self._analyze_with_vader(texts)

            # Try LLM for richer context (sample if too many texts)
            llm_score = None
            if self._api_failures < self._max_api_failures:
                sample_texts = texts[:5]  # Limit to 5 texts per source
                try:
                    llm_result = self._call_llm(
                        symbol=src_name.upper(),
                        indicators={"texts": sample_texts, "source": src_name},
                    )
                    llm_score = llm_result.get("score", 0.0)
                except Exception:
                    pass

            # Blend for this source
            blended = self._blend_scores(llm_score, vader_score, regime_id)
            scores.append(blended)

            logger.debug(
                "Source %s: vader=%.3f, llm=%s, blended=%.3f",
                src_name,
                vader_score,
                f"{llm_score:.3f}" if llm_score is not None else "N/A",
                blended,
            )

        if not scores:
            return 0.0

        return float(np.mean(scores))
