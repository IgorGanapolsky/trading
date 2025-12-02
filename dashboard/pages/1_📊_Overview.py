"""
Overview Page - High-level sentiment metrics and market regime analysis.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from dashboard.utils.chart_builders import COLORS

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

st.title("📊 Sentiment Overview")
st.markdown("High-level market sentiment analysis and key metrics")


@st.cache_data(ttl=60)
def load_latest_sentiment(data_dir: Path):
    """Load most recent sentiment data."""
    available_files = sorted(data_dir.glob("news_*.json"), reverse=True)

    if not available_files:
        return None

    latest_date = available_files[0].stem.split("_", 1)[1]

    reddit_file = data_dir / f"reddit_{latest_date}.json"
    news_file = data_dir / f"news_{latest_date}.json"

    data = {"reddit": None, "news": None, "combined": {}}

    if reddit_file.exists():
        with open(reddit_file) as f:
            data["reddit"] = json.load(f)

    if news_file.exists():
        with open(news_file) as f:
            data["news"] = json.load(f)

    # Combine scores
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
            reddit_score = min(100, max(-100, reddit_data.get("score", 0) / 2))

        if data["news"] and ticker in data["news"]["sentiment_by_ticker"]:
            news_score = data["news"]["sentiment_by_ticker"][ticker].get("score", 0)

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


def main():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "sentiment"

    data = load_latest_sentiment(data_dir)

    if not data or not data["combined"]:
        st.warning("No sentiment data available. Run collection scripts first.")
        return

    # Calculate key metrics
    total_tickers = len(data["combined"])
    avg_sentiment = sum(s["score"] for s in data["combined"].values()) / total_tickers

    bullish_tickers = [t for t, s in data["combined"].items() if s["score"] > 20]
    bearish_tickers = [t for t, s in data["combined"].items() if s["score"] < -20]
    neutral_tickers = [t for t, s in data["combined"].items() if -20 <= s["score"] <= 20]

    high_confidence = sum(1 for s in data["combined"].values() if s["confidence"] == "high")

    # Market regime determination
    if avg_sentiment > 20:
        regime = "RISK ON"
        regime_class = "bullish"
        regime_emoji = "🟢"
    elif avg_sentiment < -20:
        regime = "RISK OFF"
        regime_class = "bearish"
        regime_emoji = "🔴"
    else:
        regime = "NEUTRAL"
        regime_class = "neutral"
        regime_emoji = "🟡"

    # Market regime banner
    st.markdown(
        f"""
        <div class="big-metric {regime_class}" style="font-size: 4rem; padding: 2rem;">
            {regime_emoji} Market Regime: {regime}
        </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Average Sentiment",
            f"{avg_sentiment:.1f}",
            delta=None,
            help="Overall market sentiment score (-100 to 100)",
        )

    with col2:
        st.metric(
            "Total Tickers Analyzed",
            total_tickers,
            help="Number of stocks with sentiment data",
        )

    with col3:
        st.metric(
            "High Confidence Signals",
            high_confidence,
            delta=f"{(high_confidence / total_tickers) * 100:.0f}%",
            help="Signals with strong conviction",
        )

    with col4:
        bull_bear_ratio = len(bullish_tickers) / max(len(bearish_tickers), 1)
        st.metric(
            "Bull/Bear Ratio",
            f"{bull_bear_ratio:.2f}",
            help="Ratio of bullish to bearish signals",
        )

    st.markdown("---")

    # Sentiment distribution
    st.subheader("📊 Sentiment Distribution")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div style='background: {COLORS["bullish"]}20; padding: 1.5rem; border-radius: 10px; border-left: 5px solid {COLORS["bullish"]}'>
                <h2 style='color: {COLORS["bullish"]}; margin: 0;'>{len(bullish_tickers)}</h2>
                <p style='color: {COLORS["text"]}; margin: 0.5rem 0 0 0;'>Bullish Signals</p>
                <p style='color: {COLORS["secondary"]}; font-size: 0.9rem; margin: 0;'>
                    {", ".join(bullish_tickers[:5])}{" +more" if len(bullish_tickers) > 5 else ""}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style='background: {COLORS["neutral"]}20; padding: 1.5rem; border-radius: 10px; border-left: 5px solid {COLORS["neutral"]}'>
                <h2 style='color: {COLORS["neutral"]}; margin: 0;'>{len(neutral_tickers)}</h2>
                <p style='color: {COLORS["text"]}; margin: 0.5rem 0 0 0;'>Neutral Signals</p>
                <p style='color: {COLORS["secondary"]}; font-size: 0.9rem; margin: 0;'>
                    {", ".join(neutral_tickers[:5])}{" +more" if len(neutral_tickers) > 5 else ""}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div style='background: {COLORS["bearish"]}20; padding: 1.5rem; border-radius: 10px; border-left: 5px solid {COLORS["bearish"]}'>
                <h2 style='color: {COLORS["bearish"]}; margin: 0;'>{len(bearish_tickers)}</h2>
                <p style='color: {COLORS["text"]}; margin: 0.5rem 0 0 0;'>Bearish Signals</p>
                <p style='color: {COLORS["secondary"]}; font-size: 0.9rem; margin: 0;'>
                    {", ".join(bearish_tickers[:5])}{" +more" if len(bearish_tickers) > 5 else ""}
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Top movers
    st.subheader("🚀 Top Sentiment Movers")

    col1, col2 = st.columns(2)

    # Most bullish
    most_bullish = sorted(data["combined"].items(), key=lambda x: x[1]["score"], reverse=True)[:5]

    with col1:
        st.markdown("**Most Bullish**")
        for ticker, sentiment_data in most_bullish:
            st.markdown(
                f"""
                <div style='background: {COLORS["grid"]}; padding: 0.8rem; margin: 0.5rem 0; border-radius: 5px; border-left: 3px solid {COLORS["bullish"]}'>
                    <strong>{ticker}</strong>: {sentiment_data["score"]:.1f}
                    <span style='color: {COLORS["secondary"]}; float: right;'>{sentiment_data["confidence"]}</span>
                </div>
            """,
                unsafe_allow_html=True,
            )

    # Most bearish
    most_bearish = sorted(data["combined"].items(), key=lambda x: x[1]["score"])[:5]

    with col2:
        st.markdown("**Most Bearish**")
        for ticker, sentiment_data in most_bearish:
            st.markdown(
                f"""
                <div style='background: {COLORS["grid"]}; padding: 0.8rem; margin: 0.5rem 0; border-radius: 5px; border-left: 3px solid {COLORS["bearish"]}'>
                    <strong>{ticker}</strong>: {sentiment_data["score"]:.1f}
                    <span style='color: {COLORS["secondary"]}; float: right;'>{sentiment_data["confidence"]}</span>
                </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Data freshness
    if data["news"]:
        timestamp = data["news"]["meta"].get("timestamp")
        if timestamp:
            last_update = datetime.fromisoformat(timestamp)
            time_ago = datetime.now() - last_update
            hours_ago = time_ago.total_seconds() / 3600

            freshness_color = (
                COLORS["bullish"]
                if hours_ago < 1
                else COLORS["neutral"]
                if hours_ago < 6
                else COLORS["bearish"]
            )

            st.markdown(
                f"""
                <div style='text-align: center; padding: 1rem; background: {COLORS["grid"]}; border-radius: 8px;'>
                    <p style='color: {freshness_color}; font-size: 1.2rem; margin: 0;'>
                        Data last updated: {last_update.strftime("%Y-%m-%d %I:%M %p")}
                        ({hours_ago:.1f} hours ago)
                    </p>
                </div>
            """,
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    # Apply custom CSS
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
        </style>
    """,
        unsafe_allow_html=True,
    )

    main()
