"""
Sentiment-focused helpers powered by MultiLLMAnalyzer.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

from mcp.client import get_multi_llm_analyzer
from mcp.utils import ensure_env_var, run_sync


def _normalize_news(news: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if not news:
        return []
    normalized = []
    for item in news:
        normalized.append(
            {
                "title": item.get("title", "N/A"),
                "content": item.get("content", ""),
                "source": item.get("source"),
            }
        )
    return normalized


async def ensemble_sentiment_async(
    market_data: Mapping[str, Any], news: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Return aggregate sentiment score across configured LLMs.
    """

    analyzer = ensure_env_var(
        lambda: get_multi_llm_analyzer(use_async=True), "OpenRouter MultiLLMAnalyzer"
    )
    sentiment = await analyzer.get_ensemble_sentiment(dict(market_data), _normalize_news(news))
    return {"sentiment": sentiment}


def ensemble_sentiment(
    market_data: Mapping[str, Any], news: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Sync wrapper around `ensemble_sentiment_async`.
    """

    return run_sync(ensemble_sentiment_async(market_data, news))


async def detailed_sentiment_async(
    market_data: Mapping[str, Any], news: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Return detailed sentiment analysis with per-model breakdown.
    """

    analyzer = ensure_env_var(
        lambda: get_multi_llm_analyzer(use_async=True), "OpenRouter MultiLLMAnalyzer"
    )

    result = await analyzer.get_ensemble_sentiment_detailed(
        dict(market_data), _normalize_news(news)
    )

    if is_dataclass(result):
        result = asdict(result)

    return result


def detailed_sentiment(
    market_data: Mapping[str, Any], news: Iterable[Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Sync wrapper around `detailed_sentiment_async`.
    """

    return run_sync(detailed_sentiment_async(market_data, news))


async def market_outlook_async() -> dict[str, Any]:
    """
    Generate a broad market outlook using the ensemble models.
    """

    analyzer = ensure_env_var(
        lambda: get_multi_llm_analyzer(use_async=True), "OpenRouter MultiLLMAnalyzer"
    )

    outlook = await analyzer.get_market_outlook()
    return outlook


def market_outlook() -> dict[str, Any]:
    """
    Sync wrapper around `market_outlook_async`.
    """

    return run_sync(market_outlook_async())
