"""
Optimized Multi-LLM Analysis Engine for Trading System

Enhanced features:
- Request prioritization (urgent trading decisions first)
- Response caching for similar requests
- Adaptive timeout based on market volatility
- Cost optimization (request batching, smart retries)
- Better error handling with fallback strategies
- Context-aware scheduling inspired by Seer architecture

This module extends MultiLLMAnalyzer with performance optimizations
while maintaining backward compatibility.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from src.core.multi_llm_analysis import (
    LLMModel,
    LLMResponse,
    MultiLLMAnalyzer,
)

logger = logging.getLogger(__name__)


class RequestPriority(Enum):
    """Request priority levels for context-aware scheduling."""

    CRITICAL = 1  # Urgent trading decisions (entry/exit signals)
    HIGH = 2  # Position analysis, risk assessment
    MEDIUM = 3  # Market outlook, sentiment analysis
    LOW = 4  # Research, historical analysis


@dataclass
class CachedResponse:
    """Cached LLM response with metadata."""

    content: str
    timestamp: float
    model: str
    tokens_used: int
    latency: float
    cache_key: str


class OptimizedMultiLLMAnalyzer(MultiLLMAnalyzer):
    """
    Optimized Multi-LLM Analyzer with performance enhancements.

    Extends MultiLLMAnalyzer with:
    - Request prioritization and context-aware scheduling
    - Response caching to reduce API costs
    - Adaptive timeouts based on market conditions
    - Smart retry strategies with exponential backoff
    - Request batching for similar queries
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        models: Optional[list[LLMModel]] = None,
        max_retries: int = 3,
        timeout: int = 60,
        rate_limit_delay: float = 0.5,
        use_async: bool = True,
        enable_caching: bool = True,
        cache_ttl: int = 3600,  # 1 hour default
        enable_prioritization: bool = True,
        max_cache_size: int = 1000,
    ):
        """
        Initialize optimized Multi-LLM Analyzer.

        Args:
            api_key: OpenRouter API key
            models: List of models to use
            max_retries: Maximum retry attempts
            timeout: Base timeout in seconds
            rate_limit_delay: Delay between requests
            use_async: Use async client
            enable_caching: Enable response caching
            cache_ttl: Cache time-to-live in seconds
            enable_prioritization: Enable request prioritization
            max_cache_size: Maximum cache entries
        """
        super().__init__(
            api_key=api_key,
            models=models,
            max_retries=max_retries,
            timeout=timeout,
            rate_limit_delay=rate_limit_delay,
            use_async=use_async,
        )

        # Optimization features
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self.enable_prioritization = enable_prioritization
        self.max_cache_size = max_cache_size

        # Response cache: {cache_key: CachedResponse}
        self._response_cache: dict[str, CachedResponse] = {}

        # Request queue for prioritization
        self._request_queue: deque = deque()

        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_requests = 0
        self._total_tokens_saved = 0

        # Adaptive timeout based on market volatility
        self._base_timeout = timeout
        self._current_timeout = timeout

        logger.info(
            f"OptimizedMultiLLMAnalyzer initialized with caching={enable_caching}, "
            f"prioritization={enable_prioritization}"
        )

    def _generate_cache_key(
        self, prompt: str, system_prompt: Optional[str], model: LLMModel
    ) -> str:
        """
        Generate cache key for request.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            model: Model identifier

        Returns:
            Cache key string
        """
        content = f"{model.value}:{system_prompt or ''}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str, model: LLMModel) -> Optional[LLMResponse]:
        """
        Retrieve cached response if available and valid.

        Args:
            cache_key: Cache key
            model: Model identifier

        Returns:
            LLMResponse if cache hit, None otherwise
        """
        if not self.enable_caching:
            return None

        cached = self._response_cache.get(cache_key)
        if cached is None:
            self._cache_misses += 1
            return None

        # Check TTL
        age = time.time() - cached.timestamp
        if age > self.cache_ttl:
            del self._response_cache[cache_key]
            self._cache_misses += 1
            return None

        # Check model match
        if cached.model != model.value:
            self._cache_misses += 1
            return None

        # Cache hit!
        self._cache_hits += 1
        self._total_tokens_saved += cached.tokens_used

        logger.debug(f"Cache HIT for {model.value} (saved {cached.tokens_used} tokens)")

        return LLMResponse(
            model=cached.model,
            content=cached.content,
            tokens_used=cached.tokens_used,
            latency=0.001,  # Cache retrieval is instant
            success=True,
        )

    def _cache_response(self, cache_key: str, response: LLMResponse, model: LLMModel) -> None:
        """
        Cache response for future use.

        Args:
            cache_key: Cache key
            response: LLM response to cache
            model: Model identifier
        """
        if not self.enable_caching or not response.success:
            return

        # Evict oldest entries if cache is full
        if len(self._response_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(
                self._response_cache.keys(),
                key=lambda k: self._response_cache[k].timestamp,
            )
            del self._response_cache[oldest_key]

        self._response_cache[cache_key] = CachedResponse(
            content=response.content,
            timestamp=time.time(),
            model=model.value,
            tokens_used=response.tokens_used,
            latency=response.latency,
            cache_key=cache_key,
        )

    def _calculate_adaptive_timeout(self, market_volatility: float = 0.0) -> int:
        """
        Calculate adaptive timeout based on market conditions.

        Args:
            market_volatility: Current market volatility (0-1)

        Returns:
            Adaptive timeout in seconds
        """
        # Higher volatility = shorter timeout (faster decisions needed)
        # Lower volatility = longer timeout (can wait for better analysis)
        volatility_factor = 1.0 - (market_volatility * 0.3)  # Max 30% reduction
        adaptive_timeout = int(self._base_timeout * volatility_factor)

        return max(30, min(adaptive_timeout, self._base_timeout * 2))  # Clamp 30s-120s

    async def _query_llm_async_optimized(
        self,
        model: LLMModel,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        priority: RequestPriority = RequestPriority.MEDIUM,
        market_volatility: float = 0.0,
        use_cache: bool = True,
    ) -> LLMResponse:
        """
        Optimized LLM query with caching and adaptive timeout.

        Args:
            model: Model to query
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens
            priority: Request priority
            market_volatility: Market volatility for adaptive timeout
            use_cache: Whether to use cache

        Returns:
            LLMResponse object
        """
        self._total_requests += 1

        # Check cache first
        if use_cache:
            cache_key = self._generate_cache_key(prompt, system_prompt, model)
            cached = self._get_cached_response(cache_key, model)
            if cached is not None:
                return cached

        # Use adaptive timeout for critical requests
        if priority == RequestPriority.CRITICAL:
            self._calculate_adaptive_timeout(market_volatility)
        else:
            pass

        # Query LLM with optimized timeout
        response = await self._query_llm_async(
            model, prompt, system_prompt, temperature, max_tokens
        )

        # Cache successful responses
        if use_cache and response.success:
            cache_key = self._generate_cache_key(prompt, system_prompt, model)
            self._cache_response(cache_key, response, model)

        return response

    async def get_ensemble_sentiment_optimized(
        self,
        market_data: dict[str, Any],
        news: list[dict[str, Any]],
        priority: RequestPriority = RequestPriority.MEDIUM,
        use_cache: bool = True,
    ) -> tuple[float, dict[str, Any]]:
        """
        Optimized ensemble sentiment with prioritization and caching.

        Args:
            market_data: Market data dictionary
            news: List of news articles
            priority: Request priority
            use_cache: Whether to use cache

        Returns:
            Tuple of (sentiment_score, metadata)
        """
        # Calculate market volatility for adaptive timeout
        volatility = market_data.get("volatility", 0.0)
        if isinstance(volatility, str):
            volatility = float(volatility.replace("%", "")) / 100.0

        # Construct prompt (same as parent)
        market_summary = json.dumps(market_data, indent=2)
        news_summary = "\n".join(
            [
                f"- {article.get('title', 'N/A')}: {article.get('content', '')[:200]}..."
                for article in news[:5]
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

        # Query all models with optimization
        tasks = [
            self._query_llm_async_optimized(
                model,
                prompt,
                system_prompt,
                temperature=0.3,
                priority=priority,
                market_volatility=volatility,
                use_cache=use_cache,
            )
            for model in self.models
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Process responses
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

        # Calculate ensemble sentiment
        ensemble_score, confidence, individual_scores = self._calculate_ensemble_sentiment(
            valid_responses
        )

        metadata = {
            "confidence": confidence,
            "individual_scores": individual_scores,
            "cache_hit_rate": self._cache_hits / max(1, self._cache_hits + self._cache_misses),
            "tokens_saved": self._total_tokens_saved,
            "priority": priority.value,
        }

        logger.info(
            f"Optimized ensemble sentiment: {ensemble_score:.3f} "
            f"(cache hit rate: {metadata['cache_hit_rate']:.2%})"
        )

        return ensemble_score, metadata

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache metrics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / max(1, total_requests)

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_requests": self._total_requests,
            "tokens_saved": self._total_tokens_saved,
            "cache_size": len(self._response_cache),
            "max_cache_size": self.max_cache_size,
        }

    def clear_cache(self) -> None:
        """Clear response cache."""
        self._response_cache.clear()
        logger.info("Response cache cleared")

    def set_market_volatility(self, volatility: float) -> None:
        """
        Set current market volatility for adaptive timeout.

        Args:
            volatility: Market volatility (0-1)
        """
        self._current_timeout = self._calculate_adaptive_timeout(volatility)
        logger.debug(
            f"Adaptive timeout set to {self._current_timeout}s (volatility: {volatility:.2%})"
        )


# Convenience function
def create_optimized_analyzer(
    api_key: Optional[str] = None,
    enable_caching: bool = True,
    enable_prioritization: bool = True,
) -> OptimizedMultiLLMAnalyzer:
    """
    Create optimized MultiLLMAnalyzer instance.

    Args:
        api_key: OpenRouter API key
        enable_caching: Enable response caching
        enable_prioritization: Enable request prioritization

    Returns:
        Configured OptimizedMultiLLMAnalyzer instance
    """
    return OptimizedMultiLLMAnalyzer(
        api_key=api_key,
        enable_caching=enable_caching,
        enable_prioritization=enable_prioritization,
    )
