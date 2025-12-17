"""
Dashboard Integration for Gemini Deep Research Visualizations.

This module provides functions to integrate research visualizations
into the progress dashboard without modifying existing dashboard code.

Usage:
    from src.ml.dashboard_research_integration import get_research_dashboard_section

    # In dashboard generator:
    research_section = get_research_dashboard_section()
    dashboard_md += research_section
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Paths
RESEARCH_OUTPUT_DIR = Path("data/research_outputs")
RESEARCH_VISUALS_DIR = Path("wiki/graphs/research")


def get_latest_research_files(max_age_hours: int = 24) -> list[dict[str, Any]]:
    """
    Get list of recent research output files.

    Args:
        max_age_hours: Maximum age of research files to include

    Returns:
        List of research metadata dictionaries
    """
    json_dir = RESEARCH_OUTPUT_DIR / "json"
    if not json_dir.exists():
        return []

    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    results = []

    for filepath in json_dir.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)

            # Parse timestamp
            ts_str = data.get("timestamp", "")
            if ts_str:
                try:
                    ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    if ts >= cutoff:
                        data["_filepath"] = str(filepath)
                        data["_parsed_time"] = ts
                        results.append(data)
                except ValueError:
                    pass
        except (json.JSONDecodeError, OSError):
            continue

    # Sort by timestamp, newest first
    results.sort(key=lambda x: x.get("_parsed_time", datetime.min), reverse=True)
    return results


def generate_research_visualization_section(
    research_data: Optional[dict[str, Any]] = None,
) -> str:
    """
    Generate markdown section for research visualizations.

    If no research_data provided, uses latest available research.

    Returns:
        Markdown string for dashboard section
    """
    # Try to get latest research if not provided
    if research_data is None:
        recent = get_latest_research_files(max_age_hours=48)
        if recent:
            research_data = recent[0]

    if not research_data:
        return _generate_no_research_section()

    # Generate visualizations
    try:
        from src.ml.research_visualizer import ResearchVisualizer

        RESEARCH_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
        visualizer = ResearchVisualizer(output_dir=RESEARCH_VISUALS_DIR)

        # Get text content (may be nested or direct)
        text_content = research_data.get("text_content", research_data)

        viz_result = visualizer.visualize_research(text_content, save_to_file=True)
        charts = viz_result.get("charts", {})

    except ImportError:
        logger.warning("ResearchVisualizer not available, skipping chart generation")
        charts = {}
    except Exception as e:
        logger.error(f"Failed to generate research visualizations: {e}")
        charts = {}

    return _build_research_section_md(research_data, charts)


def _generate_no_research_section() -> str:
    """Generate placeholder section when no research available."""
    return """
## 🔍 Deep Research Insights

> No recent research data available. Research will appear here after running:
> ```python
> from src.ml.gemini_deep_research import get_researcher
> researcher = get_researcher()
> result = researcher.research_market_conditions()
> ```

"""


def _build_research_section_md(
    research_data: dict[str, Any],
    charts: dict[str, Any]
) -> str:
    """Build markdown section from research data and generated charts."""
    research_name = research_data.get("research_name", "Market Research")
    timestamp = research_data.get("timestamp", "")
    text_content = research_data.get("text_content", research_data)
    visual_outputs = research_data.get("visual_outputs", [])

    # Format timestamp
    ts_display = timestamp
    if timestamp:
        try:
            ts = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            ts_display = ts.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            pass

    md = f"""
## 🔍 Deep Research Insights

**Last Updated:** {ts_display}
**Research:** {research_name.replace("_", " ").title()}

"""

    # Add recommendation if available
    recommendation = text_content.get("recommendation", "")
    confidence = text_content.get("confidence", 0)
    if recommendation:
        # Normalize confidence
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100

        rec_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(
            recommendation.upper(), "⚪"
        )
        md += f"### Trading Signal: {rec_emoji} **{recommendation.upper()}** ({confidence:.0%} confidence)\n\n"

    # Add generated charts (if available)
    if charts:
        md += "### Research Visualizations\n\n"

        for chart_type, chart_info in charts.items():
            if isinstance(chart_info, dict) and "path" in chart_info:
                # Convert to relative path for wiki
                path = Path(chart_info["path"])
                rel_path = path.relative_to(Path("wiki")) if "wiki" in str(path) else path
                md += f"![{chart_type.title()}]({rel_path})\n\n"

    # Add Gemini visual outputs (if available from API)
    if visual_outputs:
        md += "### AI-Generated Visuals (from Gemini)\n\n"
        for viz in visual_outputs:
            if isinstance(viz, dict) and viz.get("path"):
                path = Path(viz["path"])
                md += f"![Research Visual]({path.name})\n\n"

    # Add key metrics in a table
    md += "### Key Metrics\n\n"
    md += "| Metric | Value |\n|--------|-------|\n"

    # Extract key metrics
    metrics_to_show = [
        ("sentiment", "Sentiment"),
        ("risk_level", "Risk Level"),
        ("market_regime", "Market Regime"),
        ("vix_analysis", "VIX Analysis"),
    ]

    for key, label in metrics_to_show:
        value = text_content.get(key)
        if value:
            if isinstance(value, dict):
                value = json.dumps(value, default=str)[:50] + "..."
            md += f"| {label} | {value} |\n"

    # Add key levels if available
    key_levels = text_content.get("key_levels", {})
    if key_levels:
        support = key_levels.get("support", [])
        resistance = key_levels.get("resistance", [])
        if support:
            md += f"| Support Levels | {', '.join(f'${s:,.0f}' for s in support[:3] if isinstance(s, (int, float)))} |\n"
        if resistance:
            md += f"| Resistance Levels | {', '.join(f'${r:,.0f}' for r in resistance[:3] if isinstance(r, (int, float)))} |\n"

    # Add allocation if available
    allocation = text_content.get("allocation", {})
    if allocation:
        alloc_str = ", ".join(f"{k}: {v}%" for k, v in allocation.items() if isinstance(v, (int, float)))
        md += f"| Recommended Allocation | {alloc_str} |\n"

    # Add key risks if available
    key_risks = text_content.get("key_risks", [])
    if key_risks and isinstance(key_risks, list):
        risks_str = ", ".join(key_risks[:3])
        md += f"| Key Risks | {risks_str} |\n"

    md += "\n"

    # Add sources if available
    sources = text_content.get("sources", research_data.get("sources", []))
    if sources:
        md += "<details>\n<summary><strong>Research Sources</strong></summary>\n\n"
        for source in sources[:5]:
            md += f"- {source}\n"
        md += "\n</details>\n\n"

    return md


def get_research_dashboard_section() -> str:
    """
    Main entry point for dashboard integration.

    Call this from the dashboard generator to add research section.

    Returns:
        Markdown string for research dashboard section
    """
    try:
        return generate_research_visualization_section()
    except Exception as e:
        logger.error(f"Failed to generate research dashboard section: {e}")
        return _generate_no_research_section()


if __name__ == "__main__":
    # Test the integration
    logging.basicConfig(level=logging.INFO)

    # Create sample research data for testing
    sample_data = {
        "research_name": "market_conditions",
        "timestamp": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
        "text_content": {
            "recommendation": "HOLD",
            "confidence": 0.65,
            "sentiment": "neutral",
            "risk_level": "medium",
            "market_regime": "sideways",
            "key_levels": {"support": [95000], "resistance": [100000]},
            "key_risks": ["Fed policy uncertainty", "Geopolitical tensions"],
        },
    }

    section = generate_research_visualization_section(sample_data)
    print(section)
