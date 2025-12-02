"""
IPO analysis helpers powered by MultiLLMAnalyzer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.client import get_multi_llm_analyzer
from mcp.utils import ensure_env_var, run_sync


async def analyze_ipo_async(company_data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Analyze IPO opportunities with ensemble LLM scoring.
    """

    analyzer = ensure_env_var(
        lambda: get_multi_llm_analyzer(use_async=True), "OpenRouter MultiLLMAnalyzer"
    )

    return await analyzer.analyze_ipo(dict(company_data))


def analyze_ipo(company_data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Sync wrapper around `analyze_ipo_async`.
    """

    return run_sync(analyze_ipo_async(company_data))
