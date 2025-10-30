"""
Multi-LLM Analysis Engine for Trading System

This module provides a comprehensive analysis engine that queries multiple LLMs
(Claude 3.5 Sonnet, GPT-4o, Gemini 2.0 Flash) through OpenRouter API to generate
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
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion

# Configure logging
logger = logging.getLogger(__name__)


class LLMModel(Enum):
    """Available LLM models through OpenRouter."""

    CLAUDE_35_SONNET = "anthropic/claude-3.5-sonnet"
    GPT4O = "openai/gpt-4o"
    GEMINI_2_FLASH = "google/gemini-2.0-flash-exp:free"


@dataclass
class LLMResponse:
    """Container for LLM response data."""

    model: str
    content: str
    tokens_used: int
    latency: float
    success: bool
    error: Optional[str] = None


@dataclass
class SentimentAnalysis:
    """Container for sentiment analysis results."""

    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasoning: str
    individual_scores: Dict[str, float]
    metadata: Dict[str, Any]


@dataclass
class IPOAnalysis:
    """Container for IPO analysis results."""

    score: int  # 0-100
    recommendation: str  # "Strong Buy", "Buy", "Hold", "Avoid"
    risk_level: str  # "Low", "Medium", "High"
    key_factors: List[str]
    concerns: List[str]
    price_target: Optional[float]
    confidence: float
    individual_analyses: Dict[str, Dict[str, Any]]


@dataclass
class StockAnalysis:
    """Container for stock analysis results."""

    symbol: str
    sentiment: float
    recommendation: str
    target_price: Optional[float]
    risk_assessment: str
    key_insights: List[str]
    confidence: float
    timestamp: float


@dataclass
class MarketOutlook:
    """Container for market outlook results."""

    overall_sentiment: float
    trend: str  # "Bullish", "Bearish", "Neutral"
    key_drivers: List[str]
    risks: List[str]
    opportunities: List[str]
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
        api_key: Optional[str] = None,
        models: Optional[List[LLMModel]] = None,
        max_retries: int = 3,
        timeout: int = 60,
        rate_limit_delay: float = 0.5,
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
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key must be provided or set in OPENROUTER_API_KEY env var"
            )

        self.models = models or [
            LLMModel.CLAUDE_35_SONNET,
            LLMModel.GPT4O,
            LLMModel.GEMINI_2_FLASH,
        ]
        self.max_retries = max_retries
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.use_async = use_async

        # Initialize OpenAI client with OpenRouter base URL
        base_url = "https://openrouter.ai/api/v1"

        if use_async:
            self.client = AsyncOpenAI(
                api_key=self.api_key, base_url=base_url, timeout=timeout
            )
        else:
            self.sync_client = OpenAI(
                api_key=self.api_key, base_url=base_url, timeout=timeout
            )

        logger.info(
            f"Initialized MultiLLMAnalyzer with models: {[m.value for m in self.models]}"
        )

    async def _query_llm_async(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: Optional[str] = None,
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
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {model.value}: {str(e)}"
                )

                if attempt == self.max_retries - 1:
                    return LLMResponse(
                        model=model.value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=str(e),
                    )

                # Exponential backoff
                await asyncio.sleep(2**attempt * self.rate_limit_delay)

    def _query_llm_sync(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: Optional[str] = None,
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
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {model.value}: {str(e)}"
                )

                if attempt == self.max_retries - 1:
                    return LLMResponse(
                        model=model.value,
                        content="",
                        tokens_used=0,
                        latency=0,
                        success=False,
                        error=str(e),
                    )

                # Exponential backoff
                time.sleep(2**attempt * self.rate_limit_delay)

    async def _query_all_llms_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> List[LLMResponse]:
        """
        Query all configured LLMs in parallel.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            List of LLMResponse objects
        """
        tasks = [
            self._query_llm_async(model, prompt, system_prompt, temperature, max_tokens)
            for model in self.models
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
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> List[LLMResponse]:
        """Synchronous version of _query_all_llms_async."""
        responses = []
        for model in self.models:
            response = self._query_llm_sync(
                model, prompt, system_prompt, temperature, max_tokens
            )
            responses.append(response)
            time.sleep(self.rate_limit_delay)
        return responses

    def _parse_sentiment_score(self, content: str) -> Optional[float]:
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

    def _parse_ipo_score(self, content: str) -> Optional[int]:
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
        self, responses: List[LLMResponse]
    ) -> Tuple[float, float, Dict[str, float]]:
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
            variance = sum((s - ensemble_score) ** 2 for s in valid_scores) / len(
                valid_scores
            )
            # Confidence inversely proportional to variance
            confidence = max(0.0, min(1.0, 1.0 - variance))
        else:
            confidence = 0.5  # Low confidence with single model

        return ensemble_score, confidence, individual_scores

    def _calculate_ensemble_ipo_score(
        self, responses: List[LLMResponse]
    ) -> Tuple[int, float, Dict[str, int]]:
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
            variance = sum((s - ensemble_score) ** 2 for s in valid_scores) / len(
                valid_scores
            )
            # Normalize variance to 0-1 range (max variance is 50^2 = 2500)
            confidence = max(0.0, min(1.0, 1.0 - variance / 2500))
        else:
            confidence = 0.5

        return ensemble_score, confidence, individual_scores

    async def get_ensemble_sentiment(
        self, market_data: Dict[str, Any], news: List[Dict[str, Any]]
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
            responses = await self._query_all_llms_async(
                prompt, system_prompt, temperature=0.3
            )
        else:
            responses = self._query_all_llms_sync(
                prompt, system_prompt, temperature=0.3
            )

        ensemble_score, confidence, individual_scores = (
            self._calculate_ensemble_sentiment(responses)
        )

        logger.info(
            f"Ensemble sentiment: {ensemble_score:.3f} (confidence: {confidence:.3f})"
        )
        logger.info(f"Individual scores: {individual_scores}")

        return ensemble_score

    async def get_ensemble_sentiment_detailed(
        self, market_data: Dict[str, Any], news: List[Dict[str, Any]]
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
            responses = await self._query_all_llms_async(
                prompt, system_prompt, temperature=0.3
            )
        else:
            responses = self._query_all_llms_sync(
                prompt, system_prompt, temperature=0.3
            )

        ensemble_score, confidence, individual_scores = (
            self._calculate_ensemble_sentiment(responses)
        )

        # Extract reasoning from successful responses
        reasoning_parts = []
        for response in responses:
            if response.success and response.content:
                try:
                    data = json.loads(response.content)
                    if "reasoning" in data:
                        reasoning_parts.append(
                            f"[{response.model}] {data['reasoning']}"
                        )
                except:
                    pass

        reasoning = (
            "\n\n".join(reasoning_parts)
            if reasoning_parts
            else "No detailed reasoning available"
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

    async def analyze_ipo(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
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
            responses = await self._query_all_llms_async(
                prompt, system_prompt, temperature=0.3
            )
        else:
            responses = self._query_all_llms_sync(
                prompt, system_prompt, temperature=0.3
            )

        ensemble_score, confidence, individual_scores = (
            self._calculate_ensemble_ipo_score(responses)
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
                    logger.warning(
                        f"Error parsing IPO analysis from {response.model}: {str(e)}"
                    )

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
        risk_counts = {}
        for risk in all_risk_levels:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        risk_level = (
            max(risk_counts.items(), key=lambda x: x[1])[0] if risk_counts else "Medium"
        )

        # Average price target
        avg_price_target = (
            sum(price_targets) / len(price_targets) if price_targets else None
        )

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

    async def analyze_stock(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
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
            responses = await self._query_all_llms_async(
                prompt, system_prompt, temperature=0.3
            )
        else:
            responses = self._query_all_llms_sync(
                prompt, system_prompt, temperature=0.3
            )

        ensemble_sentiment, confidence, individual_scores = (
            self._calculate_ensemble_sentiment(responses)
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
                else "Medium" if abs(ensemble_sentiment) > 0.3 else "Low"
            ),
            "key_insights": list(set(all_insights))[:10],
            "confidence": confidence,
            "individual_scores": individual_scores,
            "timestamp": time.time(),
        }

    async def get_market_outlook(self) -> Dict[str, Any]:
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
            responses = await self._query_all_llms_async(
                prompt, system_prompt, temperature=0.5
            )
        else:
            responses = self._query_all_llms_sync(
                prompt, system_prompt, temperature=0.5
            )

        ensemble_sentiment, confidence, individual_scores = (
            self._calculate_ensemble_sentiment(responses)
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


# Convenience functions for synchronous usage
def create_analyzer(
    api_key: Optional[str] = None, use_async: bool = True
) -> MultiLLMAnalyzer:
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
        print(f"\nDetailed Analysis:")
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
        print(f"\nIPO Analysis:")
        print(f"Score: {ipo_analysis['score']}/100")
        print(f"Recommendation: {ipo_analysis['recommendation']}")
        print(f"Risk Level: {ipo_analysis['risk_level']}")

        # Get market outlook
        outlook = await analyzer.get_market_outlook()
        print(f"\nMarket Outlook:")
        print(f"Trend: {outlook['trend']}")
        print(f"Sentiment: {outlook['overall_sentiment']:.3f}")
        print(f"Key Drivers: {outlook['key_drivers'][:3]}")

        analyzer.close()

    # Run example
    asyncio.run(main())
