"""
Data Sources Page - Breakdown of sentiment data by source and API usage metrics.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from dashboard.utils.chart_builders import (
    COLORS,
    create_source_breakdown_pie,
)

st.set_page_config(page_title="Data Sources", page_icon="🔍", layout="wide")

st.title("🔍 Sentiment Data Sources")
st.markdown("Breakdown of data collection across platforms and API usage metrics")


@st.cache_data(ttl=300)
def load_source_data(data_dir: Path):
    """Load data from all sentiment sources."""
    latest_files = {"reddit": None, "news": None}

    # Find latest files
    reddit_files = sorted(data_dir.glob("reddit_*.json"), reverse=True)
    news_files = sorted(data_dir.glob("news_*.json"), reverse=True)

    if reddit_files:
        with open(reddit_files[0]) as f:
            latest_files["reddit"] = json.load(f)

    if news_files:
        with open(news_files[0]) as f:
            latest_files["news"] = json.load(f)

    return latest_files


def main():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "sentiment"

    source_data = load_source_data(data_dir)

    if not source_data["reddit"] and not source_data["news"]:
        st.warning("No source data available.")
        return

    # Overview metrics
    st.subheader("📊 Data Source Overview")

    col1, col2, col3, col4 = st.columns(4)

    # Reddit metrics
    reddit_meta = source_data.get("reddit", {}).get("meta", {})
    reddit_total_posts = reddit_meta.get("total_posts", 0)
    reddit_tickers = reddit_meta.get("total_tickers", 0)

    with col1:
        st.metric("Reddit Posts", reddit_total_posts)

    with col2:
        st.metric("Reddit Tickers", reddit_tickers)

    # News metrics
    news_meta = source_data.get("news", {}).get("meta", {})
    news_tickers = news_meta.get("tickers_analyzed", 0)

    # Calculate total articles
    total_articles = 0
    if source_data.get("news"):
        for ticker_data in source_data["news"].get("sentiment_by_ticker", {}).values():
            sources = ticker_data.get("sources", {})
            for source in sources.values():
                total_articles += source.get("articles", 0) + source.get("messages", 0)

    with col3:
        st.metric("News Articles", total_articles)

    with col4:
        st.metric("News Tickers", news_tickers)

    st.markdown("---")

    # Source breakdown
    st.subheader("📈 Data Volume by Source")

    # Calculate source breakdown
    source_counts = {}

    # Reddit sources
    if source_data.get("reddit"):
        subreddits = reddit_meta.get("subreddits", [])
        for sub in subreddits:
            # Estimate posts per subreddit (simplified)
            source_counts[f"Reddit: r/{sub}"] = (
                reddit_total_posts // len(subreddits) if subreddits else 0
            )

    # News sources
    if source_data.get("news"):
        news_sources = news_meta.get("sources", [])
        articles_per_source = total_articles // len(news_sources) if news_sources else 0
        for source in news_sources:
            source_counts[f"News: {source.title()}"] = articles_per_source

    if source_counts:
        col1, col2 = st.columns([1, 1])

        with col1:
            fig_pie = create_source_breakdown_pie(source_counts)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            st.markdown("**Source Details**")

            source_df = pd.DataFrame(
                [
                    {
                        "Source": k,
                        "Count": v,
                        "Percentage": f"{(v / sum(source_counts.values()) * 100):.1f}%",
                    }
                    for k, v in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
                ]
            )

            st.dataframe(source_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Reddit breakdown
    st.subheader("🗣️ Reddit Sentiment Breakdown")

    if source_data.get("reddit"):
        reddit_sentiments = source_data["reddit"].get("sentiment_by_ticker", {})

        reddit_data = []
        for ticker, data in reddit_sentiments.items():
            reddit_data.append(
                {
                    "Ticker": ticker,
                    "Score": data.get("score", 0),
                    "Mentions": data.get("mentions", 0),
                    "Bullish Keywords": data.get("bullish_keywords", 0),
                    "Bearish Keywords": data.get("bearish_keywords", 0),
                    "Confidence": data.get("confidence", "unknown").upper(),
                    "Sentiment": (
                        "🟢 Bullish"
                        if data.get("score", 0) > 50
                        else ("🔴 Bearish" if data.get("score", 0) < -50 else "🟡 Neutral")
                    ),
                }
            )

        reddit_df = pd.DataFrame(reddit_data).sort_values("Mentions", ascending=False)
        st.dataframe(reddit_df, use_container_width=True, hide_index=True)

        # Reddit statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            avg_mentions = reddit_df["Mentions"].mean() if len(reddit_df) > 0 else 0
            st.metric("Avg Mentions per Ticker", f"{avg_mentions:.1f}")

        with col2:
            total_bullish_kw = reddit_df["Bullish Keywords"].sum()
            st.metric("Total Bullish Keywords", total_bullish_kw)

        with col3:
            total_bearish_kw = reddit_df["Bearish Keywords"].sum()
            st.metric("Total Bearish Keywords", total_bearish_kw)

    else:
        st.info("No Reddit data available")

    st.markdown("---")

    # News breakdown
    st.subheader("📰 News Sentiment Breakdown")

    if source_data.get("news"):
        news_sentiments = source_data["news"].get("sentiment_by_ticker", {})

        news_data = []
        for ticker, data in news_sentiments.items():
            sources = data.get("sources", {})

            # Calculate total articles/messages
            total_sources = 0
            source_details = []
            for source_name, source_info in sources.items():
                count = source_info.get("articles", 0) + source_info.get("messages", 0)
                total_sources += count
                source_details.append(f"{source_name}: {count}")

            news_data.append(
                {
                    "Ticker": ticker,
                    "Score": data.get("score", 0),
                    "Confidence": data.get("confidence", "unknown").upper(),
                    "Sources": len(sources),
                    "Total Articles": total_sources,
                    "Source Details": ", ".join(source_details),
                    "Sentiment": (
                        "🟢 Bullish"
                        if data.get("score", 0) > 20
                        else ("🔴 Bearish" if data.get("score", 0) < -20 else "🟡 Neutral")
                    ),
                }
            )

        news_df = pd.DataFrame(news_data).sort_values("Score", ascending=False)
        st.dataframe(news_df, use_container_width=True, hide_index=True)

        # News statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            avg_score = news_df["Score"].mean() if len(news_df) > 0 else 0
            st.metric("Avg News Score", f"{avg_score:.1f}")

        with col2:
            total_news_articles = news_df["Total Articles"].sum()
            st.metric("Total Articles Analyzed", total_news_articles)

        with col3:
            avg_sources = news_df["Sources"].mean() if len(news_df) > 0 else 0
            st.metric("Avg Sources per Ticker", f"{avg_sources:.1f}")

    else:
        st.info("No news data available")

    st.markdown("---")

    # API Usage Metrics
    st.subheader("🔌 API Usage & Rate Limits")

    st.markdown(
        f"""
        <div style='background: {COLORS["grid"]}; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem;'>
            <h4 style='color: {COLORS["text"]}; margin-top: 0;'>Data Source APIs</h4>
            <p style='color: {COLORS["secondary"]}; margin-bottom: 0;'>
                All data sources use free tier APIs with generous rate limits.
                No additional costs for sentiment collection.
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # API metrics table
    api_data = pd.DataFrame(
        {
            "API": ["Reddit (PRAW)", "Yahoo Finance", "Stocktwits", "Alpha Vantage"],
            "Status": ["✅ Active", "✅ Active", "✅ Active", "⏸️ Standby"],
            "Rate Limit": ["100 req/min", "Unlimited", "200 req/hour", "25 req/day"],
            "Usage Today": [
                f"{reddit_total_posts} posts",
                f"{total_articles // 2} articles",
                f"{total_articles // 2} messages",
                "0 calls",
            ],
            "Cost": ["$0 (Free)", "$0 (Free)", "$0 (Free)", "$0 (Free)"],
        }
    )

    st.dataframe(api_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Data quality metrics
    st.subheader("✅ Data Quality Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Coverage - percentage of target tickers with data
        target_tickers = ["SPY", "QQQ", "NVDA", "GOOGL", "AMZN", "TSLA"]
        covered_tickers = set()

        if source_data.get("reddit"):
            covered_tickers.update(source_data["reddit"].get("sentiment_by_ticker", {}).keys())
        if source_data.get("news"):
            covered_tickers.update(source_data["news"].get("sentiment_by_ticker", {}).keys())

        coverage = (
            len([t for t in target_tickers if t in covered_tickers]) / len(target_tickers) * 100
        )

        st.metric(
            "Ticker Coverage",
            f"{coverage:.0f}%",
            help="Percentage of target tickers with sentiment data",
        )

    with col2:
        # Freshness - hours since last update
        freshness_hours = 0
        if source_data.get("news"):
            timestamp = source_data["news"]["meta"].get("timestamp")
            if timestamp:
                last_update = datetime.fromisoformat(timestamp)
                freshness_hours = (datetime.now() - last_update).total_seconds() / 3600

        freshness_color = "normal" if freshness_hours < 6 else "inverse"

        st.metric(
            "Data Freshness",
            f"{freshness_hours:.1f}h",
            delta=None,
            delta_color=freshness_color,
            help="Hours since last data update",
        )

    with col3:
        # Confidence - percentage of high confidence signals
        high_conf = 0
        total_signals = 0

        if source_data.get("reddit"):
            for ticker_data in source_data["reddit"].get("sentiment_by_ticker", {}).values():
                total_signals += 1
                if ticker_data.get("confidence") == "high":
                    high_conf += 1

        if source_data.get("news"):
            for ticker_data in source_data["news"].get("sentiment_by_ticker", {}).values():
                total_signals += 1
                if ticker_data.get("confidence") == "high":
                    high_conf += 1

        conf_pct = (high_conf / total_signals * 100) if total_signals > 0 else 0

        st.metric(
            "High Confidence %",
            f"{conf_pct:.0f}%",
            help="Percentage of signals with high confidence",
        )

    st.markdown("---")

    # Data collection schedule
    st.subheader("⏰ Collection Schedule")

    st.markdown(
        f"""
        <div style='background: {COLORS["grid"]}; padding: 1.5rem; border-radius: 10px;'>
            <h4 style='color: {COLORS["text"]}; margin-top: 0;'>Automated Data Collection</h4>
            <ul style='color: {COLORS["text"]};'>
                <li><strong>Reddit Sentiment:</strong> Every 4 hours (6x daily)</li>
                <li><strong>News Sentiment:</strong> Every 2 hours (12x daily)</li>
                <li><strong>Alpha Vantage:</strong> Once daily at 8:00 AM ET</li>
                <li><strong>YouTube Analysis:</strong> Daily at 8:00 AM ET</li>
            </ul>
            <p style='color: {COLORS["secondary"]}; margin-bottom: 0;'>
                All collection is fully automated and requires zero manual intervention.
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLORS["background"]};
        }}
        </style>
    """,
        unsafe_allow_html=True,
    )

    main()
