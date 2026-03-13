"""Analytics module for trading system metrics and analysis."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "build_analytics_artifacts",
    "build_local_ops_snapshot",
    "build_perplexity_usage_snapshot",
    "recommend_provider",
    "render_local_ops_markdown",
    "render_sql_analytics_summary",
    "run_browser_ab_pilot",
    "summarize_provider_results",
]


def __getattr__(name: str) -> Any:
    module_map = {
        "run_browser_ab_pilot": ("src.analytics.browser_automation_pilot", "run_browser_ab_pilot"),
        "summarize_provider_results": (
            "src.analytics.browser_automation_pilot",
            "summarize_provider_results",
        ),
        "recommend_provider": ("src.analytics.browser_provider_promotion", "recommend_provider"),
        "build_local_ops_snapshot": (
            "src.analytics.local_ops_snapshot",
            "build_local_ops_snapshot",
        ),
        "render_local_ops_markdown": (
            "src.analytics.local_ops_snapshot",
            "render_local_ops_markdown",
        ),
        "build_perplexity_usage_snapshot": (
            "src.analytics.perplexity_utilization_audit",
            "build_perplexity_usage_snapshot",
        ),
        "build_analytics_artifacts": (
            "src.analytics.sqlite_analytics",
            "build_analytics_artifacts",
        ),
        "render_sql_analytics_summary": (
            "src.analytics.sqlite_analytics",
            "render_sql_analytics_summary",
        ),
    }
    if name not in module_map:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = module_map[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
