"""
Research Visualization Generator for Gemini Deep Research.

Generates charts and visualizations from research JSON data.
Works independently of Gemini visual outputs - always produces charts
from structured research data.

This module provides operational reliability by:
1. Generating visuals from any JSON research data
2. Gracefully handling missing fields
3. Using consistent trading theme colors
4. Supporting both matplotlib (file output) and Plotly (dashboard)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check matplotlib availability
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not installed - file-based charts unavailable")

# Check plotly availability
try:
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("plotly not installed - interactive charts unavailable")


# Trading theme colors (consistent with dashboard)
COLORS = {
    "bullish": "#00ff88",
    "neutral": "#ffd700",
    "bearish": "#ff4444",
    "background": "#0e1117",
    "grid": "#262730",
    "text": "#fafafa",
    "secondary": "#808495",
    "high_confidence": "#00cc66",
    "medium_confidence": "#ffaa00",
    "low_confidence": "#ff6666",
}


class ResearchVisualizer:
    """
    Generates visualizations from Gemini Deep Research output.

    Supports two output modes:
    1. File-based (matplotlib) - for wiki/dashboard markdown embedding
    2. Interactive (plotly) - for Streamlit dashboard
    """

    DEFAULT_OUTPUT_DIR = Path("wiki/graphs/research")

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize visualizer.

        Args:
            output_dir: Directory for saving chart images (default: wiki/graphs/research/)
        """
        self.output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def visualize_research(
        self, research_data: dict[str, Any], save_to_file: bool = True
    ) -> dict[str, Any]:
        """
        Generate all applicable visualizations from research data.

        Args:
            research_data: JSON output from Gemini Deep Research
            save_to_file: If True, save matplotlib charts to files

        Returns:
            Dictionary with paths to generated charts and/or Plotly figures
        """
        outputs: dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
            "charts": {},
            "figures": {},
        }

        research_name = research_data.get("research_name", "research")

        # Generate applicable charts based on available data
        if self._has_recommendation_data(research_data):
            chart_info = self._create_recommendation_chart(
                research_data, research_name, save_to_file
            )
            if chart_info:
                outputs["charts"]["recommendation"] = chart_info

        if self._has_sentiment_data(research_data):
            chart_info = self._create_sentiment_gauge_chart(
                research_data, research_name, save_to_file
            )
            if chart_info:
                outputs["charts"]["sentiment"] = chart_info

        if self._has_key_levels_data(research_data):
            chart_info = self._create_key_levels_chart(
                research_data, research_name, save_to_file
            )
            if chart_info:
                outputs["charts"]["key_levels"] = chart_info

        if self._has_allocation_data(research_data):
            chart_info = self._create_allocation_pie_chart(
                research_data, research_name, save_to_file
            )
            if chart_info:
                outputs["charts"]["allocation"] = chart_info

        if self._has_risk_data(research_data):
            chart_info = self._create_risk_meter_chart(
                research_data, research_name, save_to_file
            )
            if chart_info:
                outputs["charts"]["risk"] = chart_info

        logger.info(f"Generated {len(outputs['charts'])} charts for {research_name}")
        return outputs

    # --- Data Detection Methods ---

    def _has_recommendation_data(self, data: dict) -> bool:
        return "recommendation" in data and "confidence" in data

    def _has_sentiment_data(self, data: dict) -> bool:
        return "sentiment" in data or "fear_greed_index" in data

    def _has_key_levels_data(self, data: dict) -> bool:
        return "key_levels" in data or "support" in data or "resistance" in data

    def _has_allocation_data(self, data: dict) -> bool:
        return "allocation" in data

    def _has_risk_data(self, data: dict) -> bool:
        return "risk_level" in data or "key_risks" in data

    # --- Chart Generation Methods ---

    def _create_recommendation_chart(
        self, data: dict, name: str, save: bool
    ) -> Optional[dict]:
        """Create a recommendation confidence chart."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        recommendation = data.get("recommendation", "HOLD")
        confidence = data.get("confidence", 0.5)

        # Normalize confidence to 0-1 if it's a percentage
        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100

        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor(COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        # Create horizontal bar
        rec_colors = {
            "BUY": COLORS["bullish"],
            "SELL": COLORS["bearish"],
            "HOLD": COLORS["neutral"],
        }
        bar_color = rec_colors.get(recommendation.upper(), COLORS["neutral"])

        ax.barh([0], [confidence], color=bar_color, height=0.5, alpha=0.8)
        ax.barh([0], [1], color=COLORS["grid"], height=0.5, alpha=0.3)

        # Add text
        ax.text(
            0.5,
            0.7,
            f"{recommendation.upper()}",
            ha="center",
            va="center",
            fontsize=24,
            fontweight="bold",
            color=bar_color,
            transform=ax.transAxes,
        )
        ax.text(
            0.5,
            0.3,
            f"Confidence: {confidence:.0%}",
            ha="center",
            va="center",
            fontsize=14,
            color=COLORS["text"],
            transform=ax.transAxes,
        )

        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, 1)
        ax.axis("off")
        ax.set_title(
            "Trading Recommendation",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if save:
            filepath = self.output_dir / f"{name}_recommendation.png"
            plt.savefig(
                filepath,
                dpi=150,
                bbox_inches="tight",
                facecolor=COLORS["background"],
            )
            plt.close(fig)
            return {"path": str(filepath), "type": "recommendation"}

        plt.close(fig)
        return {"type": "recommendation", "generated": True}

    def _create_sentiment_gauge_chart(
        self, data: dict, name: str, save: bool
    ) -> Optional[dict]:
        """Create a sentiment gauge chart."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        # Extract sentiment (normalize various formats)
        sentiment = data.get("sentiment", data.get("fear_greed_index", "neutral"))
        if isinstance(sentiment, str):
            sentiment_map = {
                "bullish": 75,
                "very bullish": 90,
                "bearish": -75,
                "very bearish": -90,
                "neutral": 0,
                "fear": -50,
                "greed": 50,
                "extreme fear": -80,
                "extreme greed": 80,
            }
            score = sentiment_map.get(sentiment.lower(), 0)
        elif isinstance(sentiment, (int, float)):
            score = float(sentiment)
            # Normalize to -100 to 100 if needed
            if 0 <= score <= 100:
                score = (score - 50) * 2
        else:
            score = 0

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor(COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        # Create gauge background
        theta = np.linspace(0, np.pi, 100)
        r = 1

        # Draw gauge sections
        sections = [
            (0, np.pi / 5, COLORS["bearish"]),
            (np.pi / 5, 2 * np.pi / 5, "#ff8866"),
            (2 * np.pi / 5, 3 * np.pi / 5, COLORS["neutral"]),
            (3 * np.pi / 5, 4 * np.pi / 5, "#88ff66"),
            (4 * np.pi / 5, np.pi, COLORS["bullish"]),
        ]

        for start, end, color in sections:
            theta_section = np.linspace(start, end, 50)
            for t in theta_section:
                ax.plot(
                    [0, r * np.cos(t)],
                    [0, r * np.sin(t)],
                    color=color,
                    alpha=0.3,
                    linewidth=2,
                )

        # Draw needle
        needle_angle = np.pi * (1 - (score + 100) / 200)  # Map -100,100 to pi,0
        ax.arrow(
            0,
            0,
            0.8 * np.cos(needle_angle),
            0.8 * np.sin(needle_angle),
            head_width=0.1,
            head_length=0.05,
            fc=COLORS["text"],
            ec=COLORS["text"],
            linewidth=3,
        )

        # Add labels
        ax.text(
            0,
            -0.3,
            f"Score: {score:.0f}",
            ha="center",
            fontsize=18,
            fontweight="bold",
            color=COLORS["text"],
        )

        # Sentiment label
        if score >= 50:
            label = "BULLISH"
            label_color = COLORS["bullish"]
        elif score >= 20:
            label = "MILDLY BULLISH"
            label_color = "#88ff66"
        elif score <= -50:
            label = "BEARISH"
            label_color = COLORS["bearish"]
        elif score <= -20:
            label = "MILDLY BEARISH"
            label_color = "#ff8866"
        else:
            label = "NEUTRAL"
            label_color = COLORS["neutral"]

        ax.text(
            0,
            -0.5,
            label,
            ha="center",
            fontsize=14,
            color=label_color,
        )

        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-0.7, 1.2)
        ax.axis("off")
        ax.set_aspect("equal")
        ax.set_title(
            "Market Sentiment",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if save:
            filepath = self.output_dir / f"{name}_sentiment.png"
            plt.savefig(
                filepath,
                dpi=150,
                bbox_inches="tight",
                facecolor=COLORS["background"],
            )
            plt.close(fig)
            return {"path": str(filepath), "type": "sentiment"}

        plt.close(fig)
        return {"type": "sentiment", "generated": True}

    def _create_key_levels_chart(
        self, data: dict, name: str, save: bool
    ) -> Optional[dict]:
        """Create a support/resistance levels chart."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        key_levels = data.get("key_levels", {})
        support = key_levels.get("support", data.get("support", []))
        resistance = key_levels.get("resistance", data.get("resistance", []))

        if not support and not resistance:
            return None

        # Normalize to lists
        if isinstance(support, (int, float)):
            support = [support]
        if isinstance(resistance, (int, float)):
            resistance = [resistance]

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor(COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        all_levels = []
        if support:
            all_levels.extend([(s, "support") for s in support[:3]])
        if resistance:
            all_levels.extend([(r, "resistance") for r in resistance[:3]])

        if not all_levels:
            plt.close(fig)
            return None

        all_levels.sort(key=lambda x: x[0])

        y_positions = range(len(all_levels))
        colors_list = [
            COLORS["bullish"] if t == "support" else COLORS["bearish"]
            for _, t in all_levels
        ]
        values = [v for v, _ in all_levels]

        bars = ax.barh(y_positions, values, color=colors_list, alpha=0.7, height=0.6)

        # Add value labels
        for bar, (value, level_type) in zip(bars, all_levels, strict=False):
            ax.text(
                bar.get_width() + max(values) * 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"${value:,.2f}",
                va="center",
                fontsize=12,
                color=COLORS["text"],
            )

        ax.set_yticks(y_positions)
        ax.set_yticklabels(
            [f"{t.title()}" for _, t in all_levels], color=COLORS["text"]
        )
        ax.set_xlabel("Price Level", color=COLORS["text"])
        ax.tick_params(colors=COLORS["text"])
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.spines["left"].set_color(COLORS["grid"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Legend
        support_patch = mpatches.Patch(color=COLORS["bullish"], label="Support")
        resistance_patch = mpatches.Patch(color=COLORS["bearish"], label="Resistance")
        ax.legend(
            handles=[support_patch, resistance_patch],
            loc="upper right",
            facecolor=COLORS["background"],
            edgecolor=COLORS["grid"],
            labelcolor=COLORS["text"],
        )

        ax.set_title(
            "Key Price Levels",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if save:
            filepath = self.output_dir / f"{name}_key_levels.png"
            plt.savefig(
                filepath,
                dpi=150,
                bbox_inches="tight",
                facecolor=COLORS["background"],
            )
            plt.close(fig)
            return {"path": str(filepath), "type": "key_levels"}

        plt.close(fig)
        return {"type": "key_levels", "generated": True}

    def _create_allocation_pie_chart(
        self, data: dict, name: str, save: bool
    ) -> Optional[dict]:
        """Create a portfolio allocation pie chart."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        allocation = data.get("allocation", {})
        if not allocation:
            return None

        fig, ax = plt.subplots(figsize=(8, 8))
        fig.patch.set_facecolor(COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        # Parse allocation
        labels = []
        sizes = []
        colors_list = []

        color_map = {
            "stocks": COLORS["bullish"],
            "crypto": "#8844ff",
            "cash": COLORS["neutral"],
            "bonds": "#4488ff",
        }

        for key, value in allocation.items():
            if isinstance(value, (int, float)) and value > 0:
                # Extract percentage from string like "40%" or number
                if isinstance(value, str):
                    value = float(value.replace("%", ""))
                labels.append(key.title())
                sizes.append(value)
                colors_list.append(color_map.get(key.lower(), COLORS["secondary"]))

        if not sizes:
            plt.close(fig)
            return None

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct="%1.0f%%",
            colors=colors_list,
            textprops={"color": COLORS["text"], "fontsize": 12},
            wedgeprops={"edgecolor": COLORS["background"], "linewidth": 2},
        )

        for autotext in autotexts:
            autotext.set_color(COLORS["background"])
            autotext.set_fontweight("bold")

        ax.set_title(
            "Recommended Portfolio Allocation",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if save:
            filepath = self.output_dir / f"{name}_allocation.png"
            plt.savefig(
                filepath,
                dpi=150,
                bbox_inches="tight",
                facecolor=COLORS["background"],
            )
            plt.close(fig)
            return {"path": str(filepath), "type": "allocation"}

        plt.close(fig)
        return {"type": "allocation", "generated": True}

    def _create_risk_meter_chart(
        self, data: dict, name: str, save: bool
    ) -> Optional[dict]:
        """Create a risk level meter chart."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        risk_level = data.get("risk_level", "medium")
        key_risks = data.get("key_risks", [])

        # Map risk level to score
        risk_map = {"low": 25, "medium": 50, "high": 75, "extreme": 95}
        if isinstance(risk_level, str):
            risk_score = risk_map.get(risk_level.lower(), 50)
        elif isinstance(risk_level, (int, float)):
            risk_score = min(100, max(0, risk_level))
        else:
            risk_score = 50

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(COLORS["background"])
        ax.set_facecolor(COLORS["background"])

        # Create gradient bar
        gradient = np.linspace(0, 1, 100).reshape(1, -1)
        ax.imshow(
            gradient,
            cmap="RdYlGn_r",
            aspect="auto",
            extent=[0, 100, 0, 1],
            alpha=0.7,
        )

        # Add marker
        ax.axvline(x=risk_score, color=COLORS["text"], linewidth=4)
        ax.plot(risk_score, 0.5, "v", color=COLORS["text"], markersize=20)

        # Labels
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.5, 1.5)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xticklabels(["Low", "", "Medium", "", "High"], color=COLORS["text"])
        ax.set_yticks([])

        # Risk score text
        ax.text(
            50,
            1.2,
            f"Risk Level: {risk_level.upper() if isinstance(risk_level, str) else f'{risk_score}%'}",
            ha="center",
            fontsize=18,
            fontweight="bold",
            color=COLORS["text"],
        )

        # Key risks
        if key_risks and isinstance(key_risks, list):
            risks_text = ", ".join(key_risks[:3])
            ax.text(
                50,
                -0.3,
                f"Key Risks: {risks_text}",
                ha="center",
                fontsize=10,
                color=COLORS["secondary"],
                wrap=True,
            )

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(COLORS["grid"])

        ax.set_title(
            "Market Risk Assessment",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        if save:
            filepath = self.output_dir / f"{name}_risk.png"
            plt.savefig(
                filepath,
                dpi=150,
                bbox_inches="tight",
                facecolor=COLORS["background"],
            )
            plt.close(fig)
            return {"path": str(filepath), "type": "risk"}

        plt.close(fig)
        return {"type": "risk", "generated": True}

    # --- Plotly Interactive Charts (for Streamlit) ---

    def create_recommendation_gauge_plotly(
        self, data: dict[str, Any]
    ) -> Optional["go.Figure"]:
        """Create an interactive recommendation gauge using Plotly."""
        if not PLOTLY_AVAILABLE:
            return None

        recommendation = data.get("recommendation", "HOLD")
        confidence = data.get("confidence", 0.5)

        if isinstance(confidence, (int, float)) and confidence > 1:
            confidence = confidence / 100

        rec_colors = {
            "BUY": COLORS["bullish"],
            "SELL": COLORS["bearish"],
            "HOLD": COLORS["neutral"],
        }
        bar_color = rec_colors.get(recommendation.upper(), COLORS["neutral"])

        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=confidence * 100,
                domain={"x": [0, 1], "y": [0, 1]},
                title={
                    "text": f"<b>{recommendation.upper()}</b>",
                    "font": {"size": 28, "color": bar_color},
                },
                number={
                    "suffix": "% confidence",
                    "font": {"size": 20, "color": COLORS["text"]},
                },
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": COLORS["text"]},
                    "bar": {"color": bar_color},
                    "bgcolor": COLORS["grid"],
                    "borderwidth": 2,
                    "bordercolor": COLORS["text"],
                    "steps": [
                        {"range": [0, 33], "color": "rgba(255, 68, 68, 0.2)"},
                        {"range": [33, 66], "color": "rgba(255, 215, 0, 0.2)"},
                        {"range": [66, 100], "color": "rgba(0, 255, 136, 0.2)"},
                    ],
                },
            )
        )

        fig.update_layout(
            paper_bgcolor=COLORS["background"],
            font={"color": COLORS["text"]},
            height=300,
        )

        return fig


# Convenience function
def visualize_research_output(
    research_data: dict[str, Any], output_dir: Optional[Path] = None
) -> dict[str, Any]:
    """
    Generate visualizations from research data.

    Args:
        research_data: JSON output from Gemini Deep Research
        output_dir: Optional output directory

    Returns:
        Dictionary with chart paths
    """
    visualizer = ResearchVisualizer(output_dir)
    return visualizer.visualize_research(research_data)


if __name__ == "__main__":
    # Test with sample data
    logging.basicConfig(level=logging.INFO)

    sample_research = {
        "research_name": "BTC_market_research",
        "recommendation": "BUY",
        "confidence": 0.75,
        "sentiment": "bullish",
        "key_levels": {"support": [95000, 92000], "resistance": [100000, 105000]},
        "allocation": {"crypto": 30, "stocks": 50, "cash": 20},
        "risk_level": "medium",
        "key_risks": ["Fed policy", "Geopolitical tensions", "Crypto regulation"],
    }

    result = visualize_research_output(sample_research)
    print(json.dumps(result, indent=2, default=str))
