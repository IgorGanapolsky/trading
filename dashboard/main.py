#!/usr/bin/env python3
"""
World-Class AI Trading Dashboard
================================

A clean, efficient, single-pane-of-glass view for the AI trading system.
Designed for professional traders with focus on:
- At-a-glance hero metrics
- Progressive disclosure (summary → detail)
- Real-time data with clear timestamps
- Options theta tracking
- Path to $100/day progress

Run: streamlit run dashboard/main.py
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PAGE CONFIG - Dark theme, wide layout
# =============================================================================
st.set_page_config(
    page_title="AI Trading System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# CUSTOM CSS - Professional dark theme
# =============================================================================
st.markdown(
    """
<style>
    /* Dark theme base */
    .stApp {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }

    /* Hero metrics styling */
    .hero-metric {
        background: linear-gradient(135deg, #21262d 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .hero-metric:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .hero-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #58a6ff 0%, #79c0ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .hero-value.positive { background: linear-gradient(135deg, #3fb950 0%, #56d364 100%); -webkit-background-clip: text; }
    .hero-value.negative { background: linear-gradient(135deg, #f85149 0%, #ff7b72 100%); -webkit-background-clip: text; }
    .hero-label {
        font-size: 0.9rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 8px;
    }
    .hero-delta {
        font-size: 0.85rem;
        margin-top: 4px;
    }
    .delta-positive { color: #3fb950; }
    .delta-negative { color: #f85149; }
    .delta-neutral { color: #8b949e; }

    /* Progress bar styling */
    .progress-container {
        background: #21262d;
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        border: 1px solid #30363d;
    }
    .progress-bar {
        height: 24px;
        background: #30363d;
        border-radius: 12px;
        overflow: hidden;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #238636 0%, #3fb950 50%, #56d364 100%);
        border-radius: 12px;
        transition: width 0.5s ease;
    }

    /* Card styling */
    .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    .card-header {
        color: #f0f6fc;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Status indicators */
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }
    .status-green { background: #3fb950; box-shadow: 0 0 8px #3fb950; }
    .status-yellow { background: #d29922; box-shadow: 0 0 8px #d29922; }
    .status-red { background: #f85149; box-shadow: 0 0 8px #f85149; }

    /* Table styling */
    .dataframe {
        background: #161b22 !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #161b22;
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: #8b949e;
        padding: 12px 24px;
    }
    .stTabs [aria-selected="true"] {
        background: #238636;
        color: #ffffff;
    }

    /* Metric overrides */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }

    /* Hide default streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# DATA LOADING
# =============================================================================
DATA_DIR = Path("data")


@st.cache_data(ttl=30)
def load_json_safe(filepath: Path, default: Any = None) -> Any:
    """Load JSON file with error handling."""
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


@st.cache_data(ttl=30)
def get_account_data() -> dict | None:
    """Fetch live account data from Alpaca."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        api_secret = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not api_secret:
            return None

        client = TradingClient(api_key, api_secret, paper=True)
        account = client.get_account()
        positions = client.get_all_positions()

        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "last_equity": float(account.last_equity)
            if hasattr(account, "last_equity")
            else float(account.equity),
            "positions": [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc) * 100,
                    "market_value": float(pos.market_value),
                }
                for pos in positions
            ],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        st.error(f"Account error: {e}")
        return None


@st.cache_data(ttl=60)
def get_performance_data() -> pd.DataFrame:
    """Load historical performance data."""
    perf_file = DATA_DIR / "performance_log.json"
    data = load_json_safe(perf_file, [])
    if data:
        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df
    return pd.DataFrame()


@st.cache_data(ttl=60)
def get_trades_today() -> list:
    """Get today's trades (with yesterday fallback)."""
    today = datetime.now().date()
    trade_file = DATA_DIR / f"trades_{today.isoformat()}.json"
    trades = load_json_safe(trade_file, [])

    if not trades:
        yesterday = today - timedelta(days=1)
        trade_file = DATA_DIR / f"trades_{yesterday.isoformat()}.json"
        trades = load_json_safe(trade_file, [])

    return trades if isinstance(trades, list) else []


@st.cache_data(ttl=120)
def get_options_data() -> dict:
    """Get options portfolio and theta data."""
    try:
        # Try to load wheel state
        wheel_file = DATA_DIR / "wheel_state.json"
        wheel_data = load_json_safe(wheel_file, {})

        # Try to load options signals
        signals_dir = DATA_DIR / "options_signals"
        latest_plan = None
        if signals_dir.exists():
            plans = sorted(signals_dir.glob("options_profit_plan_*.json"), reverse=True)
            if plans:
                latest_plan = load_json_safe(plans[0])

        # Calculate portfolio theta
        total_theta = 0.0
        positions = wheel_data.get("positions", {})
        for pos in positions.values():
            # Estimate theta based on premium collected and DTE
            premium = pos.get("total_premium_collected", 0)
            total_theta += premium / 30  # Rough daily theta estimate

        return {
            "wheel_positions": len(positions),
            "wheel_premium_collected": sum(
                p.get("total_premium_collected", 0) for p in positions.values()
            ),
            "estimated_daily_theta": total_theta,
            "theta_target": 10.0,  # $10/day target
            "profit_plan": latest_plan,
            "active_puts": sum(1 for p in positions.values() if p.get("phase") == "selling_puts"),
            "active_calls": sum(1 for p in positions.values() if p.get("phase") == "selling_calls"),
        }
    except Exception:
        return {
            "wheel_positions": 0,
            "wheel_premium_collected": 0,
            "estimated_daily_theta": 0,
            "theta_target": 10.0,
            "profit_plan": None,
            "active_puts": 0,
            "active_calls": 0,
        }


def calculate_win_rate(trades: list) -> tuple[float, int, int]:
    """Calculate win rate from trades."""
    closed = [t for t in trades if t.get("pl") is not None or t.get("action") == "SELL"]
    if not closed:
        return 0.0, 0, 0
    winning = sum(1 for t in closed if t.get("pl", 0) > 0)
    return (winning / len(closed) * 100) if closed else 0.0, winning, len(closed)


# =============================================================================
# DASHBOARD COMPONENTS
# =============================================================================


def render_hero_metric(
    label: str, value: str, delta: str = "", delta_type: str = "neutral", icon: str = ""
):
    """Render a hero metric card."""
    value_class = (
        "positive" if delta_type == "positive" else "negative" if delta_type == "negative" else ""
    )
    delta_class = f"delta-{delta_type}"

    st.markdown(
        f"""
        <div class="hero-metric">
            <p class="hero-value {value_class}">{icon} {value}</p>
            <p class="hero-label">{label}</p>
            {f'<p class="hero-delta {delta_class}">{delta}</p>' if delta else ""}
        </div>
    """,
        unsafe_allow_html=True,
    )


def render_progress_to_goal(current: float, target: float = 100.0):
    """Render progress bar to $100/day goal."""
    pct = min(100, (current / target * 100)) if target > 0 else 0

    st.markdown(
        f"""
        <div class="progress-container">
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                <span style="color: #f0f6fc; font-weight: 600;">🎯 Path to $100/Day</span>
                <span style="color: #8b949e;">${current:.2f} / ${target:.0f}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pct}%;"></div>
            </div>
            <div style="text-align: center; margin-top: 8px; color: #8b949e;">
                {pct:.1f}% Complete
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )


def render_status_indicator(status: str, label: str):
    """Render a status indicator."""
    color_class = (
        "status-green"
        if status == "ok"
        else "status-yellow"
        if status == "warning"
        else "status-red"
    )
    st.markdown(
        f"""
        <span class="status-dot {color_class}"></span>
        <span style="color: #f0f6fc;">{label}</span>
    """,
        unsafe_allow_html=True,
    )


# =============================================================================
# MAIN DASHBOARD
# =============================================================================


def main():
    # Header with timestamp
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🎯 AI Trading System")
    with col2:
        st.markdown(
            f"""
            <div style="text-align: right; padding-top: 20px;">
                <span style="color: #3fb950;">●</span>
                <span style="color: #8b949e; font-size: 0.85rem;">
                    Live · {datetime.now().strftime("%H:%M:%S")}
                </span>
            </div>
        """,
            unsafe_allow_html=True,
        )

    # Load all data
    account = get_account_data()
    trades = get_trades_today()
    options_data = get_options_data()
    win_rate, wins, total = calculate_win_rate(trades)

    # Calculate key metrics
    if account:
        equity = account["equity"]
        daily_pl = equity - account["last_equity"]
        daily_pl_pct = (
            (daily_pl / account["last_equity"] * 100) if account["last_equity"] > 0 else 0
        )
        total_pl = equity - 100000  # Starting balance
    else:
        equity = 100000
        daily_pl = 0
        daily_pl_pct = 0
        total_pl = 0

    # R&D Phase info
    rd_day = 9  # Day 9 of 90
    rd_pct = (rd_day / 90) * 100

    # ==========================================================================
    # HERO METRICS ROW
    # ==========================================================================
    st.markdown("<br>", unsafe_allow_html=True)

    cols = st.columns(5)

    with cols[0]:
        render_hero_metric(
            "Portfolio Value",
            f"${equity:,.0f}",
            f"${total_pl:+,.2f} total",
            "positive" if total_pl >= 0 else "negative",
        )

    with cols[1]:
        render_hero_metric(
            "Daily P/L",
            f"${daily_pl:+,.2f}",
            f"{daily_pl_pct:+.2f}%",
            "positive" if daily_pl >= 0 else "negative",
        )

    with cols[2]:
        render_hero_metric(
            "Win Rate",
            f"{win_rate:.1f}%",
            f"{wins}/{total} trades" if total > 0 else "No trades yet",
            "positive" if win_rate >= 55 else "negative" if win_rate < 45 else "neutral",
        )

    with cols[3]:
        theta = options_data["estimated_daily_theta"]
        render_hero_metric(
            "Daily Theta",
            f"${theta:.2f}",
            f"Target: ${options_data['theta_target']:.0f}",
            "positive" if theta >= options_data["theta_target"] else "neutral",
        )

    with cols[4]:
        render_hero_metric("R&D Phase", f"Day {rd_day}/90", f"{rd_pct:.0f}% Complete", "neutral")

    # ==========================================================================
    # PROGRESS TO $100/DAY
    # ==========================================================================
    # Estimate daily income from theta + equity returns
    estimated_daily = theta + (daily_pl if daily_pl > 0 else 0)
    render_progress_to_goal(estimated_daily, 100.0)

    # ==========================================================================
    # MAIN TABS
    # ==========================================================================
    tabs = st.tabs(["📊 Overview", "💼 Positions", "🎯 Options", "📈 Performance"])

    # --------------------------------------------------------------------------
    # TAB 1: OVERVIEW
    # --------------------------------------------------------------------------
    with tabs[0]:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### 📊 System Status")

            status_col1, status_col2, status_col3 = st.columns(3)

            with status_col1:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                render_status_indicator("ok" if account else "error", "Alpaca API")
                st.markdown("</div>", unsafe_allow_html=True)

            with status_col2:
                circuit_ok = daily_pl_pct > -2  # -2% daily loss limit
                st.markdown('<div class="card">', unsafe_allow_html=True)
                render_status_indicator("ok" if circuit_ok else "error", "Circuit Breaker")
                st.markdown("</div>", unsafe_allow_html=True)

            with status_col3:
                market_open = datetime.now().weekday() < 5 and 9 <= datetime.now().hour < 16
                st.markdown('<div class="card">', unsafe_allow_html=True)
                render_status_indicator(
                    "ok" if market_open else "warning",
                    "Market" + (" Open" if market_open else " Closed"),
                )
                st.markdown("</div>", unsafe_allow_html=True)

            # Quick stats
            st.markdown("### 📋 Today's Activity")

            act_col1, act_col2, act_col3, act_col4 = st.columns(4)
            with act_col1:
                st.metric(
                    "Trades",
                    len(
                        [
                            t
                            for t in trades
                            if t.get("timestamp", "").startswith(str(datetime.now().date()))
                        ]
                    ),
                )
            with act_col2:
                st.metric("Open Positions", len(account["positions"]) if account else 0)
            with act_col3:
                st.metric("Wheel Positions", options_data["wheel_positions"])
            with act_col4:
                unrealized = sum(p["unrealized_pl"] for p in account["positions"]) if account else 0
                st.metric("Unrealized P/L", f"${unrealized:,.2f}")

        with col2:
            st.markdown("### ⏰ Next Actions")
            st.markdown(
                """
                <div class="card">
                    <p style="color: #8b949e; margin: 0;">Next Trade Window</p>
                    <p style="color: #f0f6fc; font-size: 1.5rem; margin: 8px 0;">Dec 10, 9:35 AM ET</p>
                    <p style="color: #3fb950; margin: 0;">Momentum + RL Strategy</p>
                </div>
            """,
                unsafe_allow_html=True,
            )

            st.markdown(
                """
                <div class="card">
                    <p style="color: #8b949e; margin: 0;">Strategy Queue</p>
                    <p style="color: #f0f6fc; margin: 8px 0;">1. Momentum Scan</p>
                    <p style="color: #f0f6fc; margin: 4px 0;">2. RL Filter</p>
                    <p style="color: #f0f6fc; margin: 4px 0;">3. Risk Check</p>
                    <p style="color: #f0f6fc; margin: 4px 0;">4. Execute</p>
                </div>
            """,
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------------------------
    # TAB 2: POSITIONS
    # --------------------------------------------------------------------------
    with tabs[1]:
        if account and account.get("positions"):
            st.markdown("### 💼 Current Positions")

            df = pd.DataFrame(account["positions"])

            # Calculate additional metrics
            df["Value"] = df["market_value"]
            df["P/L"] = df["unrealized_pl"]
            df["P/L %"] = df["unrealized_plpc"]
            df["Qty"] = df["qty"].astype(int)

            # Style the dataframe
            st.dataframe(
                df[["symbol", "Qty", "entry_price", "current_price", "P/L", "P/L %", "Value"]]
                .style.format(
                    {
                        "entry_price": "${:.2f}",
                        "current_price": "${:.2f}",
                        "P/L": "${:+,.2f}",
                        "P/L %": "{:+.2f}%",
                        "Value": "${:,.2f}",
                    }
                )
                .applymap(
                    lambda x: "color: #3fb950"
                    if isinstance(x, (int, float)) and x > 0
                    else "color: #f85149"
                    if isinstance(x, (int, float)) and x < 0
                    else "",
                    subset=["P/L", "P/L %"],
                ),
                use_container_width=True,
                hide_index=True,
            )

            # Summary row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Value", f"${df['Value'].sum():,.2f}")
            with col2:
                st.metric("Total P/L", f"${df['P/L'].sum():,.2f}")
            with col3:
                avg_return = df["P/L %"].mean()
                st.metric("Avg Return", f"{avg_return:+.2f}%")
        else:
            st.info("No open positions")

    # --------------------------------------------------------------------------
    # TAB 3: OPTIONS
    # --------------------------------------------------------------------------
    with tabs[2]:
        st.markdown("### 🎯 Options & Theta Tracking")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Theta Income")

            theta_col1, theta_col2 = st.columns(2)
            with theta_col1:
                st.metric(
                    "Est. Daily Theta",
                    f"${options_data['estimated_daily_theta']:.2f}",
                    f"Target: ${options_data['theta_target']:.0f}",
                )
            with theta_col2:
                st.metric(
                    "Premium Collected",
                    f"${options_data['wheel_premium_collected']:.2f}",
                    "All time",
                )

            # Theta progress
            theta_pct = min(
                100, (options_data["estimated_daily_theta"] / options_data["theta_target"] * 100)
            )
            st.progress(theta_pct / 100)
            st.caption(f"{theta_pct:.1f}% of $10/day theta target")

        with col2:
            st.markdown("#### Wheel Strategy")

            wheel_col1, wheel_col2, wheel_col3 = st.columns(3)
            with wheel_col1:
                st.metric("Active Positions", options_data["wheel_positions"])
            with wheel_col2:
                st.metric("CSPs Open", options_data["active_puts"])
            with wheel_col3:
                st.metric("CCs Open", options_data["active_calls"])

        st.markdown("---")

        # Options opportunities
        st.markdown("#### 🔍 Opportunities")

        if options_data.get("profit_plan"):
            plan = options_data["profit_plan"]
            st.json(plan)
        else:
            st.markdown(
                """
                <div class="card">
                    <p style="color: #8b949e;">No active options signals. Run the options scanner:</p>
                    <code style="color: #79c0ff;">python scripts/options_profit_planner.py --target-daily 10</code>
                </div>
            """,
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------------------------
    # TAB 4: PERFORMANCE
    # --------------------------------------------------------------------------
    with tabs[3]:
        st.markdown("### 📈 Historical Performance")

        df = get_performance_data()

        if not df.empty and "date" in df.columns:
            # Equity curve
            if "equity" in df.columns:
                st.markdown("#### Equity Curve")
                st.line_chart(df.set_index("date")["equity"], use_container_width=True)

            # Daily P/L
            pl_col = next((c for c in ["pl", "pnl", "daily_net"] if c in df.columns), None)
            if pl_col:
                st.markdown("#### Daily P/L")
                st.bar_chart(df.set_index("date")[pl_col], use_container_width=True)

            # Stats
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if "equity" in df.columns:
                    max_equity = df["equity"].max()
                    current_equity = df["equity"].iloc[-1]
                    drawdown = (
                        ((max_equity - current_equity) / max_equity * 100) if max_equity > 0 else 0
                    )
                    st.metric("Max Drawdown", f"{drawdown:.2f}%")

            with col2:
                if pl_col:
                    avg_pl = df[pl_col].mean()
                    st.metric("Avg Daily P/L", f"${avg_pl:.2f}")

            with col3:
                if "sharpe" in df.columns or "sharpe_ratio" in df.columns:
                    sharpe_col = "sharpe" if "sharpe" in df.columns else "sharpe_ratio"
                    sharpe = df[sharpe_col].iloc[-1]
                    st.metric("Sharpe Ratio", f"{sharpe:.2f}")

            with col4:
                st.metric("Days Tracked", len(df))
        else:
            st.info("No performance data yet. Run the trading system to generate data.")

    # ==========================================================================
    # FOOTER
    # ==========================================================================
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col3:
        st.caption("AI Trading System v2.0")


if __name__ == "__main__":
    main()
