"""Analytics module for trading system metrics and analysis."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "analyze_loss_clusters",
    "build_analytics_artifacts",
    "build_local_ops_snapshot",
    "build_perplexity_usage_snapshot",
    "build_system_diagnosis",
    "build_trade_setup_audit",
    "render_local_ops_markdown",
    "render_sql_analytics_summary",
    "render_trade_setup_audit_markdown",
    "write_trade_setup_audit_artifacts",
]


def __getattr__(name: str) -> Any:
    module_map = {
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
        "build_trade_setup_audit": (
            "src.analytics.trade_setup_audit",
            "build_trade_setup_audit",
        ),
        "render_trade_setup_audit_markdown": (
            "src.analytics.trade_setup_audit",
            "render_trade_setup_audit_markdown",
        ),
        "write_trade_setup_audit_artifacts": (
            "src.analytics.trade_setup_audit",
            "write_trade_setup_audit_artifacts",
        ),
        "analyze_loss_clusters": (
            "src.analytics.loss_forensics",
            "analyze_loss_clusters",
        ),
        "build_system_diagnosis": (
            "src.analytics.loss_forensics",
            "build_system_diagnosis",
        ),
    }
    if name not in module_map:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = module_map[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
