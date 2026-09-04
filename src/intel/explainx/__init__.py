"""Honest ExplainX trending ingest. Not a clone. Not a skill installer."""

from src.intel.explainx.ceilings import (
    COHORT_GATE_N,
    FORBIDDEN_RESETS,
    build_ceiling_report,
)
from src.intel.explainx.harness_split import classify_command
from src.intel.explainx.map_rails import map_items
from src.intel.explainx.parse import (
    TRENDING_URL,
    UNAVAILABLE,
    parse_trending_html,
)

__all__ = [
    "COHORT_GATE_N",
    "FORBIDDEN_RESETS",
    "TRENDING_URL",
    "UNAVAILABLE",
    "build_ceiling_report",
    "classify_command",
    "map_items",
    "parse_trending_html",
]
