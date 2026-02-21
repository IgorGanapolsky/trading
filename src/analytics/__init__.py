"""Analytics module for trading system metrics and analysis."""

from .browser_automation_pilot import run_browser_ab_pilot, summarize_provider_results
from .local_ops_snapshot import build_local_ops_snapshot, render_local_ops_markdown
from .perplexity_utilization_audit import build_perplexity_usage_snapshot

__all__ = [
    "build_local_ops_snapshot",
    "build_perplexity_usage_snapshot",
    "render_local_ops_markdown",
    "run_browser_ab_pilot",
    "summarize_provider_results",
]
