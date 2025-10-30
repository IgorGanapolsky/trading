"""
Trading System Monitoring Dashboard

A comprehensive Streamlit dashboard for real-time monitoring of trading operations,
portfolio performance, risk metrics, and system status.

Features:
- Real-time portfolio metrics and P/L tracking
- Strategy performance breakdown (Tier 1-4)
- Interactive performance charts with Plotly
- Recent trades and current positions tables
- Risk metrics (win rate, Sharpe ratio, max drawdown)
- Alert history display
- System status monitoring (circuit breakers, trading status)
- Auto-refresh capability

Author: Trading System
Date: 2025-10-28
"""

import os
import sys
import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Page configuration
st.set_page_config(
    page_title="Trading System Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .positive {
        color: #28a745;
        font-weight: bold;
    }
    .negative {
        color: #dc3545;
        font-weight: bold;
    }
    .alert-critical {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border-left: 4px solid #dc3545;
        margin: 0.5rem 0;
    }
    .alert-warning {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border-left: 4px solid #ffc107;
        margin: 0.5rem 0;
    }
    .alert-info {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border-left: 4px solid #17a2b8;
        margin: 0.5rem 0;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-active {
        background-color: #28a745;
    }
    .status-inactive {
        background-color: #dc3545;
    }
    .status-warning {
        background-color: #ffc107;
    }
</style>
""",
    unsafe_allow_html=True,
)


class DashboardDataManager:
    """Manages data loading and processing for the dashboard."""

    def __init__(self, data_dir: str):
        """
        Initialize the data manager.

        Args:
            data_dir: Path to the data directory
        """
        self.data_dir = Path(data_dir)
        self.trades_file = self.data_dir / "trades.csv"
        self.performance_file = self.data_dir / "performance.json"
        self.positions_file = self.data_dir / "positions.csv"
        self.alerts_file = self.data_dir / "alerts.json"
        self.system_status_file = self.data_dir / "system_status.json"

    def load_trades(self) -> pd.DataFrame:
        """Load trades data from CSV file."""
        try:
            if self.trades_file.exists():
                df = pd.read_csv(self.trades_file)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                return df
            else:
                # Return sample data if file doesn't exist
                return self._generate_sample_trades()
        except Exception as e:
            st.error(f"Error loading trades: {e}")
            return self._generate_sample_trades()

    def load_performance(self) -> Dict:
        """Load performance metrics from JSON file."""
        try:
            if self.performance_file.exists():
                with open(self.performance_file, "r") as f:
                    return json.load(f)
            else:
                return self._generate_sample_performance()
        except Exception as e:
            st.error(f"Error loading performance: {e}")
            return self._generate_sample_performance()

    def load_positions(self) -> pd.DataFrame:
        """Load current positions from CSV file."""
        try:
            if self.positions_file.exists():
                df = pd.read_csv(self.positions_file)
                return df
            else:
                return self._generate_sample_positions()
        except Exception as e:
            st.error(f"Error loading positions: {e}")
            return self._generate_sample_positions()

    def load_alerts(self) -> List[Dict]:
        """Load alert history from JSON file."""
        try:
            if self.alerts_file.exists():
                with open(self.alerts_file, "r") as f:
                    return json.load(f)
            else:
                return self._generate_sample_alerts()
        except Exception as e:
            st.error(f"Error loading alerts: {e}")
            return self._generate_sample_alerts()

    def load_system_status(self) -> Dict:
        """Load system status from JSON file."""
        try:
            if self.system_status_file.exists():
                with open(self.system_status_file, "r") as f:
                    return json.load(f)
            else:
                return self._generate_sample_system_status()
        except Exception as e:
            st.error(f"Error loading system status: {e}")
            return self._generate_sample_system_status()

    def _generate_sample_trades(self) -> pd.DataFrame:
        """Generate sample trades data for demonstration."""
        dates = pd.date_range(end=datetime.now(), periods=50, freq="H")
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META"]
        strategies = ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]
        sides = ["BUY", "SELL"]

        trades = []
        for i, date in enumerate(dates):
            pnl = np.random.normal(50, 200)
            trades.append(
                {
                    "timestamp": date,
                    "symbol": np.random.choice(symbols),
                    "side": np.random.choice(sides),
                    "quantity": np.random.uniform(1, 10),
                    "price": np.random.uniform(100, 500),
                    "amount": np.random.uniform(1000, 5000),
                    "strategy": np.random.choice(strategies),
                    "pnl": pnl,
                    "status": "FILLED",
                }
            )

        return pd.DataFrame(trades)

    def _generate_sample_performance(self) -> Dict:
        """Generate sample performance data."""
        return {
            "total_value": 125000.0,
            "cash": 45000.0,
            "equity": 80000.0,
            "daily_pnl": 1250.75,
            "total_pnl": 25000.0,
            "total_pnl_pct": 25.0,
            "strategies": {
                "Tier 1": {"pnl": 8500.0, "trades": 45, "win_rate": 62.5},
                "Tier 2": {"pnl": 6200.0, "trades": 38, "win_rate": 58.3},
                "Tier 3": {"pnl": 5800.0, "trades": 52, "win_rate": 55.2},
                "Tier 4": {"pnl": 4500.0, "trades": 28, "win_rate": 53.8},
            },
            "equity_curve": self._generate_equity_curve(),
            "daily_pnl_history": self._generate_daily_pnl(),
        }

    def _generate_equity_curve(self) -> List[Dict]:
        """Generate sample equity curve data."""
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        initial_value = 100000
        equity_curve = []

        for i, date in enumerate(dates):
            value = initial_value + np.random.normal(i * 800, 2000)
            equity_curve.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "equity": max(value, initial_value * 0.9),
                }
            )

        return equity_curve

    def _generate_daily_pnl(self) -> List[Dict]:
        """Generate sample daily P/L data."""
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        daily_pnl = []

        for date in dates:
            pnl = np.random.normal(300, 800)
            daily_pnl.append({"date": date.strftime("%Y-%m-%d"), "pnl": pnl})

        return daily_pnl

    def _generate_sample_positions(self) -> pd.DataFrame:
        """Generate sample positions data."""
        positions = [
            {
                "symbol": "AAPL",
                "quantity": 15.5,
                "avg_entry_price": 175.20,
                "current_price": 182.30,
                "market_value": 2825.65,
                "cost_basis": 2715.60,
                "unrealized_pnl": 110.05,
                "unrealized_pnl_pct": 4.05,
            },
            {
                "symbol": "GOOGL",
                "quantity": 8.0,
                "avg_entry_price": 138.50,
                "current_price": 142.10,
                "market_value": 1136.80,
                "cost_basis": 1108.00,
                "unrealized_pnl": 28.80,
                "unrealized_pnl_pct": 2.60,
            },
            {
                "symbol": "MSFT",
                "quantity": 12.0,
                "avg_entry_price": 375.80,
                "current_price": 389.20,
                "market_value": 4670.40,
                "cost_basis": 4509.60,
                "unrealized_pnl": 160.80,
                "unrealized_pnl_pct": 3.57,
            },
            {
                "symbol": "TSLA",
                "quantity": 5.0,
                "avg_entry_price": 242.00,
                "current_price": 238.50,
                "market_value": 1192.50,
                "cost_basis": 1210.00,
                "unrealized_pnl": -17.50,
                "unrealized_pnl_pct": -1.45,
            },
            {
                "symbol": "NVDA",
                "quantity": 10.0,
                "avg_entry_price": 485.00,
                "current_price": 512.30,
                "market_value": 5123.00,
                "cost_basis": 4850.00,
                "unrealized_pnl": 273.00,
                "unrealized_pnl_pct": 5.63,
            },
        ]

        return pd.DataFrame(positions)

    def _generate_sample_alerts(self) -> List[Dict]:
        """Generate sample alerts data."""
        return [
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "severity": "WARNING",
                "message": "Consecutive losses: 3",
                "details": {"consecutive_losses": 3},
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=5)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "severity": "INFO",
                "message": "Daily P&L reached +$1,000",
                "details": {"daily_pnl": 1000},
            },
            {
                "timestamp": (datetime.now() - timedelta(days=1)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "severity": "WARNING",
                "message": "Position size approaching limit: 9.5%",
                "details": {"position_size_pct": 9.5},
            },
        ]

    def _generate_sample_system_status(self) -> Dict:
        """Generate sample system status data."""
        return {
            "trading_enabled": True,
            "circuit_breakers": {
                "daily_loss_breaker": False,
                "drawdown_breaker": False,
                "consecutive_loss_breaker": False,
            },
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system_health": "HEALTHY",
            "active_strategies": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
        }


def calculate_risk_metrics(trades_df: pd.DataFrame, performance: Dict) -> Dict:
    """
    Calculate comprehensive risk metrics.

    Args:
        trades_df: DataFrame of trade history
        performance: Performance data dictionary

    Returns:
        Dictionary of risk metrics
    """
    if trades_df.empty:
        return {
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
        }

    # Calculate win rate
    winning_trades = len(trades_df[trades_df["pnl"] > 0])
    total_trades = len(trades_df[trades_df["pnl"] != 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    # Calculate average win and loss
    wins = trades_df[trades_df["pnl"] > 0]["pnl"]
    losses = trades_df[trades_df["pnl"] < 0]["pnl"]
    avg_win = wins.mean() if len(wins) > 0 else 0.0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0.0

    # Calculate profit factor
    total_wins = wins.sum() if len(wins) > 0 else 0.0
    total_losses = abs(losses.sum()) if len(losses) > 0 else 0.0
    profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0

    # Calculate Sharpe ratio (simplified)
    if "pnl" in trades_df.columns:
        returns = trades_df["pnl"]
        sharpe_ratio = (
            (returns.mean() / returns.std() * np.sqrt(252))
            if returns.std() > 0
            else 0.0
        )
    else:
        sharpe_ratio = 0.0

    # Calculate max drawdown from equity curve
    if "equity_curve" in performance:
        equity_data = performance["equity_curve"]
        equity_values = [item["equity"] for item in equity_data]
        peak = equity_values[0]
        max_dd = 0.0

        for value in equity_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        max_drawdown = max_dd
    else:
        max_drawdown = 0.0

    return {
        "win_rate": round(win_rate, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "max_drawdown": round(max_drawdown, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
    }


def render_header():
    """Render the dashboard header."""
    st.markdown(
        '<h1 class="main-header">Trading System Dashboard</h1>', unsafe_allow_html=True
    )
    st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.markdown("---")


def render_metric_cards(performance: Dict, risk_metrics: Dict):
    """
    Render the top metric cards.

    Args:
        performance: Performance data dictionary
        risk_metrics: Risk metrics dictionary
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_value = performance.get("total_value", 0)
        st.metric(
            label="Total Portfolio Value",
            value=f"${total_value:,.2f}",
            delta=f"${performance.get('total_pnl', 0):,.2f}",
        )

    with col2:
        daily_pnl = performance.get("daily_pnl", 0)
        delta_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            label="Daily P/L",
            value=f"${daily_pnl:,.2f}",
            delta=f"{(daily_pnl / total_value * 100) if total_value > 0 else 0:.2f}%",
            delta_color=delta_color,
        )

    with col3:
        win_rate = risk_metrics.get("win_rate", 0)
        st.metric(label="Win Rate", value=f"{win_rate:.1f}%")

    with col4:
        max_dd = risk_metrics.get("max_drawdown", 0)
        st.metric(label="Max Drawdown", value=f"{max_dd:.2f}%", delta_color="inverse")


def render_strategy_performance(performance: Dict):
    """
    Render strategy performance breakdown table.

    Args:
        performance: Performance data dictionary
    """
    st.subheader("Strategy Performance Breakdown")

    strategies = performance.get("strategies", {})

    if strategies:
        strategy_data = []
        for strategy_name, metrics in strategies.items():
            strategy_data.append(
                {
                    "Strategy": strategy_name,
                    "P/L": f"${metrics.get('pnl', 0):,.2f}",
                    "Trades": metrics.get("trades", 0),
                    "Win Rate": f"{metrics.get('win_rate', 0):.1f}%",
                }
            )

        df = pd.DataFrame(strategy_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No strategy performance data available")


def render_equity_curve(performance: Dict):
    """
    Render the equity curve chart.

    Args:
        performance: Performance data dictionary
    """
    st.subheader("Equity Curve")

    equity_data = performance.get("equity_curve", [])

    if equity_data:
        df = pd.DataFrame(equity_data)
        df["date"] = pd.to_datetime(df["date"])

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["equity"],
                mode="lines",
                name="Equity",
                line=dict(color="#1f77b4", width=2),
                fill="tozeroy",
                fillcolor="rgba(31, 119, 180, 0.1)",
            )
        )

        fig.update_layout(
            title="Portfolio Equity Over Time",
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            hovermode="x unified",
            template="plotly_white",
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No equity curve data available")


def render_daily_pnl_chart(performance: Dict):
    """
    Render the daily P/L bar chart.

    Args:
        performance: Performance data dictionary
    """
    st.subheader("Daily P/L History")

    pnl_data = performance.get("daily_pnl_history", [])

    if pnl_data:
        df = pd.DataFrame(pnl_data)
        df["date"] = pd.to_datetime(df["date"])
        df["color"] = df["pnl"].apply(lambda x: "Profit" if x >= 0 else "Loss")

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["pnl"],
                marker_color=df["pnl"].apply(
                    lambda x: "#28a745" if x >= 0 else "#dc3545"
                ),
                name="Daily P/L",
            )
        )

        fig.update_layout(
            title="Daily Profit/Loss",
            xaxis_title="Date",
            yaxis_title="P/L ($)",
            hovermode="x unified",
            template="plotly_white",
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily P/L data available")


def render_recent_trades(trades_df: pd.DataFrame, limit: int = 10):
    """
    Render recent trades table.

    Args:
        trades_df: DataFrame of trades
        limit: Number of recent trades to display
    """
    st.subheader("Recent Trades")

    if not trades_df.empty:
        # Sort by timestamp and get most recent
        recent_trades = trades_df.sort_values("timestamp", ascending=False).head(limit)

        # Format the dataframe
        display_df = recent_trades[
            [
                "timestamp",
                "symbol",
                "side",
                "quantity",
                "price",
                "amount",
                "strategy",
                "pnl",
                "status",
            ]
        ].copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        display_df["quantity"] = display_df["quantity"].apply(lambda x: f"{x:.2f}")
        display_df["price"] = display_df["price"].apply(lambda x: f"${x:.2f}")
        display_df["amount"] = display_df["amount"].apply(lambda x: f"${x:.2f}")
        display_df["pnl"] = display_df["pnl"].apply(lambda x: f"${x:.2f}")

        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent trades available")


def render_current_positions(positions_df: pd.DataFrame):
    """
    Render current positions table.

    Args:
        positions_df: DataFrame of current positions
    """
    st.subheader("Current Positions")

    if not positions_df.empty:
        # Format the dataframe
        display_df = positions_df.copy()
        display_df["quantity"] = display_df["quantity"].apply(lambda x: f"{x:.2f}")
        display_df["avg_entry_price"] = display_df["avg_entry_price"].apply(
            lambda x: f"${x:.2f}"
        )
        display_df["current_price"] = display_df["current_price"].apply(
            lambda x: f"${x:.2f}"
        )
        display_df["market_value"] = display_df["market_value"].apply(
            lambda x: f"${x:.2f}"
        )
        display_df["unrealized_pnl"] = display_df["unrealized_pnl"].apply(
            lambda x: f"${x:.2f}"
        )
        display_df["unrealized_pnl_pct"] = display_df["unrealized_pnl_pct"].apply(
            lambda x: f"{x:.2f}%"
        )

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Position breakdown pie chart
        if len(positions_df) > 0:
            fig = px.pie(
                positions_df,
                values="market_value",
                names="symbol",
                title="Position Allocation",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No open positions")


def render_risk_metrics(risk_metrics: Dict):
    """
    Render detailed risk metrics.

    Args:
        risk_metrics: Risk metrics dictionary
    """
    st.subheader("Risk Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
        st.metric("Profit Factor", f"{risk_metrics.get('profit_factor', 0):.2f}")

    with col2:
        st.metric("Average Win", f"${risk_metrics.get('avg_win', 0):.2f}")
        st.metric("Average Loss", f"${risk_metrics.get('avg_loss', 0):.2f}")

    with col3:
        win_rate = risk_metrics.get("win_rate", 0)
        st.metric("Win Rate", f"{win_rate:.1f}%")
        st.metric("Max Drawdown", f"{risk_metrics.get('max_drawdown', 0):.2f}%")


def render_alerts(alerts: List[Dict]):
    """
    Render alert history.

    Args:
        alerts: List of alert dictionaries
    """
    st.subheader("Recent Alerts")

    if alerts:
        for alert in reversed(alerts[-10:]):  # Show last 10 alerts
            severity = alert.get("severity", "INFO")
            message = alert.get("message", "")
            timestamp = alert.get("timestamp", "")

            if severity == "CRITICAL":
                alert_class = "alert-critical"
                icon = "🚨"
            elif severity == "WARNING":
                alert_class = "alert-warning"
                icon = "⚠️"
            else:
                alert_class = "alert-info"
                icon = "ℹ️"

            st.markdown(
                f'<div class="{alert_class}">'
                f"{icon} <strong>{severity}</strong> - {timestamp}<br>"
                f"{message}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No alerts")


def render_system_status(system_status: Dict):
    """
    Render system status in sidebar.

    Args:
        system_status: System status dictionary
    """
    st.sidebar.title("System Status")

    # Trading status
    trading_enabled = system_status.get("trading_enabled", False)
    status_class = "status-active" if trading_enabled else "status-inactive"
    status_text = "ACTIVE" if trading_enabled else "INACTIVE"

    st.sidebar.markdown(
        f'<div><span class="status-indicator {status_class}"></span>'
        f"<strong>Trading:</strong> {status_text}</div>",
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("---")

    # Circuit breakers
    st.sidebar.subheader("Circuit Breakers")
    circuit_breakers = system_status.get("circuit_breakers", {})

    for breaker_name, triggered in circuit_breakers.items():
        status_class = "status-inactive" if not triggered else "status-warning"
        status_text = "TRIGGERED" if triggered else "OK"
        display_name = breaker_name.replace("_", " ").title()

        st.sidebar.markdown(
            f'<div><span class="status-indicator {status_class}"></span>'
            f"{display_name}: {status_text}</div>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")

    # System health
    health = system_status.get("system_health", "UNKNOWN")
    health_class = "status-active" if health == "HEALTHY" else "status-warning"

    st.sidebar.markdown(
        f'<div><span class="status-indicator {health_class}"></span>'
        f"<strong>System Health:</strong> {health}</div>",
        unsafe_allow_html=True,
    )

    # Active strategies
    st.sidebar.markdown("---")
    st.sidebar.subheader("Active Strategies")
    active_strategies = system_status.get("active_strategies", [])
    for strategy in active_strategies:
        st.sidebar.markdown(f"- {strategy}")

    # Last update
    last_update = system_status.get("last_update", "Unknown")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last Update: {last_update}")


def render_sidebar_controls(data_manager: DashboardDataManager):
    """
    Render sidebar controls.

    Args:
        data_manager: Instance of DashboardDataManager

    Returns:
        Tuple of (auto_refresh, refresh_interval, date_filter)
    """
    st.sidebar.title("Controls")

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)

    # Refresh interval
    if auto_refresh:
        refresh_interval = st.sidebar.slider(
            "Refresh interval (seconds)", min_value=10, max_value=300, value=60, step=10
        )
    else:
        refresh_interval = None

    # Manual refresh button
    if st.sidebar.button("Refresh Now", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")

    # Date filter
    st.sidebar.subheader("Filters")
    date_range = st.sidebar.selectbox(
        "Time Range",
        options=["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
        index=1,
    )

    return auto_refresh, refresh_interval, date_range


def filter_trades_by_date(trades_df: pd.DataFrame, date_range: str) -> pd.DataFrame:
    """
    Filter trades by date range.

    Args:
        trades_df: DataFrame of trades
        date_range: Selected date range string

    Returns:
        Filtered DataFrame
    """
    if trades_df.empty or "timestamp" not in trades_df.columns:
        return trades_df

    now = datetime.now()

    if date_range == "Last 24 Hours":
        cutoff = now - timedelta(hours=24)
    elif date_range == "Last 7 Days":
        cutoff = now - timedelta(days=7)
    elif date_range == "Last 30 Days":
        cutoff = now - timedelta(days=30)
    else:  # All Time
        return trades_df

    return trades_df[trades_df["timestamp"] >= cutoff]


def main():
    """Main dashboard application."""

    # Initialize data manager
    data_dir = Path(__file__).parent.parent / "data"
    data_manager = DashboardDataManager(str(data_dir))

    # Render sidebar controls
    auto_refresh, refresh_interval, date_filter = render_sidebar_controls(data_manager)

    # Load system status
    system_status = data_manager.load_system_status()
    render_system_status(system_status)

    # Load data
    trades_df = data_manager.load_trades()
    performance = data_manager.load_performance()
    positions_df = data_manager.load_positions()
    alerts = data_manager.load_alerts()

    # Filter trades by date
    filtered_trades = filter_trades_by_date(trades_df, date_filter)

    # Calculate risk metrics
    risk_metrics = calculate_risk_metrics(filtered_trades, performance)

    # Render header
    render_header()

    # Row 1: Metric cards
    render_metric_cards(performance, risk_metrics)

    st.markdown("---")

    # Row 2: Strategy performance
    render_strategy_performance(performance)

    st.markdown("---")

    # Row 3: Charts
    col1, col2 = st.columns(2)

    with col1:
        render_equity_curve(performance)

    with col2:
        render_daily_pnl_chart(performance)

    st.markdown("---")

    # Row 4: Recent trades
    render_recent_trades(filtered_trades)

    st.markdown("---")

    # Row 5: Current positions
    render_current_positions(positions_df)

    st.markdown("---")

    # Row 6: Risk metrics
    render_risk_metrics(risk_metrics)

    st.markdown("---")

    # Row 7: Alerts
    render_alerts(alerts)

    # Auto-refresh implementation
    if auto_refresh and refresh_interval:
        import time

        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.exception(e)
