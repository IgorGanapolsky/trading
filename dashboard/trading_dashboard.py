#!/usr/bin/env python3
"""
Trading System Operational Control Center

Real-time dashboard for monitoring trading system performance,
positions, risk metrics, and system health.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Trading Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Data directory
DATA_DIR = Path("data")


def load_json_file(filepath: Path, default=None):
    """Load JSON file safely."""
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading {filepath}: {e}")
    return default or {}


def get_latest_trades():
    """Get latest trades from today's trade log."""
    today = datetime.now().date()
    trade_file = DATA_DIR / f"trades_{today.isoformat()}.json"

    if trade_file.exists():
        return load_json_file(trade_file, [])

    # Try yesterday's file
    yesterday = today - timedelta(days=1)
    trade_file = DATA_DIR / f"trades_{yesterday.isoformat()}.json"
    return load_json_file(trade_file, [])


def get_performance_data():
    """Get performance log data."""
    perf_file = DATA_DIR / "performance_log.json"
    return load_json_file(perf_file, [])


def get_system_state():
    """Get system state."""
    state_file = DATA_DIR / "system_state.json"
    return load_json_file(state_file, {})


def get_account_summary():
    """Get account summary from Alpaca API and Kalshi."""
    account_data = {
        "equity": 0.0,
        "cash": 0.0,
        "buying_power": 0.0,
        "portfolio_value": 0.0,
        "last_equity": 0.0,
        "positions": [],
        "daytrade_count": 0,
        "pattern_day_trader": False,
    }

    # 1. Alpaca (Equities, ETFs, Crypto)
    try:
        import alpaca_trade_api as tradeapi

        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_SECRET_KEY")

        # Check mode (default to Paper if not specified or explicit 'true')
        is_paper = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes", "on")
        base_url = "https://paper-api.alpaca.markets" if is_paper else "https://api.alpaca.markets"

        if api_key and api_secret:
            api = tradeapi.REST(api_key, api_secret, base_url)
            account = api.get_account()
            positions = api.list_positions()

            account_data["equity"] = float(account.equity)
            account_data["cash"] = float(account.cash)
            account_data["buying_power"] = float(account.buying_power)

            # Use portfolio_value if available, else equity
            if hasattr(account, "portfolio_value"):
                account_data["portfolio_value"] = float(account.portfolio_value)
            else:
                account_data["portfolio_value"] = float(account.equity)

            account_data["last_equity"] = (
                float(account.last_equity)
                if hasattr(account, "last_equity")
                else float(account.equity)
            )

            account_data["daytrade_count"] = getattr(
                account, "daytrade_count", getattr(account, "day_trade_count", 0)
            )
            account_data["pattern_day_trader"] = (
                account.pattern_day_trader if hasattr(account, "pattern_day_trader") else False
            )

            for pos in positions:
                # Determine asset class
                asset_class = pos.asset_class if hasattr(pos, "asset_class") else "Unknown"
                if asset_class == "us_equity":
                    # Simple heuristic: ETFs often not tagged explicitly in all APIs,
                    # but we can label them generally as Equity/ETF
                    asset_class = "Equity/ETF"
                elif asset_class == "crypto":
                    asset_class = "Crypto"

                account_data["positions"].append(
                    {
                        "symbol": pos.symbol,
                        "qty": float(pos.qty),
                        "entry_price": float(pos.avg_entry_price),
                        "current_price": float(pos.current_price),
                        "unrealized_pl": float(pos.unrealized_pl),
                        "unrealized_plpc": float(pos.unrealized_plpc) * 100,
                        "asset_class": asset_class,
                        "source": "Alpaca",
                    }
                )
    except Exception as e:
        st.error(f"Error fetching Alpaca data: {e}")

    # 2. Kalshi (Prediction Markets)
    try:
        from src.brokers.kalshi_client import get_kalshi_client

        # Check mode for Kalshi (can be independent, but using same env var pattern)
        is_kalshi_paper = os.getenv("KALSHI_PAPER", "true").lower() in ("true", "1", "yes", "on")
        kalshi = get_kalshi_client(paper=is_kalshi_paper)

        if kalshi.is_configured():
            try:
                # Add Kalshi balance to cash/equity
                k_account = kalshi.get_account()
                account_data["cash"] += k_account.balance
                account_data["equity"] += k_account.portfolio_value
                account_data["portfolio_value"] += k_account.portfolio_value

                # We assume Kalshi doesn't have "margin" same as Alpaca, so buying power += balance
                account_data["buying_power"] += k_account.balance

                k_positions = kalshi.get_positions()
                for k_pos in k_positions:
                    # Kalshi positions: Side (Yes/No) is important
                    symbol_display = f"{k_pos.market_ticker} ({k_pos.side.upper()})"

                    # Calculate P/L %
                    pl_pct = (
                        (k_pos.unrealized_pl / k_pos.cost_basis * 100)
                        if k_pos.cost_basis > 0
                        else 0.0
                    )

                    account_data["positions"].append(
                        {
                            "symbol": symbol_display,
                            "qty": float(k_pos.quantity),
                            "entry_price": k_pos.avg_price / 100.0,  # Cents to Dollars
                            "current_price": (k_pos.market_value / k_pos.quantity)
                            if k_pos.quantity > 0
                            else 0.0,
                            "unrealized_pl": k_pos.unrealized_pl,
                            "unrealized_plpc": pl_pct,
                            "asset_class": "Prediction",
                            "source": "Kalshi",
                        }
                    )
            except Exception as ke:
                # Log but don't crash if just Kalshi fails
                print(f"Kalshi fetch error: {ke}")

    except ImportError:
        pass  # Kalshi module not found
    except Exception as e:
        st.error(f"Error fetching Kalshi data: {e}")

    return account_data


def calculate_win_rate(trades):
    """Calculate win rate from closed trades."""
    closed_trades = [t for t in trades if t.get("action") == "SELL" or t.get("pl") is not None]
    if not closed_trades:
        return None, 0, 0

    winning = sum(1 for t in closed_trades if t.get("pl", 0) > 0)
    total = len(closed_trades)
    win_rate = (winning / total * 100) if total > 0 else 0

    return win_rate, winning, total


def main():
    """Main dashboard."""
    st.title("📊 Trading System Control Center")
    st.markdown("**Real-time monitoring and operational control**")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ System Status")

        # Check system health
        system_state = get_system_state()
        if system_state:
            last_updated = system_state.get("meta", {}).get("last_updated", "Unknown")
            st.success("✅ System Active")
            st.caption(f"Last Updated: {last_updated}")
        else:
            st.warning("⚠️ System State Not Available")

        # Show recent trades (handles midnight rollover by checking yesterday too)
        recent_trades = get_latest_trades()
        if recent_trades:
            st.info(f"✅ {len(recent_trades)} Recent Trades")
        else:
            st.caption("No recent trades")

        st.divider()

        st.header("🔧 Quick Actions")
        if st.button("🔄 Refresh Data"):
            st.rerun()

        if st.button("📊 View Logs"):
            st.info("Check GitHub Actions for execution logs")

        st.divider()

        st.header("🚨 Manual Override")
        st.caption("Emergency controls")

        if st.button("⏸️ Pause Trading", type="secondary"):
            st.warning("⚠️ Trading pause not implemented yet")

        if st.button("🔄 Force Refresh", type="secondary"):
            st.rerun()

    # Main dashboard
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📈 Performance",
            "💼 Positions",
            "🛡️ Risk",
            "📋 Trades",
            "🚀 Sentiment Boost",
            "🧠 RAG Insights",
        ]
    )

    # Tab 1: Performance
    with tab1:
        st.header("Performance Metrics")

        account = get_account_summary()
        perf_data = get_performance_data()

        if account:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Portfolio Value",
                    f"${account['equity']:,.2f}",
                    delta=(
                        f"${account['equity'] - account['last_equity']:,.2f}"
                        if account.get("last_equity")
                        else None
                    ),
                )

            with col2:
                daily_pl = (
                    account["equity"] - account["last_equity"] if account.get("last_equity") else 0
                )
                st.metric(
                    "Daily P/L",
                    f"${daily_pl:,.2f}",
                    delta=(
                        f"{(daily_pl / account['last_equity'] * 100):.2f}%"
                        if account.get("last_equity") and account["last_equity"] > 0
                        else None
                    ),
                )

            with col3:
                total_pl = account["equity"] - 100000.0  # Starting balance
                st.metric(
                    "Total P/L",
                    f"${total_pl:,.2f}",
                    delta=f"{(total_pl / 100000.0 * 100):.2f}%",
                )

            with col4:
                st.metric("Cash", f"${account['cash']:,.2f}")

            # Win rate
            trades = get_latest_trades()
            win_rate, winning, total_closed = calculate_win_rate(trades)

            if win_rate is not None:
                st.metric("Win Rate", f"{win_rate:.1f}%", f"{winning}/{total_closed} trades")
            else:
                st.metric("Win Rate", "N/A", "No closed trades yet")

            # Performance chart
            if perf_data:
                st.subheader("Performance Trend")
                df = pd.DataFrame(perf_data)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date")

                    st.line_chart(df.set_index("date")[["equity", "pl"]])
        else:
            st.warning("⚠️ Unable to fetch account data. Check API credentials.")

    # Tab 2: Positions
    with tab2:
        st.header("Current Positions")

        account = get_account_summary()
        if account and account.get("positions"):
            positions_df = pd.DataFrame(account["positions"])

            # Format display
            display_df = positions_df.copy()
            display_df["Entry"] = display_df["entry_price"].apply(lambda x: f"${x:.2f}")
            display_df["Current"] = display_df["current_price"].apply(lambda x: f"${x:.2f}")
            display_df["P/L"] = display_df["unrealized_pl"].apply(lambda x: f"${x:,.2f}")
            display_df["P/L %"] = display_df["unrealized_plpc"].apply(lambda x: f"{x:.2f}%")
            display_df["Qty"] = display_df["qty"]
            display_df["Class"] = display_df.get("asset_class", "Unknown")
            display_df["Source"] = display_df.get("source", "Unknown")

            st.dataframe(
                display_df[
                    ["symbol", "Class", "Entry", "Current", "P/L", "P/L %", "Qty", "Source"]
                ],
                use_container_width=True,
                hide_index=True,
            )

            # Position summary
            total_unrealized = sum(p["unrealized_pl"] for p in account["positions"])
            st.metric("Total Unrealized P/L", f"${total_unrealized:,.2f}")
        else:
            st.info("No open positions")

    # Tab 3: Risk
    with tab3:
        st.header("Risk Management Status")

        account = get_account_summary()
        if account:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("PDT Protection")
                daytrade_count = account.get("daytrade_count", 0)
                is_pdt = account.get("pattern_day_trader", False)
                equity = account["equity"]

                if daytrade_count >= 3 and equity < 25000:
                    st.error(
                        f"🚨 BLOCKED: Daytrade count ({daytrade_count}) >= 3 and equity ${equity:,.2f} < $25,000"
                    )
                elif is_pdt and equity < 25000:
                    st.error(
                        f"🚨 BLOCKED: Pattern Day Trader flag set and equity ${equity:,.2f} < $25,000"
                    )
                else:
                    st.success("✅ Trading Allowed")
                    st.caption(f"Daytrade Count: {daytrade_count}/3")
                    st.caption(f"Equity: ${equity:,.2f}")

            with col2:
                st.subheader("Daily Loss Limit")
                daily_pl = (
                    account["equity"] - account["last_equity"] if account.get("last_equity") else 0
                )
                daily_loss_pct = (
                    (daily_pl / account["equity"] * 100) if account["equity"] > 0 else 0
                )
                max_daily_loss = 2.0  # 2% default

                if daily_loss_pct < -max_daily_loss:
                    st.error(
                        f"🚨 BREACHED: Daily loss {daily_loss_pct:.2f}% exceeds limit {-max_daily_loss}%"
                    )
                else:
                    st.success("✅ Within Limits")
                    st.caption(f"Daily P/L: {daily_loss_pct:.2f}%")
                    st.caption(f"Limit: {-max_daily_loss}%")

            # Circuit breaker status
            st.subheader("Circuit Breaker Status")
            if daily_loss_pct < -max_daily_loss or (daytrade_count >= 3 and equity < 25000):
                st.error("🔴 CIRCUIT BREAKER ACTIVE - Trading Blocked")
            else:
                st.success("🟢 CIRCUIT BREAKER OK - Trading Allowed")
        else:
            st.warning("⚠️ Unable to fetch risk data")

    # Tab 4: Trades
    with tab4:
        st.header("Recent Trades")

        trades = get_latest_trades()
        if trades:
            # Show last 20 trades
            recent_trades = trades[-20:]
            df = pd.DataFrame(recent_trades)

            # Format display
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp", ascending=False)

            st.dataframe(df, use_container_width=True, hide_index=True)

            # Trade statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Trades Today",
                    len(
                        [
                            t
                            for t in trades
                            if t.get("timestamp", "").startswith(str(datetime.now().date()))
                        ]
                    ),
                )
            with col2:
                win_rate, winning, total = calculate_win_rate(trades)
                if win_rate is not None:
                    st.metric("Win Rate", f"{win_rate:.1f}%")
                else:
                    st.metric("Win Rate", "N/A")
            with col3:
                total_amount = sum(t.get("amount", 0) for t in trades if t.get("amount"))
                st.metric("Total Invested", f"${total_amount:,.2f}")
        else:
            st.info("No trades recorded yet")

    # Tab 5: Sentiment Boost
    with tab5:
        st.header("Sentiment Boost Signals")

        account = get_account_summary()
        if account and account.get("positions"):
            st.subheader("Active Sentiment Boost Analysis")

            # Check for sentiment boost opportunities
            try:
                from src.utils.sentiment_boost import calculate_sentiment_boost

                positions = account["positions"]
                boost_opportunities = []

                for pos in positions:
                    symbol = pos["symbol"]
                    pos["current_price"]
                    pos["entry_price"]
                    technical_score = 50.0  # Placeholder - would come from actual analysis

                    # Calculate sentiment boost
                    boost_amount, boost_info = calculate_sentiment_boost(
                        symbol=symbol,
                        base_amount=100.0,  # Example amount
                        technical_score=technical_score,
                        sentiment_threshold=0.8,
                        boost_multiplier=1.2,
                    )

                    if boost_info.get("boost_applied"):
                        boost_opportunities.append(
                            {
                                "symbol": symbol,
                                "boost_applied": True,
                                "reason": boost_info.get("reason", ""),
                                "sentiment_score": boost_info.get("sentiment_score", 0),
                                "technical_score": technical_score,
                            }
                        )

                if boost_opportunities:
                    st.success(f"✅ {len(boost_opportunities)} Active Sentiment Boost Signals")
                    for opp in boost_opportunities:
                        with st.expander(f"🚀 {opp['symbol']} - Boost Active"):
                            st.write(f"**Reason**: {opp['reason']}")
                            st.write(f"**Sentiment Score**: {opp['sentiment_score']:.2f}")
                            st.write(f"**Technical Score**: {opp['technical_score']:.2f}")
                else:
                    st.info("No active sentiment boost signals")

            except ImportError:
                st.warning("⚠️ Sentiment boost module not available")
            except Exception as e:
                st.error(f"Error checking sentiment boost: {e}")
        else:
            st.info("No positions to analyze")

        # Sentiment boost configuration
        st.subheader("Configuration")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Sentiment Threshold", "0.8", "80%")
        with col2:
            st.metric("Boost Multiplier", "1.2x", "+20%")

    # Tab 6: RAG Insights - Knowledge that helped trading decisions
    with tab6:
        st.header("🧠 RAG Knowledge Insights")
        st.caption("Latest knowledge from our RAG system that informed trading decisions")

        # Try to load RAG insights
        rag_available = False

        try:
            from src.rag.lightweight_rag import LightweightRAG

            rag = LightweightRAG()
            rag_available = True
            rag_stats = rag.get_stats()
        except ImportError:
            try:
                from src.rag.vector_db.chroma_client import TradingRAGDatabase

                rag = TradingRAGDatabase()
                rag_available = True
                rag_stats = rag.get_stats()
            except ImportError:
                rag_stats = {}

        # RAG System Status
        col1, col2, col3 = st.columns(3)
        with col1:
            doc_count = rag_stats.get("total_documents", rag_stats.get("document_count", 0))
            st.metric("📚 Total Documents", f"{doc_count:,}")
        with col2:
            sources = rag_stats.get("sources", [])
            st.metric("📰 Data Sources", len(sources) if isinstance(sources, list) else sources)
        with col3:
            status = "🟢 Active" if rag_available else "🟡 Fallback Mode"
            st.metric("Status", status)

        st.divider()

        # Get current positions for context
        account = get_account_summary()
        current_tickers = []
        if account and account.get("positions"):
            current_tickers = [p["symbol"] for p in account["positions"]]

        # Query RAG for insights on current holdings
        if rag_available and current_tickers:
            st.subheader("💡 Insights for Current Holdings")

            for ticker in current_tickers[:5]:  # Limit to 5 tickers
                try:
                    # Try get_latest_insights if available (LightweightRAG)
                    if hasattr(rag, "get_latest_insights"):
                        ticker_insights = rag.get_latest_insights(ticker=ticker, n=3)
                    else:
                        # Fallback to query
                        ticker_insights = rag.query(f"{ticker} trading analysis", n_results=3)

                    if ticker_insights:
                        with st.expander(
                            f"📊 {ticker} - {len(ticker_insights)} insights", expanded=False
                        ):
                            for i, insight in enumerate(ticker_insights, 1):
                                content = insight.get("content", insight.get("document", ""))[:300]
                                source = insight.get("metadata", {}).get(
                                    "source", insight.get("source", "unknown")
                                )
                                date = insight.get("metadata", {}).get(
                                    "date", insight.get("date", "")
                                )

                                st.markdown(f"**{i}. [{source}]** {date}")
                                st.info(content + "..." if len(content) >= 300 else content)
                except Exception as e:
                    st.warning(f"Could not fetch insights for {ticker}: {e}")

        elif not current_tickers:
            st.info("No current positions - insights will appear when you hold positions")

        st.divider()

        # Recent Market Insights (general)
        st.subheader("📈 Recent Market Knowledge")

        if rag_available:
            try:
                # Get general market insights
                if hasattr(rag, "get_latest_insights"):
                    market_insights = rag.get_latest_insights(n=5)
                else:
                    market_insights = rag.query("market analysis trading strategy", n_results=5)

                if market_insights:
                    for insight in market_insights:
                        content = insight.get("content", insight.get("document", ""))[:200]
                        source = insight.get("metadata", {}).get(
                            "source", insight.get("source", "RAG")
                        )
                        ticker = insight.get("metadata", {}).get("ticker", "")

                        ticker_badge = f"**[{ticker}]**" if ticker else ""
                        st.markdown(f"• {ticker_badge} _{source}_: {content}...")
                else:
                    st.info("No recent insights available")
            except Exception as e:
                st.warning(f"Could not load market insights: {e}")
        else:
            st.warning("⚠️ RAG system not available. Install with: `pip install fastembed lancedb`")

        st.divider()

        # Lessons Learned Section
        st.subheader("📖 Lessons Learned (Risk Prevention)")

        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            ll_rag = LessonsLearnedRAG()

            # Get recent lessons
            recent_lessons = ll_rag.get_recent_lessons(n=3)
            if recent_lessons:
                for lesson in recent_lessons:
                    severity = lesson.get("severity", "medium")
                    severity_color = {
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢",
                    }.get(severity, "⚪")

                    with st.expander(
                        f"{severity_color} {lesson.get('title', 'Lesson')}", expanded=False
                    ):
                        st.write(lesson.get("description", lesson.get("content", "")))
                        if lesson.get("prevention"):
                            st.success(f"**Prevention**: {lesson['prevention']}")
            else:
                st.info("No lessons learned recorded yet")
        except ImportError:
            # Try loading from files directly
            lessons_dir = Path("rag_knowledge/lessons_learned")
            if lessons_dir.exists():
                lesson_files = sorted(lessons_dir.glob("ll_*.md"), reverse=True)[:3]
                for lf in lesson_files:
                    with st.expander(f"📄 {lf.stem}", expanded=False):
                        content = lf.read_text()[:500]
                        st.markdown(content + "..." if len(content) >= 500 else content)
            else:
                st.info("Lessons learned module not available")
        except Exception as e:
            st.warning(f"Could not load lessons: {e}")

        # RAG Configuration
        st.divider()
        st.subheader("⚙️ RAG Configuration")

        col1, col2 = st.columns(2)
        with col1:
            st.code(f"""
RAG Backend: {"LanceDB (Lightweight)" if rag_available else "Fallback Mode"}
Embedding Model: BAAI/bge-small-en-v1.5
Vector Dimensions: 384
Storage: data/rag/lance_db/
            """)
        with col2:
            if st.button("🔄 Refresh RAG Stats"):
                st.rerun()
            if st.button("📊 Run RAG Health Check"):
                try:
                    import subprocess

                    result = subprocess.run(
                        ["python3", "scripts/rag_health_check.py"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    st.code((result.stdout + result.stderr)[:1000])
                except Exception as e:
                    st.error(f"Health check failed: {e}")


if __name__ == "__main__":
    main()
