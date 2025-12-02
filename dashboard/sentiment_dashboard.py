"""
Sentiment RAG Dashboard - Main Entry Point

A comprehensive Streamlit dashboard for visualizing the sentiment analysis
system used in the AI trading project.

Usage:
    streamlit run sentiment_dashboard.py
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.utils.chart_builders import (
    COLORS,
    create_sentiment_gauge,
)

# Page configuration
st.set_page_config(
    page_title="Sentiment RAG Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark trading theme
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {COLORS["background"]};
    }}
    .big-metric {{
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }}
    .bullish {{
        color: {COLORS["bullish"]};
        background: {COLORS["bullish"]}20;
    }}
    .bearish {{
        color: {COLORS["bearish"]};
        background: {COLORS["bearish"]}20;
    }}
    .neutral {{
        color: {COLORS["neutral"]};
        background: {COLORS["neutral"]}20;
    }}
    .stMetric {{
        background-color: {COLORS["grid"]};
        padding: 1rem;
        border-radius: 8px;
    }}
    .timestamp {{
        text-align: center;
        color: {COLORS["secondary"]};
        font-size: 0.9rem;
        margin-top: 1rem;
    }}
    .stale-warning {{
        background-color: {COLORS["bearish"]}30;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid {COLORS["bearish"]};
        margin: 1rem 0;
    }}
    </style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_sentiment_data(data_dir: Path, date: str = None):
    """Load sentiment data from JSON files."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    reddit_file = data_dir / f"reddit_{date}.json"
    news_file = data_dir / f"news_{date}.json"

    data = {
        "reddit": None,
        "news": None,
        "combined": {},
        "last_updated": None,
        "is_stale": False,
    }

    # Load Reddit data
    if reddit_file.exists():
        with open(reddit_file) as f:
            data["reddit"] = json.load(f)
            data["last_updated"] = data["reddit"]["meta"].get("timestamp")

    # Load news data
    if news_file.exists():
        with open(news_file) as f:
            data["news"] = json.load(f)
            if not data["last_updated"]:
                data["last_updated"] = data["news"]["meta"].get("timestamp")

    # Check if data is stale (>24 hours old)
    if data["last_updated"]:
        last_update = datetime.fromisoformat(data["last_updated"])
        data["is_stale"] = (datetime.now() - last_update) > timedelta(hours=24)

    # Combine sentiment scores
    if data["reddit"] and data["news"]:
        all_tickers = set()
        if data["reddit"]:
            all_tickers.update(data["reddit"]["sentiment_by_ticker"].keys())
        if data["news"]:
            all_tickers.update(data["news"]["sentiment_by_ticker"].keys())

        for ticker in all_tickers:
            reddit_score = 0
            news_score = 0

            if data["reddit"] and ticker in data["reddit"]["sentiment_by_ticker"]:
                reddit_data = data["reddit"]["sentiment_by_ticker"][ticker]
                # Normalize Reddit score to -100 to 100 scale
                reddit_score = min(100, max(-100, reddit_data.get("score", 0) / 2))

            if data["news"] and ticker in data["news"]["sentiment_by_ticker"]:
                news_score = data["news"]["sentiment_by_ticker"][ticker].get("score", 0)

            # Weighted average: 40% Reddit, 60% News (news is more reliable)
            combined_score = (reddit_score * 0.4) + (news_score * 0.6)

            data["combined"][ticker] = {
                "score": combined_score,
                "reddit_score": reddit_score,
                "news_score": news_score,
                "confidence": (
                    "high"
                    if abs(combined_score) > 30
                    else "medium"
                    if abs(combined_score) > 10
                    else "low"
                ),
            }

    return data


def get_market_regime(combined_scores: dict) -> str:
    """Determine market regime based on overall sentiment."""
    if not combined_scores:
        return "neutral"

    avg_score = sum(s["score"] for s in combined_scores.values()) / len(combined_scores)

    if avg_score > 20:
        return "risk_on"
    elif avg_score < -20:
        return "risk_off"
    else:
        return "neutral"


def main():
    """Main dashboard page."""
    # Header
    st.title("📊 Sentiment RAG Dashboard")
    st.markdown("Real-time sentiment analysis for AI trading decisions")

    # Sidebar
    st.sidebar.title("⚙️ Settings")

    # Data directory selector
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "sentiment"

    # Date selector
    available_dates = sorted(
        set([f.stem.split("_", 1)[1] for f in data_dir.glob("*_*.json")]), reverse=True
    )

    if not available_dates:
        st.error("No sentiment data found. Please run sentiment collection scripts first.")
        st.stop()

    selected_date = st.sidebar.selectbox("Select Date", available_dates, index=0)

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=False)
    if auto_refresh:
        st.sidebar.info("Dashboard will refresh every 60 seconds")

    # Load data
    data = load_sentiment_data(data_dir, selected_date)

    # Stale data warning
    if data["is_stale"]:
        st.markdown(
            """
            <div class="stale-warning">
                <strong>⚠️ Warning: Stale Data</strong><br>
                This data is more than 24 hours old. Run sentiment collection scripts to update.
            </div>
        """,
            unsafe_allow_html=True,
        )

    # Last updated timestamp
    if data["last_updated"]:
        last_update = datetime.fromisoformat(data["last_updated"])
        st.markdown(
            f"""
            <div class="timestamp">
                Last Updated: {last_update.strftime("%Y-%m-%d %I:%M:%S %p")}
            </div>
        """,
            unsafe_allow_html=True,
        )

    # Market regime
    if data["combined"]:
        regime = get_market_regime(data["combined"])
        regime_class = {
            "risk_on": "bullish",
            "risk_off": "bearish",
            "neutral": "neutral",
        }[regime]

        st.markdown(
            f"""
            <div class="big-metric {regime_class}">
                Market Regime: {regime.replace("_", " ").upper()}
            </div>
        """,
            unsafe_allow_html=True,
        )

    # Main content
    if not data["combined"]:
        st.warning("No sentiment data available for this date.")
        return

    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_tickers = len(data["combined"])
        st.metric("Total Tickers", total_tickers)

    with col2:
        bullish_count = sum(1 for s in data["combined"].values() if s["score"] > 20)
        st.metric("Bullish Signals", bullish_count)

    with col3:
        bearish_count = sum(1 for s in data["combined"].values() if s["score"] < -20)
        st.metric("Bearish Signals", bearish_count)

    with col4:
        avg_score = sum(s["score"] for s in data["combined"].values()) / len(data["combined"])
        st.metric("Avg Sentiment", f"{avg_score:.1f}")

    st.markdown("---")

    # Sentiment gauges
    st.subheader("📈 Real-time Sentiment Scores")

    # Display top 5 tickers by absolute sentiment score
    sorted_tickers = sorted(
        data["combined"].items(), key=lambda x: abs(x[1]["score"]), reverse=True
    )[:5]

    # Create 5 columns for gauges
    cols = st.columns(5)

    for idx, (ticker, sentiment_data) in enumerate(sorted_tickers):
        with cols[idx]:
            fig = create_sentiment_gauge(
                ticker, sentiment_data["score"], sentiment_data["confidence"]
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Detailed breakdown table
    st.subheader("📋 Detailed Sentiment Breakdown")

    # Create DataFrame for detailed view
    details_data = []
    for ticker, sentiment_data in sorted(
        data["combined"].items(), key=lambda x: x[1]["score"], reverse=True
    ):
        reddit_mentions = 0
        news_articles = 0

        if data["reddit"] and ticker in data["reddit"]["sentiment_by_ticker"]:
            reddit_mentions = data["reddit"]["sentiment_by_ticker"][ticker].get("mentions", 0)

        if data["news"] and ticker in data["news"]["sentiment_by_ticker"]:
            news_data = data["news"]["sentiment_by_ticker"][ticker]
            news_articles = sum(
                source.get("articles", 0) + source.get("messages", 0)
                for source in news_data.get("sources", {}).values()
            )

        details_data.append(
            {
                "Ticker": ticker,
                "Combined Score": f"{sentiment_data['score']:.1f}",
                "Reddit Score": f"{sentiment_data['reddit_score']:.1f}",
                "News Score": f"{sentiment_data['news_score']:.1f}",
                "Confidence": sentiment_data["confidence"].upper(),
                "Reddit Mentions": reddit_mentions,
                "News Articles": news_articles,
                "Signal": (
                    "🟢 BUY"
                    if sentiment_data["score"] > 20
                    else "🔴 SELL"
                    if sentiment_data["score"] < -20
                    else "🟡 HOLD"
                ),
            }
        )

    df = pd.DataFrame(details_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #808495;'>
            Sentiment RAG Dashboard v1.0 | Built with Streamlit & Plotly<br>
            Data sources: Reddit (r/wallstreetbets, r/stocks), Yahoo Finance, Stocktwits, Alpha Vantage
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Auto-refresh implementation
    if auto_refresh:
        import time

        time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
