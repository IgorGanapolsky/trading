"""
Historical Trends Page - 30-day sentiment trends and correlation analysis.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).parent.parent.parent))

from dashboard.utils.chart_builders import (
    COLORS,
    create_sentiment_timeline,
    create_win_rate_by_sentiment_bar,
)

st.set_page_config(page_title="Historical Trends", page_icon="📈", layout="wide")

st.title("📈 Historical Sentiment Trends")
st.markdown("30-day view of sentiment evolution and correlation with returns")


@st.cache_data(ttl=300)
def load_historical_sentiment(data_dir: Path, days: int = 30):
    """Load historical sentiment data for the past N days."""
    sentiment_history = []
    end_date = datetime.now()

    for i in range(days):
        date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")

        reddit_file = data_dir / f"reddit_{date}.json"
        news_file = data_dir / f"news_{date}.json"

        if not reddit_file.exists() and not news_file.exists():
            continue

        day_data = {"date": date, "tickers": {}}

        # Load Reddit data
        if reddit_file.exists():
            with open(reddit_file) as f:
                reddit_data = json.load(f)
                for ticker, data in reddit_data["sentiment_by_ticker"].items():
                    if ticker not in day_data["tickers"]:
                        day_data["tickers"][ticker] = {
                            "reddit_score": 0,
                            "news_score": 0,
                        }
                    day_data["tickers"][ticker]["reddit_score"] = min(
                        100, max(-100, data.get("score", 0) / 2)
                    )

        # Load news data
        if news_file.exists():
            with open(news_file) as f:
                news_data = json.load(f)
                for ticker, data in news_data["sentiment_by_ticker"].items():
                    if ticker not in day_data["tickers"]:
                        day_data["tickers"][ticker] = {
                            "reddit_score": 0,
                            "news_score": 0,
                        }
                    day_data["tickers"][ticker]["news_score"] = data.get("score", 0)

        # Calculate combined scores
        for ticker, scores in day_data["tickers"].items():
            combined = (scores["reddit_score"] * 0.4) + (scores["news_score"] * 0.6)
            day_data["tickers"][ticker]["combined_score"] = combined

        sentiment_history.append(day_data)

    return sentiment_history


@st.cache_data(ttl=300)
def load_performance_data(data_dir: Path):
    """Load historical performance data."""
    perf_file = data_dir / "performance_log.json"

    if not perf_file.exists():
        return None

    with open(perf_file) as f:
        return json.load(f)


def calculate_correlation(sentiment_df: pd.DataFrame, returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate correlation between sentiment and returns."""
    # Merge on date and ticker
    merged = pd.merge(sentiment_df, returns_df, on=["date", "ticker"], how="inner")

    if merged.empty:
        return pd.DataFrame()

    # Calculate correlation by ticker
    correlations = {}
    for ticker in merged["ticker"].unique():
        ticker_data = merged[merged["ticker"] == ticker]
        if len(ticker_data) > 1:
            corr = ticker_data["sentiment"].corr(ticker_data["return"])
            correlations[ticker] = corr

    # Create correlation matrix
    if correlations:
        return pd.DataFrame([correlations], index=["Correlation"])
    return pd.DataFrame()


def main():
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "sentiment"
    parent_data_dir = project_root / "data"

    # Sidebar options
    st.sidebar.subheader("Historical Analysis Options")
    days_to_show = st.sidebar.slider("Days to analyze", 7, 30, 30)
    top_n_tickers = st.sidebar.slider("Top tickers to display", 3, 10, 5)

    # Load data
    sentiment_history = load_historical_sentiment(data_dir, days_to_show)

    if not sentiment_history:
        st.warning("No historical sentiment data available.")
        st.info("Historical data will accumulate as the system runs daily.")
        return

    st.success(f"Loaded {len(sentiment_history)} days of sentiment data")

    # Convert to DataFrame for timeline
    timeline_data = []
    for day in sentiment_history:
        for ticker, scores in day["tickers"].items():
            timeline_data.append(
                {
                    "date": datetime.strptime(day["date"], "%Y-%m-%d"),
                    "ticker": ticker,
                    "score": scores["combined_score"],
                }
            )

    if not timeline_data:
        st.warning("No data to display")
        return

    df_timeline = pd.DataFrame(timeline_data)

    # Get top tickers by frequency
    ticker_counts = df_timeline["ticker"].value_counts()
    top_tickers = ticker_counts.head(top_n_tickers).index.tolist()

    # Sentiment timeline chart
    st.subheader(f"📊 Sentiment Timeline - Top {top_n_tickers} Tickers")

    filtered_df = df_timeline[df_timeline["ticker"].isin(top_tickers)]
    fig_timeline = create_sentiment_timeline(filtered_df, top_tickers)
    st.plotly_chart(fig_timeline, use_container_width=True)

    st.markdown("---")

    # Statistics summary
    st.subheader("📈 Sentiment Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Average Sentiment by Ticker**")
        avg_sentiment = (
            df_timeline.groupby("ticker")["score"].mean().sort_values(ascending=False).head(10)
        )

        stats_df = pd.DataFrame(
            {
                "Ticker": avg_sentiment.index,
                "Avg Sentiment": avg_sentiment.values.round(1),
                "Trend": [
                    ("🟢 Bullish" if x > 20 else "🔴 Bearish" if x < -20 else "🟡 Neutral")
                    for x in avg_sentiment.values
                ],
            }
        )
        st.dataframe(stats_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**Sentiment Volatility (Std Dev)**")
        volatility = (
            df_timeline.groupby("ticker")["score"].std().sort_values(ascending=False).head(10)
        )

        vol_df = pd.DataFrame(
            {
                "Ticker": volatility.index,
                "Volatility": volatility.values.round(1),
                "Stability": [
                    "⚠️ High" if x > 30 else "✅ Low" if x < 15 else "➡️ Medium"
                    for x in volatility.values
                ],
            }
        )
        st.dataframe(vol_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Correlation analysis (if performance data available)
    st.subheader("🔗 Sentiment vs Returns Correlation")

    perf_data = load_performance_data(parent_data_dir)

    if perf_data and len(perf_data) > 1:
        # Calculate daily returns
        perf_df = pd.DataFrame(perf_data)
        perf_df["date"] = pd.to_datetime(perf_df["date"])
        perf_df = perf_df.sort_values("date")
        perf_df["daily_return"] = perf_df["pl_pct"].pct_change() * 100

        st.markdown(
            f"""
            <div style='background: {COLORS["grid"]}; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                <p style='color: {COLORS["text"]}; margin: 0;'>
                    <strong>Correlation Analysis:</strong> Comparing sentiment scores with actual portfolio returns.
                    High positive correlation indicates sentiment is a good predictor of returns.
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # Calculate overall correlation
        if len(perf_df) > 2:
            # Simple correlation between average sentiment and returns
            daily_sentiment = df_timeline.groupby("date")["score"].mean().reset_index()
            daily_sentiment["date"] = pd.to_datetime(daily_sentiment["date"])

            merged_data = pd.merge(
                daily_sentiment,
                perf_df[["date", "daily_return"]],
                on="date",
                how="inner",
            )

            if len(merged_data) > 2:
                overall_corr = merged_data["score"].corr(merged_data["daily_return"])

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Overall Correlation", f"{overall_corr:.3f}")

                with col2:
                    corr_strength = (
                        "Strong"
                        if abs(overall_corr) > 0.7
                        else "Moderate"
                        if abs(overall_corr) > 0.4
                        else "Weak"
                    )
                    st.metric("Correlation Strength", corr_strength)

                with col3:
                    predictive = "Yes ✅" if abs(overall_corr) > 0.5 else "No ❌"
                    st.metric("Predictive Value", predictive)

                # Scatter plot
                import plotly.express as px

                fig_scatter = px.scatter(
                    merged_data,
                    x="score",
                    y="daily_return",
                    trendline="ols",
                    title="Sentiment vs Daily Returns",
                    labels={
                        "score": "Sentiment Score",
                        "daily_return": "Daily Return (%)",
                    },
                )

                fig_scatter.update_layout(
                    paper_bgcolor=COLORS["background"],
                    plot_bgcolor=COLORS["background"],
                    font={"color": COLORS["text"]},
                    xaxis=dict(gridcolor=COLORS["grid"]),
                    yaxis=dict(gridcolor=COLORS["grid"]),
                )

                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.info("Not enough overlapping data for correlation analysis.")
        else:
            st.info("Not enough performance data for correlation analysis.")
    else:
        st.info(
            "Performance data not available. Correlation analysis will be available after trades are executed."
        )

    st.markdown("---")

    # Win rate by sentiment level (simulated for now)
    st.subheader("🎯 Win Rate by Sentiment Level")

    st.markdown(
        f"""
        <div style='background: {COLORS["grid"]}; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
            <p style='color: {COLORS["text"]}; margin: 0;'>
                <strong>Analysis:</strong> Breakdown of trading success rate by sentiment strength.
                This helps validate whether stronger sentiment signals lead to better outcomes.
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Generate sample win rate data (will be replaced with real data)
    win_rate_data = pd.DataFrame(
        {
            "sentiment_range": [
                "Very Bearish (< -50)",
                "Bearish (-50 to -20)",
                "Neutral (-20 to 20)",
                "Bullish (20 to 50)",
                "Very Bullish (> 50)",
            ],
            "win_rate": [45.0, 48.0, 52.0, 58.0, 65.0],
            "trade_count": [5, 12, 25, 18, 8],
        }
    )

    fig_winrate = create_win_rate_by_sentiment_bar(win_rate_data)
    st.plotly_chart(fig_winrate, use_container_width=True)

    st.info(
        "Note: Win rate data shown is simulated. Real data will appear once sufficient trades are executed."
    )

    st.markdown("---")

    # Data quality metrics
    st.subheader("📊 Data Quality Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        total_days = len(sentiment_history)
        st.metric("Days of Data", total_days)

    with col2:
        total_tickers = df_timeline["ticker"].nunique()
        st.metric("Unique Tickers", total_tickers)

    with col3:
        total_datapoints = len(timeline_data)
        st.metric("Total Data Points", total_datapoints)


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
