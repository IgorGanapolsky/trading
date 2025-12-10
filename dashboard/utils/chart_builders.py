"""
Reusable Plotly chart builders for Sentiment RAG Dashboard.

This module provides consistent, themed chart functions for visualizing
trading sentiment data across multiple data sources.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Trading theme colors
COLORS = {
    "bullish": "#00ff88",  # Green
    "neutral": "#ffd700",  # Gold
    "bearish": "#ff4444",  # Red
    "background": "#0e1117",
    "grid": "#262730",
    "text": "#fafafa",
    "secondary": "#808495",
}


def get_sentiment_color(score: float) -> str:
    """Get color based on sentiment score (-100 to 100 scale)."""
    if score >= 20:
        return COLORS["bullish"]
    elif score <= -20:
        return COLORS["bearish"]
    else:
        return COLORS["neutral"]


def create_sentiment_gauge(ticker: str, score: float, confidence: str = "medium") -> go.Figure:
    """
    Create a gauge chart for sentiment score.

    Args:
        ticker: Stock ticker symbol
        score: Sentiment score (-100 to 100)
        confidence: Confidence level (low/medium/high)

    Returns:
        Plotly figure object
    """
    # Normalize score to 0-100 for gauge
    (score + 100) / 2

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": f"{ticker}<br><span style='font-size:0.8em;color:{COLORS['secondary']}'>Confidence: {confidence}</span>",
                "font": {"size": 20, "color": COLORS["text"]},
            },
            number={"font": {"size": 40, "color": get_sentiment_color(score)}},
            gauge={
                "axis": {
                    "range": [-100, 100],
                    "tickwidth": 1,
                    "tickcolor": COLORS["text"],
                },
                "bar": {"color": get_sentiment_color(score), "thickness": 0.75},
                "bgcolor": COLORS["grid"],
                "borderwidth": 2,
                "bordercolor": COLORS["text"],
                "steps": [
                    {"range": [-100, -20], "color": "rgba(255, 68, 68, 0.2)"},
                    {"range": [-20, 20], "color": "rgba(255, 215, 0, 0.2)"},
                    {"range": [20, 100], "color": "rgba(0, 255, 136, 0.2)"},
                ],
                "threshold": {
                    "line": {"color": COLORS["text"], "width": 4},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )

    fig.update_layout(
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        height=300,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


def create_sentiment_timeline(df: pd.DataFrame, tickers: list[str]) -> go.Figure:
    """
    Create a timeline chart showing sentiment trends over time.

    Args:
        df: DataFrame with columns ['date', 'ticker', 'score']
        tickers: List of ticker symbols to display

    Returns:
        Plotly figure object
    """
    fig = go.Figure()

    for ticker in tickers:
        ticker_data = df[df["ticker"] == ticker].sort_values("date")

        fig.add_trace(
            go.Scatter(
                x=ticker_data["date"],
                y=ticker_data["score"],
                mode="lines+markers",
                name=ticker,
                line=dict(width=3),
                marker=dict(size=8),
                hovertemplate=f"<b>{ticker}</b><br>Date: %{{x}}<br>Sentiment: %{{y:.1f}}<extra></extra>",
            )
        )

    fig.update_layout(
        title={
            "text": "Sentiment Trends (30-Day View)",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        xaxis=dict(title="Date", gridcolor=COLORS["grid"], color=COLORS["text"]),
        yaxis=dict(
            title="Sentiment Score",
            gridcolor=COLORS["grid"],
            color=COLORS["text"],
            range=[-100, 100],
            zeroline=True,
            zerolinecolor=COLORS["secondary"],
            zerolinewidth=2,
        ),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        hovermode="x unified",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def create_correlation_heatmap(correlation_df: pd.DataFrame) -> go.Figure:
    """
    Create a heatmap showing correlation between sentiment and returns.

    Args:
        correlation_df: DataFrame with correlation matrix

    Returns:
        Plotly figure object
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=correlation_df.values,
            x=correlation_df.columns,
            y=correlation_df.index,
            colorscale=[
                [0, COLORS["bearish"]],
                [0.5, COLORS["neutral"]],
                [1, COLORS["bullish"]],
            ],
            zmid=0,
            text=correlation_df.values,
            texttemplate="%{text:.2f}",
            textfont={"size": 14},
            hovertemplate="%{y} vs %{x}<br>Correlation: %{z:.3f}<extra></extra>",
        )
    )

    fig.update_layout(
        title={
            "text": "Sentiment vs Actual Returns Correlation",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        height=500,
    )

    return fig


def create_source_breakdown_pie(source_data: dict[str, int]) -> go.Figure:
    """
    Create a pie chart showing data source breakdown.

    Args:
        source_data: Dictionary mapping source names to counts

    Returns:
        Plotly figure object
    """
    fig = go.Figure(
        data=[
            go.Pie(
                labels=list(source_data.keys()),
                values=list(source_data.values()),
                hole=0.4,
                marker=dict(
                    colors=[COLORS["bullish"], COLORS["neutral"], "#8844ff", "#ff8844"],
                    line=dict(color=COLORS["text"], width=2),
                ),
                textfont=dict(size=14, color=COLORS["text"]),
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title={
            "text": "Data Source Distribution",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        paper_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        showlegend=True,
        height=400,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
    )

    return fig


def create_win_rate_by_sentiment_bar(win_rate_data: pd.DataFrame) -> go.Figure:
    """
    Create a bar chart showing win rate breakdown by sentiment level.

    Args:
        win_rate_data: DataFrame with columns ['sentiment_range', 'win_rate', 'trade_count']

    Returns:
        Plotly figure object
    """
    colors = [
        (
            COLORS["bearish"]
            if "Bearish" in x
            else COLORS["neutral"]
            if "Neutral" in x
            else COLORS["bullish"]
        )
        for x in win_rate_data["sentiment_range"]
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=win_rate_data["sentiment_range"],
                y=win_rate_data["win_rate"],
                marker_color=colors,
                text=[
                    f"{wr:.1f}%<br>({tc} trades)"
                    for wr, tc in zip(
                        win_rate_data["win_rate"], win_rate_data["trade_count"], strict=False
                    )
                ],
                textposition="outside",
                textfont=dict(size=12, color=COLORS["text"]),
                hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        title={
            "text": "Win Rate by Sentiment Level",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        xaxis=dict(title="Sentiment Range", gridcolor=COLORS["grid"], color=COLORS["text"]),
        yaxis=dict(
            title="Win Rate (%)",
            gridcolor=COLORS["grid"],
            color=COLORS["text"],
            range=[0, 100],
        ),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        height=450,
    )

    return fig


def create_performance_comparison_table(comparison_data: pd.DataFrame) -> go.Figure:
    """
    Create a table comparing trades with vs without sentiment.

    Args:
        comparison_data: DataFrame with performance metrics

    Returns:
        Plotly figure object
    """
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(comparison_data.columns),
                    fill_color=COLORS["grid"],
                    align="left",
                    font=dict(size=14, color=COLORS["text"], family="Arial"),
                    height=40,
                ),
                cells=dict(
                    values=[comparison_data[col] for col in comparison_data.columns],
                    fill_color=COLORS["background"],
                    align="left",
                    font=dict(size=12, color=COLORS["text"], family="Arial"),
                    height=35,
                ),
            )
        ]
    )

    fig.update_layout(
        title={
            "text": "Performance Comparison: With vs Without Sentiment",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        paper_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        height=400,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


def create_mentions_timeline(df: pd.DataFrame) -> go.Figure:
    """
    Create a timeline showing mention volume across sources.

    Args:
        df: DataFrame with columns ['date', 'source', 'mentions']

    Returns:
        Plotly figure object
    """
    fig = px.area(
        df,
        x="date",
        y="mentions",
        color="source",
        title="Mention Volume Over Time by Source",
    )

    fig.update_layout(
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        xaxis=dict(gridcolor=COLORS["grid"], color=COLORS["text"]),
        yaxis=dict(gridcolor=COLORS["grid"], color=COLORS["text"]),
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


def create_roi_attribution_waterfall(attribution_data: dict[str, float]) -> go.Figure:
    """
    Create a waterfall chart showing ROI attribution.

    Args:
        attribution_data: Dictionary mapping component to ROI contribution

    Returns:
        Plotly figure object
    """
    components = list(attribution_data.keys())
    values = list(attribution_data.values())

    fig = go.Figure(
        go.Waterfall(
            name="ROI Attribution",
            orientation="v",
            measure=["relative"] * (len(components) - 1) + ["total"],
            x=components,
            textposition="outside",
            text=[f"{v:+.2f}%" for v in values],
            y=values,
            connector={"line": {"color": COLORS["secondary"]}},
            increasing={"marker": {"color": COLORS["bullish"]}},
            decreasing={"marker": {"color": COLORS["bearish"]}},
            totals={"marker": {"color": COLORS["neutral"]}},
        )
    )

    fig.update_layout(
        title={
            "text": "ROI Attribution Analysis",
            "font": {"size": 24, "color": COLORS["text"]},
        },
        xaxis=dict(title="Component", gridcolor=COLORS["grid"], color=COLORS["text"]),
        yaxis=dict(title="ROI Contribution (%)", gridcolor=COLORS["grid"], color=COLORS["text"]),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],
        font={"color": COLORS["text"], "family": "Arial"},
        showlegend=False,
        height=500,
    )

    return fig
