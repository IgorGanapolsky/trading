"""
Stock-level analysis helpers backed by MultiLLMAnalyzer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.client import get_multi_llm_analyzer
from mcp.utils import ensure_env_var, run_sync


async def analyze_stock_async(symbol: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Analyze a stock symbol using the ensemble of LLMs.
    """

    analyzer = ensure_env_var(
        lambda: get_multi_llm_analyzer(use_async=True), "OpenRouter MultiLLMAnalyzer"
    )

    return await analyzer.analyze_stock(symbol, dict(data))


def analyze_stock(symbol: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Sync wrapper around `analyze_stock_async`.
    """

    return run_sync(analyze_stock_async(symbol, data))
