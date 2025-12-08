"""
Trade Impact Page - Performance comparison with vs without sentiment analysis.
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
)

st.set_page_config(page_title="Trade Impact", page_icon="💰", layout="wide")

st.title("💰 Sentiment Impact on Trading Performance")
st.markdown("Analyze how sentiment analysis affects trade outcomes and ROI")


def load_trade_data(data_dir: Path):
    """Load historical trade data."""
    trade_files = sorted(data_dir.glob("trades_*.json"))

    all_trades = []
    for file in trade_files:
        with open(file) as f:
            trades = json.load(f)
            if isinstance(trades, list):
                all_trades.extend(trades)

    return all_trades


def load_system_state(data_dir: Path):
    """Load system state for performance metrics."""
    state_file = data_dir / "system_state.json"

    if not state_file.exists():
        return None

    with open(state_file) as f:
        return json.load(f)


def main():
    # Add timestamp to force UI update and show freshness
    st.markdown(
        f"<div style='text-align: right; color: gray; font-size: small;'>Dashboard Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
        unsafe_allow_html=True,
    )

    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"

    # Load data
    trades = load_trade_data(data_dir)
    system_state = load_system_state(data_dir)

    if not system_state:
        st.warning("System state data not available.")
        return

    # --- Current System Performance ---
    st.subheader("📊 Current System Performance")
    perf = system_state.get("performance", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", perf.get("total_trades", 0))
    with col2:
        st.metric("Win Rate", f"{perf.get('win_rate', 0):.1f}%")
    with col3:
        total_pl = system_state.get("account", {}).get("total_pl", 0)
        st.metric("Total P/L", f"${total_pl:.2f}")
    with col4:
        st.metric("Avg Return", f"{perf.get('avg_return', 0):.2f}%")

    st.markdown("---")

    # --- Real Trade Log ---
    st.subheader("📝 Real Trade Log")

    if trades:
        # Convert to DataFrame
        trade_df = pd.DataFrame(trades)

        # Display all columns available, prioritizing key ones
        preferred_cols = ["timestamp", "symbol", "action", "price", "amount", "status", "strategy"]
        cols = [c for c in preferred_cols if c in trade_df.columns]

        if not cols:
            cols = trade_df.columns.tolist()

        # Format timestamp for readability
        if "timestamp" in trade_df.columns:
            try:
                trade_df["timestamp"] = pd.to_datetime(trade_df["timestamp"]).dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except:
                pass

        st.dataframe(
            trade_df[cols].style.format(precision=2), use_container_width=True, hide_index=True
        )
    else:
        st.info("No trades found in data directory.")

    # --- Raw Data Expander (Trust verification) ---
    with st.expander("View Raw Data Source"):
        st.write(f"Data Directory: {data_dir}")
        st.json(trades)


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
