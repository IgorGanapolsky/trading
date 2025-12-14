#!/usr/bin/env python3
"""
Path to $100/Day Dashboard

Real-time visualization of progress toward $100 daily net profit goal.
Tracks key metrics, projects timelines, and identifies optimization opportunities.

Run with: streamlit run dashboard/path_to_100_dashboard.py
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Try to import Dialogflow Client (fail gracefully if not installed)
try:
    from src.agents.dialogflow_client import DialogflowClient

    DIALOGFLOW_AVAILABLE = True
except ImportError:
    DIALOGFLOW_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Path to $100/Day",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Data paths
DATA_DIR = Path("data")
TELEMETRY_DIR = DATA_DIR / "telemetry"


def load_json_file(filepath: Path, default=None):
    """Load JSON file safely."""
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else []


def get_recent_trades_count() -> int:
    """Get count of trades from today or yesterday (handles midnight rollover)."""
    today = datetime.now().date()

    # Try today's file first
    trade_file = DATA_DIR / f"trades_{today.isoformat()}.json"
    trades = load_json_file(trade_file)

    if not trades:
        # Fallback to yesterday's file
        yesterday = today - timedelta(days=1)
        trade_file = DATA_DIR / f"trades_{yesterday.isoformat()}.json"
        trades = load_json_file(trade_file)

    return len(trades) if isinstance(trades, list) else 0


def load_telemetry_data() -> pd.DataFrame:
    """Load telemetry data from various sources."""
    dfs = []

    # Try cost-adjusted telemetry
    cost_adjusted = TELEMETRY_DIR / "cost_adjusted.json"
    if cost_adjusted.exists():
        try:
            with open(cost_adjusted) as f:
                data = json.load(f)
            if isinstance(data, list):
                dfs.append(pd.DataFrame(data))
            elif isinstance(data, dict):
                dfs.append(pd.DataFrame([data]))
        except Exception:
            pass

    # Try hybrid funnel runs
    funnel_log = DATA_DIR / "hybrid_funnel_runs.jsonl"
    if funnel_log.exists():
        try:
            runs = []
            with open(funnel_log) as f:
                for line in f:
                    if line.strip():
                        runs.append(json.loads(line))
            if runs:
                dfs.append(pd.DataFrame(runs))
        except Exception:
            pass

    # Try performance log
    perf_log = DATA_DIR / "performance_log.json"
    if perf_log.exists():
        try:
            with open(perf_log) as f:
                data = json.load(f)
            if isinstance(data, list):
                dfs.append(pd.DataFrame(data))
        except Exception:
            pass

    if dfs:
        df = pd.concat(dfs, ignore_index=True)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        elif "timestamp" in df.columns:
            df["date"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("date")
        return df

    return pd.DataFrame()


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calculate key performance metrics."""
    metrics = {
        "daily_net_avg": 0.0,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "current_equity": 0.0,
        "total_trades": 0,
        "days_tracked": 0,
    }

    if df.empty:
        return metrics

    # Calculate from available columns
    if "daily_net" in df.columns:
        metrics["daily_net_avg"] = df["daily_net"].mean()
    elif "pl" in df.columns:
        metrics["daily_net_avg"] = df["pl"].mean()
    elif "pnl" in df.columns:
        metrics["daily_net_avg"] = df["pnl"].mean()

    if "win_rate" in df.columns:
        metrics["win_rate"] = df["win_rate"].iloc[-1] if len(df) > 0 else 0

    if "sharpe" in df.columns:
        metrics["sharpe_ratio"] = df["sharpe"].iloc[-1] if len(df) > 0 else 0
    elif "sharpe_ratio" in df.columns:
        metrics["sharpe_ratio"] = df["sharpe_ratio"].iloc[-1] if len(df) > 0 else 0

    if "equity" in df.columns:
        metrics["current_equity"] = df["equity"].iloc[-1] if len(df) > 0 else 0
        # Calculate max drawdown
        equity_series = df["equity"]
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        metrics["max_drawdown"] = abs(drawdown.min()) * 100

    if "date" in df.columns:
        metrics["days_tracked"] = len(df["date"].unique())

    return metrics


def calculate_days_to_goal(
    current_daily: float,
    current_equity: float,
    target_daily: float = 100.0,
    daily_input: float = 10.0,
    daily_return_pct: float = 0.12,
) -> int:
    """
    Calculate days to reach $100/day net profit goal.

    Uses compound growth model with daily inputs.
    """
    if current_daily >= target_daily:
        return 0

    if daily_return_pct <= 0:
        return 999  # Never

    # Equity needed for $100/day at current return rate
    # target_daily = equity * daily_return_pct
    target_equity = target_daily / daily_return_pct

    if current_equity >= target_equity:
        return 0

    # Days to reach target equity with compound growth + daily inputs
    # Using approximation: equity(t) = equity(0) * (1+r)^t + input * ((1+r)^t - 1) / r
    days = 0
    equity = current_equity
    max_days = 1000

    while equity < target_equity and days < max_days:
        equity = equity * (1 + daily_return_pct) + daily_input
        days += 1

    return days


def get_milestone_data() -> list[dict]:
    """Get milestone projections for the path to $100."""
    return [
        {
            "phase": "R&D Polish",
            "months": "0-2",
            "input": 600,
            "equity": 1600,
            "daily_net": "$6-8",
            "pct": 7,
        },
        {
            "phase": "Live Ignition",
            "months": "2-4.5",
            "input": 750,
            "equity": 4500,
            "daily_net": "$18-25",
            "pct": 22,
        },
        {
            "phase": "Momentum Build",
            "months": "4.5-10",
            "input": 1650,
            "equity": 12500,
            "daily_net": "$50-65",
            "pct": 60,
        },
        {
            "phase": "Goal Horizon",
            "months": "10-14",
            "input": 1200,
            "equity": 28000,
            "daily_net": "$105-130",
            "pct": 100,
        },
    ]


def main():
    """Main dashboard."""
    st.title("🎯 Path to $100/Day Net Profit")
    st.markdown("**Real-time progress tracking toward sustainable daily income from AI trading**")

    # Load data
    df = load_telemetry_data()
    metrics = calculate_metrics(df)

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        target_daily = st.number_input(
            "Target Daily Profit ($)", value=100.0, min_value=10.0, step=10.0
        )

        daily_input = st.number_input("Daily Investment ($)", value=10.0, min_value=1.0, step=1.0)

        current_equity = st.number_input(
            "Current Equity ($)",
            value=metrics["current_equity"] or 100000.0,
            min_value=0.0,
            step=100.0,
        )

        st.divider()

        st.header("📊 Data Status")
        if not df.empty:
            st.success(f"✅ {len(df)} data points loaded")
            st.caption(f"Days tracked: {metrics['days_tracked']}")
        else:
            st.warning("⚠️ No telemetry data found")
            st.caption("Run trading system to generate data")

        # Show recent trades (handles midnight rollover)
        recent_trades = get_recent_trades_count()
        if recent_trades > 0:
            st.info(f"✅ {recent_trades} Recent Trades")
        else:
            st.caption("No recent trades")

        st.divider()

        if st.button("🔄 Refresh Data"):
            st.rerun()

    # Main metrics row
    st.header("📈 Current Performance")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        daily_net = metrics["daily_net_avg"]
        pct_to_goal = (daily_net / target_daily * 100) if target_daily > 0 else 0
        st.metric(
            "Daily Net Profit (Avg)",
            f"${daily_net:.2f}",
            delta=f"{pct_to_goal:.1f}% of goal",
        )

    with col2:
        st.metric(
            "Win Rate",
            f"{metrics['win_rate']:.1f}%",
            delta="✅ Gate safe" if metrics["win_rate"] >= 62 else "⚠️ Below 62%",
        )

    with col3:
        st.metric(
            "Sharpe Ratio",
            f"{metrics['sharpe_ratio']:.2f}",
            delta="✅ Strong" if metrics["sharpe_ratio"] >= 2.0 else None,
        )

    with col4:
        st.metric(
            "Max Drawdown",
            f"{metrics['max_drawdown']:.1f}%",
            delta="✅ Controlled" if metrics["max_drawdown"] <= 5 else "⚠️ Review",
        )

    # Progress bar
    st.header("🎯 Progress to $100/Day")

    progress_pct = min(100, (metrics["daily_net_avg"] / target_daily * 100))
    st.progress(progress_pct / 100)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current", f"${metrics['daily_net_avg']:.2f}/day")
    with col2:
        st.metric("Target", f"${target_daily:.2f}/day")
    with col3:
        days_to_goal = calculate_days_to_goal(
            metrics["daily_net_avg"],
            current_equity,
            target_daily,
            daily_input,
        )
        st.metric("Est. Days to Goal", f"{days_to_goal}" if days_to_goal < 999 else "TBD")

    # Equity and P/L charts
    if not df.empty and "date" in df.columns:
        st.header("📊 Historical Performance")

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Equity Curve", "Daily P/L", "Win Rate Trend", "🤖 AI Assistant"]
        )

        with tab1:
            if "equity" in df.columns:
                st.line_chart(df.set_index("date")["equity"])
            else:
                st.info("No equity data available")

        with tab2:
            pl_col = next((c for c in ["daily_net", "pl", "pnl"] if c in df.columns), None)
            if pl_col:
                chart_df = df.set_index("date")[pl_col]
                st.bar_chart(chart_df)
            else:
                st.info("No P/L data available")

        with tab3:
            if "win_rate" in df.columns:
                st.line_chart(df.set_index("date")["win_rate"])
            else:
                st.info("No win rate data available")

        with tab4:
            st.subheader("💬 Chat with Trading Agent")

            if not DIALOGFLOW_AVAILABLE:
                st.warning(
                    "⚠️ Dialogflow client not available. Install 'google-cloud-dialogflow-cx' to enable."
                )
            else:
                # Initialize session state for chat history and session ID
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                if "session_id" not in st.session_state:
                    st.session_state.session_id = str(uuid.uuid4())

                # Display chat messages from history on app rerun
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                # Accept user input
                if prompt := st.chat_input(
                    "Ask about market trends, strategy status, or commands..."
                ):
                    # Add user message to chat history
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    # Display user message in chat message container
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Display assistant response in chat message container
                    with st.chat_message("assistant"):
                        message_placeholder = st.empty()
                        full_response = ""

                        try:
                            client = DialogflowClient()
                            response_text = client.detect_intent(
                                session_id=st.session_state.session_id, text=prompt
                            )
                            full_response = response_text
                        except Exception as e:
                            full_response = f"⚠️ Error communicating with agent: {str(e)}"

                        message_placeholder.markdown(full_response)

                    # Add assistant response to chat history
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )

    # Milestone roadmap
    st.header("🗺️ Milestone Roadmap")

    milestones = get_milestone_data()
    milestone_df = pd.DataFrame(milestones)

    # Highlight current phase based on progress

    st.dataframe(
        milestone_df,
        column_config={
            "phase": st.column_config.TextColumn("Phase", width="medium"),
            "months": st.column_config.TextColumn("Timeline", width="small"),
            "input": st.column_config.NumberColumn("Cumulative Input", format="$%d", width="small"),
            "equity": st.column_config.NumberColumn(
                "Projected Equity", format="$%d", width="small"
            ),
            "daily_net": st.column_config.TextColumn("Daily Net", width="small"),
            "pct": st.column_config.ProgressColumn(
                "Progress", min_value=0, max_value=100, width="medium"
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    # Optimization opportunities
    st.header("🚀 Optimization Opportunities")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Asset Expansion")
        st.markdown(
            """
        - **IJR (Small-Cap)**: +3-5% alpha in rotations
        - **VXUS (International)**: Diversification, -correlation
        - **GLD (Gold)**: Crisis protection, inflation hedge
        - **VNQ (REITs)**: +1.5% yield in flat markets
        """
        )

        if st.button("📊 View Asset Config"):
            try:
                import yaml

                with open("config/asset_tiers.yaml") as f:
                    config = yaml.safe_load(f)
                st.json(config)
            except Exception as e:
                st.error(f"Error loading config: {e}")

    with col2:
        st.subheader("Risk Enhancements")
        st.markdown(
            """
        - **Collar Hedging**: Caps drawdown to 1.5%
        - **VIX Triggers**: Auto-hedge at VIX > 20
        - **Regime Detection**: Adapt allocation dynamically
        - **Weekend Crypto**: +$0.40/day drift via BITO
        """
        )

        if st.button("🛡️ View Hedge Status"):
            try:
                from src.risk.hedging import HedgingOverlay

                hedger = HedgingOverlay()
                status = hedger.get_hedge_status()
                if status:
                    st.json(status)
                else:
                    st.info("No active hedges")
            except Exception as e:
                st.warning(f"Hedging module not available: {e}")

    # Key insights
    st.header("💡 Key Insights")

    insights = []

    if metrics["win_rate"] >= 67:
        insights.append("✅ Win rate above 67% - strong signal quality")
    elif metrics["win_rate"] >= 62:
        insights.append("📊 Win rate at gate threshold - maintain discipline")
    else:
        insights.append("⚠️ Win rate below 62% - review strategy")

    if metrics["sharpe_ratio"] >= 2.0:
        insights.append("✅ Sharpe > 2.0 - excellent risk-adjusted returns")

    if metrics["max_drawdown"] <= 2.5:
        insights.append("✅ Max DD < 2.5% - tight risk control")
    elif metrics["max_drawdown"] <= 5:
        insights.append("📊 Max DD < 5% - within acceptable limits")

    if current_equity >= 3000:
        insights.append("💰 Equity > $3k - eligible for asset expansion")

    if not insights:
        insights.append("📊 Generating initial metrics - keep trading!")

    for insight in insights:
        st.markdown(f"- {insight}")

    # Footer
    st.divider()
    st.caption(
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data points: {len(df)} | Days tracked: {metrics['days_tracked']}"
    )


if __name__ == "__main__":
    main()
