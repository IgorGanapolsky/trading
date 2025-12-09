"""
Multi-LLM Analysis Engine for Trading System

This module provides a comprehensive analysis engine that queries multiple LLMs
(Gemini 3 Pro Preview, Claude Sonnet 4, GPT-4o, optional DeepSeek) through OpenRouter API to generate
ensemble sentiment scores, IPO analysis, and market outlooks.

Features:
- Parallel querying of multiple LLMs
- Ensemble sentiment scoring (-1.0 to 1.0)
- IPO analysis scoring (0-100)
- Market data and news analysis
- Error handling and automatic retries
- Rate limiting and timeout management

Example:
    >>> analyzer = MultiLLMAnalyzer(api_key="your_openrouter_key")
    >>> sentiment = await analyzer.get_ensemble_sentiment(market_data, news)
    >>> ipo_score = await analyzer.analyze_ipo(company_data)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Prompt engineering for time series analysis
from src.core.prompt_engineering import (
    MarketDataSchema,
    PromptEngineer,
    get_temporal_header,
)

# OpenAI client - optional dependency (may use OpenRouter instead)
try:
    from openai import AsyncOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OpenAI = None  # type: ignore
    OPENAI_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

if not OPENAI_AVAILABLE:
    logger.warning("openai package not installed - MultiLLMAnalyzer will be unavailable")


class LLMModel(Enum):
    """Available LLM models through OpenRouter."""

    GEMINI_3_PRO = "google/gemini-3-pro-preview"  # Latest Gemini 3 Pro
    CLAUDE_SONNET_4 = "anthropic/claude-sonnet-4"  # Latest Claude Sonnet
    GPT4O = "openai/gpt-4o"  # GPT-4o
    GEMINI_2_FLASH = "google/gemini-2.5-flash"  # Fallback Gemini model
    DEEPSEEK_R1 = "deepseek/deepseek-r1"  # DeepSeek reasoning model (via OpenRouter)


@dataclass
class LLMResponse:
    """Container for LLM response data."""

    model: str
    content: str
    tokens_used: int
    latency: float
    success: bool
    error: str | None = None


@dataclass
class SentimentAnalysis:
    """Container for sentiment analysis results."""

    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasoning: str
    individual_scores: dict[str, float]
    metadata: dict[str, Any]


@dataclass
class IPOAnalysis:
    """Container for IPO analysis results."""

    score: int  # 0-100
    recommendation: str  # "Strong Buy", "Buy", "Hold", "Avoid"
    risk_level: str  # "Low", "Medium", "High"
    key_factors: list[str]
    concerns: list[str]
    price_target: float | None
    confidence: float
    individual_analyses: dict[str, dict[str, Any]]


@dataclass
class StockAnalysis:
    """Container for stock analysis results."""

    symbol: str
    sentiment: float
    recommendation: str
    target_price: float | None
    risk_assessment: str
    key_insights: list[str]
    confidence: float
    timestamp: float


@dataclass
class MarketOutlook:
    """Container for market outlook results."""

    overall_sentiment: float
    trend: str  # "Bullish", "Bearish", "Neutral"
    key_drivers: list[str]
    risks: list[str]
    opportunities: list[str]
    timeframe: str
    confidence: float


class MultiLLMAnalyzer:
    """
    Multi-LLM analysis engine for trading decisions.

    This class manages parallel queries to multiple LLMs through OpenRouter API,
    aggregates responses, and provides ensemble analysis for trading decisions.

    Attributes:
        api_key: OpenRouter API key
        models: List of LLM models to query
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        rate_limit_delay: Delay between requests in seconds
    """

    def __init__(
        self,
        api_key: str | None = None,
        models: list[LLMModel] | None = None,
        max_retries: int = 3,
        timeout: int = 60,
        rate_limit_delay: float = 2.0,  # Increased from 1.0 to reduce 429/500 errors
        use_async: bool = True,
    ):
        """
        Initialize the Multi-LLM Analyzer.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            models: List of models to use (defaults to all three models)
            max_retries: Maximum retry attempts per request
            timeout: Request timeout in seconds
            rate_limit_delay: Delay between requests to avoid rate limits
            use_async: Whether to use async client (recommended)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package is required for MultiLLMAnalyzer. "
                "Install with: pip install openai"
            )

        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key must be provided or set in OPENROUTER_API_KEY env var"
            )

        self.models = models or [
            LLMModel.GEMINI_3_PRO,  # Latest model with improved reasoning
            LLMModel.CLAUDE_SONNET_4,  # Latest Claude Sonnet
            LLMModel.GPT4O,  # GPT-4o
        ]
        deepseek_enabled_env = os.getenv("OPENROUTER_ENABLE_DEEPSEEK", "false").lower()
        deepseek_enabled = deepseek_enabled_env not in {"0", "false", "off", "no"}
        if deepseek_enabled and LLMModel.DEEPSEEK_R1 not in self.models:
            self.models.append(LLMModel.DEEPSEEK_R1)
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.use_async = use_async

        # Initialize OpenAI client with OpenRouter (with Helicone + LangSmith observability if enabled)
        # Use observability wrapper if available (handles Helicone gateway + LangSmith tracing)
        try:
            from src.utils.langsmith_wrapper import (
                get_traced_async_openai_client,
                get_traced_openai_client,
            )

            if use_async:
                # Wrapper auto-routes through Helicone if HELICONE_API_KEY is set
                self.client = get_traced_async_openai_client(api_key=self.api_key)
            else:
                self.sync_client = get_traced_openai_client(api_key=self.api_key)
        except ImportError:
            # Fallback to regular client with Helicone support if wrapper not available
            helicone_key = os.getenv("HELICONE_API_KEY")
            if helicone_key:
                base_url = "https://openrouter.helicone.ai/api/v1"
                default_headers = {"Helicone-Auth": f"Bearer {helicone_key}"}
            else:
                base_url = "https://openrouter.ai/api/v1"
                default_headers = None

            if use_async:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=default_headers,
                )
            else:
                self.sync_client = OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=default_headers,
                )

        if deepseek_enabled:
            logger.info(
                "DeepSeek (model=%s) enabled via OPENROUTER_ENABLE_DEEPSEEK",
                LLMModel.DEEPSEEK_R1.value,
            )

        logger.info(f"Initialized MultiLLMAnalyzer with models: {[m.value for m in self.models]}")

    async def _query_llm_async(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Query a single LLM with retry logic.

        Args:
            model: The LLM model to query
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse object containing the result
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = await self.client.chat.completions.create(
                    model=model.value,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency = time.time() - start_time

                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0

                logger.debug(f"Successfully queried {model.value} in {latency:.2f}s")

                return LLMResponse(
                    model=model.value,
                    content=content,
                    tokens_used=tokens_used,
                    latency=latency,
                    success=True,
                )

            except Exception as e:
                # Enhanced error logging to identify specific failure patterns
                error_type = type(e).__name__
                error_msg = str(e)
                status_code = getattr(e, "status_code", None)
                if status_code:
                    logger.warning(
                        f"[MultiLLM-Async] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: HTTP {status_code} - {error_type}: {error_msg}"
                    )
                else:
                    logger.warning(
                        f"[MultiLLM-Async] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: {error_type}: {error_msg}"
                    )

                if attempt == self.max_retries - 1:
                    return LLMResponse(
                        model=model.value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=f"{error_type}: {error_msg}",
                    )

                # Exponential backoff
                await asyncio.sleep(2**attempt * self.rate_limit_delay)

        return LLMResponse(
            model=model.value,
            content="",
            tokens_used=0,
            latency=0,
            success=False,
            error="Max retries reached (loop finished)",
        )

    def _query_llm_sync(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Synchronous version of _query_llm_async."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = self.sync_client.chat.completions.create(
                    model=model.value,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency = time.time() - start_time

                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0

                logger.debug(f"Successfully queried {model.value} in {latency:.2f}s")

                return LLMResponse(
                    model=model.value,
                    content=content,
                    tokens_used=tokens_used,
                    latency=latency,
                    success=True,
                )

            except Exception as e:
                # Enhanced error logging to identify specific failure patterns
                error_type = type(e).__name__
                error_msg = str(e)
                status_code = getattr(e, "status_code", None)
                if status_code:
                    logger.warning(
                        f"[MultiLLM-Sync] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: HTTP {status_code} - {error_type}: {error_msg}"
                    )
                else:
                    logger.warning(
                        f"[MultiLLM-Sync] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: {error_type}: {error_msg}"
                    )

                if attempt == self.max_retries - 1:
                    return LLMResponse(
                        model=model.value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=f"{error_type}: {error_msg}",
                    )

                # Exponential backoff
                time.sleep(2**attempt * self.rate_limit_delay)

        return LLMResponse(
            model=model.value,
            content="",
            tokens_used=0,
            latency=0,
            success=False,
            error="Max retries reached (loop finished)",
        )

    async def _query_all_llms_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> list[LLMResponse]:
        """
        Query all configured LLMs with staggered starts to avoid rate limits.

        Uses staggered parallel execution: each model starts with a small delay
        to prevent hitting OpenRouter rate limits (429 errors).

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            List of LLMResponse objects
        """

        async def query_with_delay(model, delay: float):
            """Query a model after a staggered delay."""
            if delay > 0:
                await asyncio.sleep(delay)
            return await self._query_llm_async(
                model, prompt, system_prompt, temperature, max_tokens
            )

        # Stagger requests: 0s, 0.5s, 1.0s, 1.5s between model starts
        # This prevents 429 rate limit errors from OpenRouter
        tasks = [
            query_with_delay(model, i * self.rate_limit_delay)
            for i, model in enumerate(self.models)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to LLMResponse
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Error querying {self.models[i].value}: {str(response)}")
                valid_responses.append(
                    LLMResponse(
                        model=self.models[i].value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=str(response),
                    )
                )
            else:
                valid_responses.append(response)

        return valid_responses

    def _query_all_llms_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> list[LLMResponse]:
        """Synchronous version of _query_all_llms_async."""
        responses = []
        for model in self.models:
            response = self._query_llm_sync(model, prompt, system_prompt, temperature, max_tokens)
            responses.append(response)
            time.sleep(self.rate_limit_delay)
        return responses

    def _parse_sentiment_score(self, content: str) -> float | None:
        """
        Parse sentiment score from LLM response.

        Looks for patterns like:
        - "sentiment: 0.75"
        - "score: -0.5"
        - JSON with "sentiment" or "score" field

        Args:
            content: LLM response content

        Returns:
            Sentiment score between -1.0 and 1.0, or None if not found
        """
        try:
            # Try to parse as JSON first
            if content.strip().startswith("{"):
                data = json.loads(content)
                score = data.get("sentiment") or data.get("score")
                if score is not None:
                    return max(-1.0, min(1.0, float(score)))

            # Look for sentiment/score patterns
            import re

            patterns = [
                r"sentiment[:\s]+(-?\d+\.?\d*)",
                r"score[:\s]+(-?\d+\.?\d*)",
                r"rating[:\s]+(-?\d+\.?\d*)",
            ]

            for pattern in patterns:
                match = re.search(pattern, content.lower())
                if match:
                    score = float(match.group(1))
                    return max(-1.0, min(1.0, score))

            return None

        except Exception as e:
            logger.warning(f"Error parsing sentiment score: {str(e)}")
            return None

    def _parse_ipo_score(self, content: str) -> int | None:
        """
        Parse IPO score from LLM response.

        Args:
            content: LLM response content

        Returns:
            IPO score between 0 and 100, or None if not found
        """
        try:
            # Try to parse as JSON first
            if content.strip().startswith("{"):
                data = json.loads(content)
                score = data.get("ipo_score") or data.get("score")
                if score is not None:
                    return max(0, min(100, int(score)))

            # Look for score patterns
            import re

            patterns = [
                r"ipo[_\s]+score[:\s]+(\d+)",
                r"score[:\s]+(\d+)",
                r"rating[:\s]+(\d+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, content.lower())
                if match:
                    score = int(match.group(1))
                    return max(0, min(100, score))

            return None

        except Exception as e:
            logger.warning(f"Error parsing IPO score: {str(e)}")
            return None

    def _calculate_ensemble_sentiment(
        self, responses: list[LLMResponse]
    ) -> tuple[float, float, dict[str, float]]:
        """
        Calculate ensemble sentiment from multiple LLM responses.

        Args:
            responses: List of LLMResponse objects

        Returns:
            Tuple of (ensemble_score, confidence, individual_scores)
        """
        individual_scores = {}
        valid_scores = []

        for response in responses:
            if response.success:
                score = self._parse_sentiment_score(response.content)
                if score is not None:
                    individual_scores[response.model] = score
                    valid_scores.append(score)

        if not valid_scores:
            logger.warning("No valid sentiment scores found in responses")
            return 0.0, 0.0, individual_scores

        # Calculate ensemble score (weighted average)
        ensemble_score = sum(valid_scores) / len(valid_scores)

        # Calculate confidence based on agreement
        if len(valid_scores) > 1:
            variance = sum((s - ensemble_score) ** 2 for s in valid_scores) / len(valid_scores)
            # Confidence inversely proportional to variance
            confidence = max(0.0, min(1.0, 1.0 - variance))
        else:
            confidence = 0.5  # Low confidence with single model

        return ensemble_score, confidence, individual_scores

    def _calculate_ensemble_ipo_score(
        self, responses: list[LLMResponse]
    ) -> tuple[int, float, dict[str, int]]:
        """
        Calculate ensemble IPO score from multiple LLM responses.

        Args:
            responses: List of LLMResponse objects

        Returns:
            Tuple of (ensemble_score, confidence, individual_scores)
        """
        individual_scores = {}
        valid_scores = []

        for response in responses:
            if response.success:
                score = self._parse_ipo_score(response.content)
                if score is not None:
                    individual_scores[response.model] = score
                    valid_scores.append(score)

        if not valid_scores:
            logger.warning("No valid IPO scores found in responses")
            return 50, 0.0, individual_scores

        # Calculate ensemble score (weighted average)
        ensemble_score = int(sum(valid_scores) / len(valid_scores))

        # Calculate confidence based on agreement
        if len(valid_scores) > 1:
            variance = sum((s - ensemble_score) ** 2 for s in valid_scores) / len(valid_scores)
            # Normalize variance to 0-1 range (max variance is 50^2 = 2500)
            confidence = max(0.0, min(1.0, 1.0 - variance / 2500))
        else:
            confidence = 0.5

        return ensemble_score, confidence, individual_scores

    async def get_ensemble_sentiment(
        self, market_data: dict[str, Any], news: list[dict[str, Any]]
    ) -> float:
        """
        Generate ensemble sentiment score from market data and news.

        Args:
            market_data: Dictionary containing market data (prices, volume, indicators)
            news: List of news articles with 'title', 'content', 'source', etc.

        Returns:
            Sentiment score between -1.0 (very bearish) and 1.0 (very bullish)

        Example:
            >>> market_data = {
            ...     'symbol': 'AAPL',
            ...     'price': 150.0,
            ...     'change': 2.5,
            ...     'volume': 1000000
            ... }
            >>> news = [
            ...     {'title': 'Apple announces new product', 'content': '...'},
            ...     {'title': 'Strong earnings beat', 'content': '...'}
            ... ]
            >>> sentiment = await analyzer.get_ensemble_sentiment(market_data, news)
        """
        # Construct prompt
        market_summary = json.dumps(market_data, indent=2)
        news_summary = "\n".join(
            [
                f"- {article.get('title', 'N/A')}: {article.get('content', '')[:200]}..."
                for article in news[:5]  # Limit to top 5 articles
            ]
        )

        prompt = f"""Analyze the following market data and news to provide a sentiment score.

Market Data:
{market_summary}

Recent News:
{news_summary}

Provide a sentiment score between -1.0 (very bearish) and 1.0 (very bullish).
Include your reasoning.

Format your response as JSON:
{{
    "sentiment": <score>,
    "reasoning": "<your analysis>"
}}
"""

        system_prompt = """You are an expert financial analyst specializing in market sentiment analysis.
Provide objective, data-driven sentiment scores based on technical indicators and news sentiment."""

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.3)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.3)

        ensemble_score, confidence, individual_scores = self._calculate_ensemble_sentiment(
            responses
        )

        logger.info(f"Ensemble sentiment: {ensemble_score:.3f} (confidence: {confidence:.3f})")
        logger.info(f"Individual scores: {individual_scores}")

        return ensemble_score

    async def get_ensemble_sentiment_detailed(
        self, market_data: dict[str, Any], news: list[dict[str, Any]]
    ) -> SentimentAnalysis:
        """
        Generate detailed ensemble sentiment analysis.

        Args:
            market_data: Dictionary containing market data
            news: List of news articles

        Returns:
            SentimentAnalysis object with detailed results
        """
        market_summary = json.dumps(market_data, indent=2)
        news_summary = "\n".join(
            [
                f"- {article.get('title', 'N/A')}: {article.get('content', '')[:200]}..."
                for article in news[:5]
            ]
        )

        prompt = f"""Analyze the following market data and news to provide a detailed sentiment analysis.

Market Data:
{market_summary}

Recent News:
{news_summary}

Provide a comprehensive sentiment analysis.

Format your response as JSON:
{{
    "sentiment": <score between -1.0 and 1.0>,
    "reasoning": "<detailed analysis>"
}}
"""

        system_prompt = """You are an expert financial analyst specializing in market sentiment analysis.
Provide objective, data-driven sentiment scores with detailed reasoning."""

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.3)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.3)

        ensemble_score, confidence, individual_scores = self._calculate_ensemble_sentiment(
            responses
        )

        # Extract reasoning from successful responses
        reasoning_parts = []
        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "reasoning" in data:
                        reasoning_parts.append(f"[{response.model}] {data['reasoning']}")
                except Exception:  # noqa: BLE001
                    pass

        reasoning = (
            "\n\n".join(reasoning_parts) if reasoning_parts else "No detailed reasoning available"
        )

        return SentimentAnalysis(
            score=ensemble_score,
            confidence=confidence,
            reasoning=reasoning,
            individual_scores=individual_scores,
            metadata={
                "market_data": market_data,
                "news_count": len(news),
                "timestamp": time.time(),
            },
        )

    async def get_ensemble_sentiment_enhanced(
        self,
        symbol: str,
        market_data: dict[str, Any],
        news: list[dict[str, Any]],
        regime_state: Any | None = None,
        recent_returns: dict[str, float] | None = None,
    ) -> SentimentAnalysis:
        """
        Enhanced sentiment analysis with temporal context and structured data.

        This method implements prompt engineering best practices from
        MachineLearningMastery for time series LLM analysis:
        1. Temporal context header (market session, regime, timing)
        2. Structured JSON schema for market data
        3. Confidence-aware responses

        Args:
            symbol: Trading symbol (e.g., "SPY")
            market_data: Dictionary containing market data and indicators
            news: List of news articles
            regime_state: Optional RegimeState from regime_detection module
            recent_returns: Optional dict with '1d', '5d', '20d' returns

        Returns:
            SentimentAnalysis with enhanced confidence and reasoning

        Example:
            >>> sentiment = await analyzer.get_ensemble_sentiment_enhanced(
            ...     symbol="SPY",
            ...     market_data={"close": 450.0, "rsi": 55, "macd": 0.25},
            ...     news=[{"title": "Market rallies", "content": "..."}],
            ...     recent_returns={"1d": 0.01, "5d": 0.02}
            ... )
        """
        # Build enhanced prompts using prompt engineering module
        engineer = PromptEngineer()
        prompt, system_prompt = engineer.build_enhanced_sentiment_prompt(
            symbol=symbol,
            market_data=market_data,
            news=news,
            regime_state=regime_state,
            recent_returns=recent_returns,
        )

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.3)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.3)

        # Calculate ensemble sentiment
        ensemble_score, base_confidence, individual_scores = self._calculate_ensemble_sentiment(
            responses
        )

        # Extract confidence and reasoning from responses
        confidences = []
        reasoning_parts = []
        key_factors = []
        risks = []

        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "confidence" in data:
                        confidences.append(float(data["confidence"]))
                    if "reasoning" in data:
                        reasoning_parts.append(f"[{response.model}] {data['reasoning']}")
                    if "key_factors" in data:
                        key_factors.extend(data["key_factors"])
                    if "risks" in data:
                        risks.extend(data["risks"])
                except Exception:  # noqa: BLE001
                    pass

        # Use LLM-reported confidence if available, otherwise use calculated confidence
        final_confidence = sum(confidences) / len(confidences) if confidences else base_confidence

        reasoning = (
            "\n\n".join(reasoning_parts) if reasoning_parts else "No detailed reasoning available"
        )

        logger.info(
            f"Enhanced sentiment for {symbol}: {ensemble_score:.3f} "
            f"(confidence: {final_confidence:.3f})"
        )

        return SentimentAnalysis(
            score=ensemble_score,
            confidence=final_confidence,
            reasoning=reasoning,
            individual_scores=individual_scores,
            metadata={
                "symbol": symbol,
                "market_data": market_data,
                "news_count": len(news),
                "timestamp": time.time(),
                "key_factors": list(set(key_factors))[:5],  # Dedupe, top 5
                "risks": list(set(risks))[:3],  # Dedupe, top 3
                "enhanced": True,  # Flag for enhanced analysis
            },
        )

    async def analyze_two_pass(
        self,
        symbol: str,
        market_data: dict[str, Any],
        regime_state: Any | None = None,
        recent_returns: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Two-pass analysis: Feature extraction then prediction.

        Implements the recommended pattern from MachineLearningMastery:
        - Pass 1: Extract features from market data (patterns, anomalies)
        - Pass 2: Make predictions based on extracted features

        This approach improves prediction quality by separating
        observation from inference.

        Args:
            symbol: Trading symbol
            market_data: Dictionary containing market data and indicators
            regime_state: Optional RegimeState from regime_detection
            recent_returns: Optional dict with '1d', '5d', '20d' returns

        Returns:
            Dictionary with:
                - extracted_features: Features from Pass 1
                - prediction: Trading prediction from Pass 2
                - confidence: Overall confidence
                - recommendation: Trading recommendation
        """
        engineer = PromptEngineer()

        # Build temporal context
        temporal_ctx = engineer.get_temporal_context(
            regime_state=regime_state,
            recent_returns=recent_returns,
        )
        temporal_header = engineer.build_temporal_header(temporal_ctx)

        # Build structured market data
        schema = MarketDataSchema.from_market_data(symbol=symbol, market_data=market_data)

        # === PASS 1: Feature Extraction ===
        logger.info(f"Two-pass analysis for {symbol}: Starting Pass 1 (feature extraction)")

        pass1_prompt, pass1_system = engineer.build_feature_extraction_prompt(
            market_data=schema,
            temporal_header=temporal_header,
        )

        # Use Claude Sonnet 4 for feature extraction (best reasoning)
        pass1_response = await self._query_llm_async(
            model=LLMModel.CLAUDE_SONNET_4,
            prompt=pass1_prompt,
            system_prompt=pass1_system,
            temperature=0.2,  # Low temp for consistent extraction
        )

        extracted_features = {}
        if pass1_response.success:
            try:
                extracted_features = json.loads(pass1_response.content)
                logger.info(f"Pass 1 complete: Extracted {len(extracted_features)} feature categories")
            except json.JSONDecodeError:
                logger.warning("Pass 1 response not valid JSON, using raw content")
                extracted_features = {"raw_analysis": pass1_response.content}
        else:
            logger.error(f"Pass 1 failed: {pass1_response.error}")
            return {
                "extracted_features": {},
                "prediction": {},
                "confidence": 0.0,
                "recommendation": "hold",
                "error": pass1_response.error,
            }

        # === PASS 2: Prediction ===
        logger.info(f"Two-pass analysis for {symbol}: Starting Pass 2 (prediction)")

        pass2_prompt, pass2_system = engineer.build_prediction_prompt(
            market_data=schema,
            temporal_header=temporal_header,
            extracted_features=extracted_features,
        )

        # Query all LLMs for ensemble prediction
        if self.use_async:
            responses = await self._query_all_llms_async(
                pass2_prompt, pass2_system, temperature=0.3
            )
        else:
            responses = self._query_all_llms_sync(pass2_prompt, pass2_system, temperature=0.3)

        # Aggregate predictions
        sentiments = []
        confidences = []
        recommendations = []
        all_reasoning = []

        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "sentiment" in data:
                        sentiments.append(float(data["sentiment"]))
                    if "confidence" in data:
                        confidences.append(float(data["confidence"]))
                    if "recommendation" in data:
                        recommendations.append(data["recommendation"])
                    if "reasoning" in data:
                        all_reasoning.append(f"[{response.model}] {data['reasoning']}")
                except Exception:  # noqa: BLE001
                    pass

        # Calculate ensemble values
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        # Most common recommendation
        if recommendations:
            from collections import Counter

            rec_counter = Counter(recommendations)
            final_recommendation = rec_counter.most_common(1)[0][0]
        else:
            final_recommendation = "hold"

        logger.info(
            f"Two-pass complete for {symbol}: sentiment={avg_sentiment:.3f}, "
            f"confidence={avg_confidence:.3f}, recommendation={final_recommendation}"
        )

        return {
            "symbol": symbol,
            "extracted_features": extracted_features,
            "prediction": {
                "sentiment": avg_sentiment,
                "confidence": avg_confidence,
                "recommendation": final_recommendation,
                "reasoning": "\n\n".join(all_reasoning),
            },
            "confidence": avg_confidence,
            "recommendation": final_recommendation,
            "temporal_context": {
                "session": temporal_ctx.market_session.value,
                "day_type": temporal_ctx.day_type.value,
                "volatility_regime": temporal_ctx.volatility_regime,
                "trend_regime": temporal_ctx.trend_regime,
            },
            "timestamp": time.time(),
        }

    async def analyze(
        self,
        query: str,
        system_prompt: str | None = None,
        model: LLMModel | None = None,
    ) -> LLMResponse:
        """
        Generic analysis using a specific or default model.

        Args:
            query: The analysis query/prompt
            system_prompt: Optional system prompt
            model: Optional model to use (defaults to Claude Sonnet 4)

        Returns:
            LLMResponse object
        """
        # Default to Claude Sonnet 4 for high-quality reasoning
        target_model = model or LLMModel.CLAUDE_SONNET_4

        return await self._query_llm_async(
            model=target_model,
            prompt=query,
            system_prompt=system_prompt,
        )

    async def analyze_ipo(self, company_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze an IPO opportunity and provide scoring.

        Args:
            company_data: Dictionary containing company information:
                - name: Company name
                - sector: Industry sector
                - financials: Financial metrics
                - description: Company description
                - ipo_details: IPO pricing and timing details

        Returns:
            Dictionary containing:
                - score: IPO score (0-100)
                - recommendation: Investment recommendation
                - risk_level: Risk assessment
                - key_factors: List of positive factors
                - concerns: List of concerns
                - confidence: Confidence level (0.0-1.0)

        Example:
            >>> company_data = {
            ...     'name': 'TechCorp',
            ...     'sector': 'Technology',
            ...     'financials': {'revenue': 1000000, 'growth_rate': 0.5},
            ...     'ipo_details': {'price_range': '15-17', 'date': '2025-11-01'}
            ... }
            >>> result = await analyzer.analyze_ipo(company_data)
        """
        company_summary = json.dumps(company_data, indent=2)

        prompt = f"""Analyze the following IPO opportunity and provide a comprehensive assessment.

Company Data:
{company_summary}

Provide a detailed IPO analysis including:
1. Overall score (0-100)
2. Investment recommendation (Strong Buy, Buy, Hold, Avoid)
3. Risk level (Low, Medium, High)
4. Key positive factors
5. Concerns and risks
6. Price target if applicable

Format your response as JSON:
{{
    "score": <0-100>,
    "recommendation": "<recommendation>",
    "risk_level": "<risk level>",
    "key_factors": ["factor1", "factor2", ...],
    "concerns": ["concern1", "concern2", ...],
    "price_target": <number or null>,
    "analysis": "<detailed analysis>"
}}
"""

        system_prompt = """You are an expert IPO analyst with deep experience evaluating pre-IPO companies.
Provide thorough, objective analysis considering market conditions, company fundamentals,
valuation, competitive landscape, and risk factors."""

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.3)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.3)

        ensemble_score, confidence, individual_scores = self._calculate_ensemble_ipo_score(
            responses
        )

        # Aggregate recommendations and factors
        all_factors = []
        all_concerns = []
        all_recommendations = []
        all_risk_levels = []
        price_targets = []
        individual_analyses = {}

        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    individual_analyses[response.model] = data

                    if "key_factors" in data:
                        all_factors.extend(data["key_factors"])
                    if "concerns" in data:
                        all_concerns.extend(data["concerns"])
                    if "recommendation" in data:
                        all_recommendations.append(data["recommendation"])
                    if "risk_level" in data:
                        all_risk_levels.append(data["risk_level"])
                    if "price_target" in data and data["price_target"]:
                        price_targets.append(data["price_target"])
                except Exception as e:
                    logger.warning(f"Error parsing IPO analysis from {response.model}: {str(e)}")

        # Determine ensemble recommendation based on score
        if ensemble_score >= 80:
            recommendation = "Strong Buy"
        elif ensemble_score >= 65:
            recommendation = "Buy"
        elif ensemble_score >= 50:
            recommendation = "Hold"
        else:
            recommendation = "Avoid"

        # Determine risk level
        risk_counts: dict[str, int] = {}
        for risk in all_risk_levels:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        risk_level = max(risk_counts.items(), key=lambda x: x[1])[0] if risk_counts else "Medium"

        # Average price target
        avg_price_target = sum(price_targets) / len(price_targets) if price_targets else None

        return {
            "score": ensemble_score,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "key_factors": list(set(all_factors))[:10],  # Top 10 unique factors
            "concerns": list(set(all_concerns))[:10],  # Top 10 unique concerns
            "price_target": avg_price_target,
            "confidence": confidence,
            "individual_scores": individual_scores,
            "individual_analyses": individual_analyses,
            "timestamp": time.time(),
        }

    async def analyze_stock(self, symbol: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a stock and provide trading recommendations.

        Args:
            symbol: Stock ticker symbol
            data: Dictionary containing:
                - price_data: Historical price data
                - technical_indicators: Technical analysis indicators
                - fundamentals: Fundamental metrics
                - news: Recent news articles

        Returns:
            Dictionary containing analysis results

        Example:
            >>> data = {
            ...     'price_data': {'current': 150, 'high_52w': 180, 'low_52w': 120},
            ...     'technical_indicators': {'rsi': 65, 'macd': 'bullish'},
            ...     'news': [...]
            ... }
            >>> result = await analyzer.analyze_stock('AAPL', data)
        """
        data_summary = json.dumps(data, indent=2)

        prompt = f"""Analyze the following stock and provide trading recommendations.

Symbol: {symbol}

Data:
{data_summary}

Provide a comprehensive stock analysis including:
1. Sentiment score (-1.0 to 1.0)
2. Recommendation (Strong Buy, Buy, Hold, Sell, Strong Sell)
3. Target price
4. Risk assessment
5. Key insights

Format your response as JSON:
{{
    "sentiment": <-1.0 to 1.0>,
    "recommendation": "<recommendation>",
    "target_price": <number or null>,
    "risk_assessment": "<assessment>",
    "key_insights": ["insight1", "insight2", ...],
    "analysis": "<detailed analysis>"
}}
"""

        system_prompt = """You are an expert stock analyst with expertise in technical analysis,
fundamental analysis, and market sentiment. Provide objective, actionable recommendations."""

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.3)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.3)

        ensemble_sentiment, confidence, individual_scores = self._calculate_ensemble_sentiment(
            responses
        )

        # Aggregate results
        all_insights = []
        all_recommendations = []
        target_prices = []

        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "key_insights" in data:
                        all_insights.extend(data["key_insights"])
                    if "recommendation" in data:
                        all_recommendations.append(data["recommendation"])
                    if "target_price" in data and data["target_price"]:
                        target_prices.append(data["target_price"])
                except Exception as e:
                    logger.warning(f"Error parsing stock analysis: {str(e)}")

        # Determine recommendation from sentiment
        if ensemble_sentiment >= 0.6:
            recommendation = "Strong Buy"
        elif ensemble_sentiment >= 0.2:
            recommendation = "Buy"
        elif ensemble_sentiment >= -0.2:
            recommendation = "Hold"
        elif ensemble_sentiment >= -0.6:
            recommendation = "Sell"
        else:
            recommendation = "Strong Sell"

        avg_target = sum(target_prices) / len(target_prices) if target_prices else None

        return {
            "symbol": symbol,
            "sentiment": ensemble_sentiment,
            "recommendation": recommendation,
            "target_price": avg_target,
            "risk_assessment": (
                "High"
                if abs(ensemble_sentiment) > 0.7
                else "Medium"
                if abs(ensemble_sentiment) > 0.3
                else "Low"
            ),
            "key_insights": list(set(all_insights))[:10],
            "confidence": confidence,
            "individual_scores": individual_scores,
            "timestamp": time.time(),
        }

    async def get_market_outlook(self) -> dict[str, Any]:
        """
        Generate overall market outlook and sentiment.

        Returns:
            Dictionary containing:
                - overall_sentiment: Market sentiment score (-1.0 to 1.0)
                - trend: Market trend (Bullish, Bearish, Neutral)
                - key_drivers: List of key market drivers
                - risks: List of market risks
                - opportunities: List of opportunities
                - timeframe: Analysis timeframe
                - confidence: Confidence level

        Example:
            >>> outlook = await analyzer.get_market_outlook()
            >>> print(f"Market trend: {outlook['trend']}")
        """
        prompt = """Provide a comprehensive outlook on the current market conditions.

Analyze:
1. Overall market sentiment and trend
2. Key drivers influencing the market
3. Major risks and concerns
4. Investment opportunities
5. Short-term and medium-term outlook

Format your response as JSON:
{
    "sentiment": <-1.0 to 1.0>,
    "trend": "<Bullish/Bearish/Neutral>",
    "key_drivers": ["driver1", "driver2", ...],
    "risks": ["risk1", "risk2", ...],
    "opportunities": ["opp1", "opp2", ...],
    "short_term_outlook": "<outlook>",
    "medium_term_outlook": "<outlook>",
    "analysis": "<detailed analysis>"
}
"""

        system_prompt = """You are a senior market strategist with expertise in macroeconomic analysis,
market trends, and investment strategy. Provide comprehensive, balanced market outlook."""

        if self.use_async:
            responses = await self._query_all_llms_async(prompt, system_prompt, temperature=0.5)
        else:
            responses = self._query_all_llms_sync(prompt, system_prompt, temperature=0.5)

        ensemble_sentiment, confidence, individual_scores = self._calculate_ensemble_sentiment(
            responses
        )

        # Aggregate insights
        all_drivers = []
        all_risks = []
        all_opportunities = []
        all_trends = []

        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "key_drivers" in data:
                        all_drivers.extend(data["key_drivers"])
                    if "risks" in data:
                        all_risks.extend(data["risks"])
                    if "opportunities" in data:
                        all_opportunities.extend(data["opportunities"])
                    if "trend" in data:
                        all_trends.append(data["trend"])
                except Exception as e:
                    logger.warning(f"Error parsing market outlook: {str(e)}")

        # Determine trend from sentiment
        if ensemble_sentiment >= 0.3:
            trend = "Bullish"
        elif ensemble_sentiment <= -0.3:
            trend = "Bearish"
        else:
            trend = "Neutral"

        return {
            "overall_sentiment": ensemble_sentiment,
            "trend": trend,
            "key_drivers": list(set(all_drivers))[:8],
            "risks": list(set(all_risks))[:8],
            "opportunities": list(set(all_opportunities))[:8],
            "timeframe": "Short to Medium Term (1-6 months)",
            "confidence": confidence,
            "individual_scores": individual_scores,
            "timestamp": time.time(),
        }

    def close(self):
        """Close the client connections."""
        if hasattr(self, "client") and self.client:
            # AsyncOpenAI doesn't require explicit closing
            pass
        logger.info("MultiLLMAnalyzer closed")


@dataclass
class CouncilResponse:
    """Container for LLM Council final response."""

    final_answer: str
    confidence: float
    individual_responses: dict[str, str]
    reviews: dict[str, dict[str, Any]]
    rankings: dict[str, list[str]]
    chairman_reasoning: str
    metadata: dict[str, Any]


class LLMCouncilAnalyzer:
    """
    LLM Council Analyzer - Multi-stage consensus system for trading decisions.

    Implements the LLM Council pattern from Karpathy's llm-council:
    1. Stage 1: First opinions - Query all LLMs individually
    2. Stage 2: Review - Each LLM reviews and ranks other responses (anonymized)
    3. Stage 3: Chairman - Designated LLM compiles final response

    This provides higher quality decisions through peer review and consensus.
    """

    def __init__(
        self,
        api_key: str | None = None,
        council_models: list[LLMModel] | None = None,
        chairman_model: LLMModel | None = None,
        max_retries: int = 3,
        timeout: int = 60,
        rate_limit_delay: float = 2.0,  # Increased from 1.0 to reduce 429/500 errors
        use_async: bool = True,
    ):
        """
        Initialize the LLM Council Analyzer.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            council_models: List of models in the council (defaults to latest models)
            chairman_model: Model to use as chairman (defaults to Gemini 3 Pro)
            max_retries: Maximum retry attempts per request
            timeout: Request timeout in seconds
            rate_limit_delay: Delay between requests to avoid rate limits
            use_async: Whether to use async client (recommended)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key must be provided or set in OPENROUTER_API_KEY env var"
            )

        self.council_models = council_models or [
            LLMModel.GEMINI_3_PRO,
            LLMModel.CLAUDE_SONNET_4,
            LLMModel.GPT4O,
        ]
        deepseek_enabled_env = os.getenv("OPENROUTER_ENABLE_DEEPSEEK", "false").lower()
        deepseek_enabled = deepseek_enabled_env not in {"0", "false", "off", "no"}
        if deepseek_enabled and LLMModel.DEEPSEEK_R1 not in self.council_models:
            self.council_models.append(LLMModel.DEEPSEEK_R1)

        self.chairman_model = chairman_model or LLMModel.GEMINI_3_PRO
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.use_async = use_async

        # Initialize OpenAI client with OpenRouter (with Helicone + LangSmith observability if enabled)
        # Use observability wrapper if available (handles Helicone gateway + LangSmith tracing)
        try:
            from src.utils.langsmith_wrapper import (
                get_traced_async_openai_client,
                get_traced_openai_client,
            )

            if use_async:
                # Wrapper auto-routes through Helicone if HELICONE_API_KEY is set
                self.client = get_traced_async_openai_client(api_key=self.api_key)
            else:
                self.sync_client = get_traced_openai_client(api_key=self.api_key)
        except ImportError:
            # Fallback to regular client with Helicone support if wrapper not available
            helicone_key = os.getenv("HELICONE_API_KEY")
            if helicone_key:
                base_url = "https://openrouter.helicone.ai/api/v1"
                default_headers = {"Helicone-Auth": f"Bearer {helicone_key}"}
            else:
                base_url = "https://openrouter.ai/api/v1"
                default_headers = None

            if use_async:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=default_headers,
                )
            else:
                self.sync_client = OpenAI(
                    api_key=self.api_key,
                    base_url=base_url,
                    timeout=timeout,
                    default_headers=default_headers,
                )

        if deepseek_enabled:
            logger.info(
                "LLM Council: DeepSeek (model=%s) enabled via OPENROUTER_ENABLE_DEEPSEEK",
                LLMModel.DEEPSEEK_R1.value,
            )

        logger.info(
            f"Initialized LLMCouncilAnalyzer with council: {[m.value for m in self.council_models]}"
        )
        logger.info(f"Chairman model: {self.chairman_model.value}")

    async def _query_llm_async(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """Query a single LLM with retry logic (reuses MultiLLMAnalyzer logic)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                response = await self.client.chat.completions.create(
                    model=model.value,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                latency = time.time() - start_time

                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0

                logger.debug(f"Successfully queried {model.value} in {latency:.2f}s")

                return LLMResponse(
                    model=model.value,
                    content=content,
                    tokens_used=tokens_used,
                    latency=latency,
                    success=True,
                )

            except Exception as e:
                # Enhanced error logging to identify specific failure patterns
                error_type = type(e).__name__
                error_msg = str(e)
                status_code = getattr(e, "status_code", None)
                if status_code:
                    logger.warning(
                        f"[Council] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: HTTP {status_code} - {error_type}: {error_msg}"
                    )
                else:
                    logger.warning(
                        f"[Council] Attempt {attempt + 1}/{self.max_retries} failed for "
                        f"{model.value}: {error_type}: {error_msg}"
                    )

                if attempt == self.max_retries - 1:
                    return LLMResponse(
                        model=model.value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=f"{error_type}: {error_msg}",
                    )

                # Exponential backoff
                await asyncio.sleep(2**attempt * self.rate_limit_delay)

    async def _stage1_first_opinions(
        self, query: str, system_prompt: str | None = None
    ) -> dict[str, LLMResponse]:
        """
        Stage 1: Get first opinions from all council members.

        Args:
            query: The trading question/query
            system_prompt: Optional system prompt

        Returns:
            Dictionary mapping model names to their responses
        """
        logger.info("Stage 1: Collecting first opinions from council members")

        async def query_with_delay(model, delay: float):
            """Query a model after a staggered delay to avoid rate limits."""
            if delay > 0:
                await asyncio.sleep(delay)
            return await self._query_llm_async(
                model=model,
                prompt=query,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000,
            )

        # Stagger requests to avoid 429 rate limit errors
        tasks = [
            query_with_delay(model, i * self.rate_limit_delay)
            for i, model in enumerate(self.council_models)
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        first_opinions = {}
        for i, response in enumerate(responses):
            model_name = self.council_models[i].value
            if isinstance(response, Exception):
                logger.error(f"Error in Stage 1 for {model_name}: {str(response)}")
                first_opinions[model_name] = LLMResponse(
                    model=model_name,
                    content="",
                    tokens_used=0,
                    latency=0,
                    success=False,
                    error=str(response),
                )
            else:
                first_opinions[model_name] = response

        logger.info(
            f"Stage 1 complete: {len([r for r in first_opinions.values() if r.success])} successful responses"
        )
        return first_opinions

    async def _stage2_review(
        self, first_opinions: dict[str, LLMResponse], query: str
    ) -> dict[str, dict[str, Any]]:
        """
        Stage 2: Each LLM reviews and ranks other responses (anonymized).

        Args:
            first_opinions: Dictionary of first opinions from Stage 1
            query: Original query for context

        Returns:
            Dictionary mapping reviewer model to their review and rankings
        """
        logger.info("Stage 2: Council members reviewing each other's responses")

        # Anonymize responses by assigning random IDs
        import random
        import string

        anonymous_responses = {}
        model_to_id = {}
        id_to_model = {}

        for model_name, response in first_opinions.items():
            if response.success:
                # Generate random anonymous ID
                anonymous_id = "".join(
                    random.choices(string.ascii_uppercase, k=3)
                )  # e.g., "ABC", "XYZ"
                anonymous_responses[anonymous_id] = response.content
                model_to_id[model_name] = anonymous_id
                id_to_model[anonymous_id] = model_name

        if len(anonymous_responses) < 2:
            logger.warning("Not enough responses for review stage")
            return {}

        # Build review prompt with anonymized responses
        responses_text = "\n\n".join(
            [f"Response {anon_id}:\n{content}" for anon_id, content in anonymous_responses.items()]
        )

        review_prompt = f"""You are part of an LLM Council evaluating trading decisions.

Original Query:
{query}

Here are anonymous responses from other council members (identities hidden):

{responses_text}

Your task:
1. Review each response for accuracy, insight, and reasoning quality
2. Rank them from best to worst (most accurate and insightful first)
3. Provide brief reasoning for your ranking

Format your response as JSON:
{{
    "rankings": ["Response_ID_1", "Response_ID_2", "Response_ID_3", ...],
    "reasoning": "Brief explanation of your ranking",
    "strengths": {{
        "Response_ID_1": "What makes this response strong",
        ...
    }},
    "weaknesses": {{
        "Response_ID_1": "What could be improved",
        ...
    }}
}}
"""

        system_prompt_review = """You are an expert financial analyst participating in a peer review process.
Evaluate responses objectively based on accuracy, insight, and reasoning quality.
Be honest and critical in your assessment."""

        async def review_with_delay(model, delay: float):
            """Query review with staggered delay to avoid rate limits."""
            if delay > 0:
                await asyncio.sleep(delay)
            return await self._query_llm_async(
                model=model,
                prompt=review_prompt,
                system_prompt=system_prompt_review,
                temperature=0.5,
                max_tokens=2000,
            )

        # Each council member reviews (excluding themselves) with staggered delays
        review_tasks = []
        delay_idx = 0
        for model in self.council_models:
            if model.value in first_opinions and first_opinions[model.value].success:
                review_tasks.append(review_with_delay(model, delay_idx * self.rate_limit_delay))
                delay_idx += 1
            else:
                review_tasks.append(None)

        review_responses = await asyncio.gather(
            *[task for task in review_tasks if task is not None],
            return_exceptions=True,
        )

        reviews = {}
        review_idx = 0
        for i, model in enumerate(self.council_models):
            if review_tasks[i] is not None:
                if isinstance(review_responses[review_idx], Exception):
                    logger.error(
                        f"Review failed for {model.value}: {str(review_responses[review_idx])}"
                    )
                else:
                    review_content = review_responses[review_idx].content
                    try:
                        # Try to parse JSON response
                        review_data = json.loads(review_content)
                        reviews[model.value] = {
                            "rankings": review_data.get("rankings", []),
                            "reasoning": review_data.get("reasoning", ""),
                            "strengths": review_data.get("strengths", {}),
                            "weaknesses": review_data.get("weaknesses", {}),
                            "raw_response": review_content,
                        }
                    except json.JSONDecodeError:
                        # Fallback: extract rankings from text
                        reviews[model.value] = {
                            "rankings": [],
                            "reasoning": review_content,
                            "raw_response": review_content,
                        }
                review_idx += 1

        logger.info(f"Stage 2 complete: {len(reviews)} reviews collected")
        return reviews

    async def _stage3_chairman(
        self,
        query: str,
        first_opinions: dict[str, LLMResponse],
        reviews: dict[str, dict[str, Any]],
    ) -> str:
        """
        Stage 3: Chairman compiles final response from all inputs.

        Args:
            query: Original query
            first_opinions: Stage 1 responses
            reviews: Stage 2 reviews and rankings

        Returns:
            Final compiled response from chairman
        """
        logger.info("Stage 3: Chairman compiling final response")

        # Build comprehensive prompt for chairman
        opinions_text = "\n\n".join(
            [
                f"**{model_name}**:\n{response.content}"
                for model_name, response in first_opinions.items()
                if response.success
            ]
        )

        reviews_text = "\n\n".join(
            [
                f"**{reviewer}** ranked responses and noted:\n{review.get('reasoning', '')}"
                for reviewer, review in reviews.items()
            ]
        )

        chairman_prompt = f"""You are the Chairman of an LLM Council making a final trading decision.

Original Query:
{query}

**Council Member Opinions (Stage 1):**
{opinions_text}

**Peer Reviews (Stage 2):**
{reviews_text}

Your task as Chairman:
1. Synthesize all opinions and reviews
2. Identify consensus points and disagreements
3. Produce a final, comprehensive answer that incorporates the best insights
4. Clearly state your confidence level and reasoning

Provide a well-structured final response that:
- Answers the original query comprehensively
- Incorporates the best insights from council members
- Addresses any disagreements or uncertainties
- Provides actionable recommendations if applicable
"""

        system_prompt_chairman = """You are the Chairman of an LLM Council, responsible for synthesizing
multiple expert opinions into a final, high-quality decision. Your role is to:
- Identify the strongest arguments and insights
- Resolve disagreements through careful analysis
- Produce a consensus-driven final answer
- Be transparent about confidence levels and uncertainties"""

        chairman_response = await self._query_llm_async(
            model=self.chairman_model,
            prompt=chairman_prompt,
            system_prompt=system_prompt_chairman,
            temperature=0.7,
            max_tokens=3000,
        )

        if chairman_response.success:
            logger.info("Stage 3 complete: Chairman response generated")
            return chairman_response.content
        else:
            logger.error(f"Chairman failed: {chairman_response.error}")
            # Fallback: return best-ranked response from reviews
            return self._fallback_response(first_opinions, reviews)

    def _fallback_response(
        self,
        first_opinions: dict[str, LLMResponse],
        reviews: dict[str, dict[str, Any]],
    ) -> str:
        """Fallback: Use highest-ranked response if chairman fails."""
        # Simple fallback: use first successful response
        for model_name, response in first_opinions.items():
            if response.success:
                return f"[Fallback] {model_name}:\n{response.content}"
        return "Error: No valid responses available"

    async def query_council(
        self,
        query: str,
        system_prompt: str | None = None,
        include_reviews: bool = True,
    ) -> CouncilResponse:
        """
        Execute full LLM Council process: First opinions → Review → Chairman.

        Args:
            query: The trading question/query to analyze
            system_prompt: Optional system prompt for Stage 1
            include_reviews: Whether to run Stage 2 review (adds latency but improves quality)

        Returns:
            CouncilResponse with final answer and all intermediate data
        """
        start_time = time.time()

        # Stage 1: First opinions
        first_opinions = await self._stage1_first_opinions(query, system_prompt)

        # Stage 2: Review (optional but recommended)
        reviews = {}
        if include_reviews and len([r for r in first_opinions.values() if r.success]) >= 2:
            reviews = await self._stage2_review(first_opinions, query)
        else:
            logger.info("Skipping Stage 2 review (not enough responses or disabled)")

        # Stage 3: Chairman compiles final answer
        final_answer = await self._stage3_chairman(query, first_opinions, reviews)

        # Calculate confidence based on agreement
        successful_responses = [r for r in first_opinions.values() if r.success]
        confidence = (
            len(successful_responses) / len(self.council_models) if self.council_models else 0.0
        )

        # Extract individual responses
        individual_responses = {
            model_name: response.content
            for model_name, response in first_opinions.items()
            if response.success
        }

        # Extract rankings from reviews
        rankings = {reviewer: review.get("rankings", []) for reviewer, review in reviews.items()}

        total_time = time.time() - start_time

        logger.info(f"LLM Council process complete in {total_time:.2f}s")

        return CouncilResponse(
            final_answer=final_answer,
            confidence=confidence,
            individual_responses=individual_responses,
            reviews=reviews,
            rankings=rankings,
            chairman_reasoning=final_answer,
            metadata={
                "query": query,
                "council_models": [m.value for m in self.council_models],
                "chairman_model": self.chairman_model.value,
                "total_time": total_time,
                "timestamp": time.time(),
            },
        )

    async def analyze_trading_decision(
        self,
        symbol: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> CouncilResponse:
        """
        Analyze a trading decision using the LLM Council.

        Args:
            symbol: Stock symbol to analyze
            market_data: Market data (price, indicators, etc.)
            context: Additional context (portfolio, risk limits, etc.)

        Returns:
            CouncilResponse with trading recommendation
        """
        context_str = ""
        if context:
            context_str = f"\n\nAdditional Context:\n{json.dumps(context, indent=2)}"

        query = f"""Analyze the following trading opportunity and provide a recommendation.

Symbol: {symbol}

Market Data:
{json.dumps(market_data, indent=2)}
{context_str}

Provide:
1. Trading recommendation (BUY/SELL/HOLD)
2. Confidence level (0-1)
3. Position size recommendation
4. Risk assessment
5. Key factors supporting your decision
6. Potential concerns or risks

Format your response clearly with reasoning."""
        system_prompt = """You are an expert trading analyst. Provide objective, data-driven
trading recommendations based on technical analysis, market conditions, and risk management principles."""

        return await self.query_council(query, system_prompt, include_reviews=True)

    def close(self):
        """Close the client connections."""
        if hasattr(self, "client") and self.client:
            pass
        logger.info("LLMCouncilAnalyzer closed")


# Convenience functions for synchronous usage
def create_analyzer(api_key: str | None = None, use_async: bool = True) -> MultiLLMAnalyzer:
    """
    Create a MultiLLMAnalyzer instance.

    Args:
        api_key: OpenRouter API key
        use_async: Whether to use async mode

    Returns:
        Configured MultiLLMAnalyzer instance
    """
    return MultiLLMAnalyzer(api_key=api_key, use_async=use_async)


# Example usage
if __name__ == "__main__":
    import asyncio

    async def main():
        # Initialize analyzer
        analyzer = MultiLLMAnalyzer()

        # Example: Get ensemble sentiment
        market_data = {
            "symbol": "AAPL",
            "price": 150.0,
            "change_percent": 2.5,
            "volume": 50000000,
            "rsi": 65,
            "macd": "bullish",
        }

        news = [
            {
                "title": "Apple announces new AI features",
                "content": "Apple unveiled significant AI capabilities...",
                "source": "TechNews",
                "sentiment": "positive",
            },
            {
                "title": "Strong quarterly earnings reported",
                "content": "Apple beat expectations with...",
                "source": "FinanceDaily",
                "sentiment": "positive",
            },
        ]

        # Get sentiment
        sentiment = await analyzer.get_ensemble_sentiment(market_data, news)
        print(f"Ensemble Sentiment: {sentiment:.3f}")

        # Get detailed sentiment analysis
        detailed = await analyzer.get_ensemble_sentiment_detailed(market_data, news)
        print("\nDetailed Analysis:")
        print(f"Score: {detailed.score:.3f}")
        print(f"Confidence: {detailed.confidence:.3f}")
        print(f"Individual Scores: {detailed.individual_scores}")

        # Analyze IPO
        ipo_data = {
            "name": "TechCorp",
            "sector": "Technology",
            "financials": {
                "revenue": 500000000,
                "growth_rate": 0.45,
                "profit_margin": 0.15,
            },
            "description": "Leading AI software company",
            "ipo_details": {
                "price_range": "15-17",
                "shares": 10000000,
                "date": "2025-11-15",
            },
        }

        ipo_analysis = await analyzer.analyze_ipo(ipo_data)
        print("\nIPO Analysis:")
        print(f"Score: {ipo_analysis['score']}/100")
        print(f"Recommendation: {ipo_analysis['recommendation']}")
        print(f"Risk Level: {ipo_analysis['risk_level']}")

        # Get market outlook
        outlook = await analyzer.get_market_outlook()
        print("\nMarket Outlook:")
        print(f"Trend: {outlook['trend']}")
        print(f"Sentiment: {outlook['overall_sentiment']:.3f}")
        print(f"Key Drivers: {outlook['key_drivers'][:3]}")

        analyzer.close()

    # Run example
    asyncio.run(main())
