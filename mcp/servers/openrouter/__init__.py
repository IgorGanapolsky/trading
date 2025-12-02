"""
OpenRouter-backed analysis helpers.

These functions wrap `MultiLLMAnalyzer` capabilities behind a code API that
agents can import on demand inside an MCP execution environment.
"""

from .ipo import analyze_ipo, analyze_ipo_async
from .sentiment import (
    detailed_sentiment,
    detailed_sentiment_async,
    ensemble_sentiment,
    ensemble_sentiment_async,
    market_outlook,
    market_outlook_async,
)
from .stocks import analyze_stock, analyze_stock_async

__all__ = [
    "ensemble_sentiment",
    "ensemble_sentiment_async",
    "detailed_sentiment",
    "detailed_sentiment_async",
    "market_outlook",
    "market_outlook_async",
    "analyze_ipo",
    "analyze_ipo_async",
    "analyze_stock",
    "analyze_stock_async",
]
