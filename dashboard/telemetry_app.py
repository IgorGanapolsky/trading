"""Streamlit app for hybrid funnel telemetry."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from src.utils.telemetry_summary import load_events, summarize_events

LOG_PATH = Path("data/audit_trail/hybrid_funnel_runs.jsonl")


def main() -> None:
    st.set_page_config(page_title="Telemetry Monitor", layout="wide")
    st.title("Hybrid Funnel Telemetry Monitor")

    log_path = Path(st.sidebar.text_input("Telemetry log path", str(LOG_PATH)))
    top_n = st.sidebar.slider("Top tickers", min_value=3, max_value=20, value=10)

    try:
        events = load_events(log_path)
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    summary = summarize_events(events, top_n=top_n)

    st.metric("Events", summary["event_count"])
    st.metric("Generated", summary["generated_at"])

    gate_df = pd.DataFrame.from_dict(summary["gates"], orient="index")
    gate_df["pass_rate_pct"] = (gate_df["pass"] / gate_df["total"] * 100).fillna(0).round(1)
    st.subheader("Gate Outcomes")
    st.dataframe(gate_df, use_container_width=True)

    if summary["top_tickers"]:
        st.subheader("Most Active Tickers")
        ticker_df = pd.DataFrame(summary["top_tickers"], columns=["ticker", "events"])
        st.bar_chart(ticker_df.set_index("ticker"))

    if summary["recent_errors"]:
        st.subheader("Recent Errors / Rejects")
        for event in summary["recent_errors"]:
            st.write(
                f"- **{event.get('ts')}** | `{event.get('event')}` "
                f"| `{event.get('ticker')}` | {event.get('payload', {}).get('reason', event.get('status'))}"
            )


if __name__ == "__main__":
    main()
