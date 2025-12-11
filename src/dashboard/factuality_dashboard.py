"""
Streamlit Dashboard for Factuality Metrics

Real-time visualization of:
- FACTS benchmark scores
- Model accuracy tracking
- Hallucination incidents
- Circuit breaker status
- Position reconciliation
- Backtest results

Run with: streamlit run src/dashboard/factuality_dashboard.py

Created: Dec 11, 2025
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

# Data paths
DATA_DIR = Path("data")
FACTUALITY_METRICS_PATH = DATA_DIR / "factuality_metrics.json"
HALLUCINATION_LOG_PATH = DATA_DIR / "hallucination_log.json"
CIRCUIT_BREAKER_STATE_PATH = DATA_DIR / "circuit_breaker_state.json"
RECONCILIATION_LOG_PATH = DATA_DIR / "position_reconciliation.json"
BACKTEST_RESULTS_PATH = DATA_DIR / "backtest_results.json"
PREDICTIONS_LOG_PATH = DATA_DIR / "predictions_log.json"

# FACTS Benchmark scores (Dec 2025)
FACTS_SCORES = {
    "google/gemini-3-pro-preview": 0.688,
    "anthropic/claude-sonnet-4": 0.665,
    "openai/gpt-4o": 0.658,
    "deepseek/deepseek-r1": 0.640,
}


def load_json_file(path: Path) -> dict:
    """Load JSON file or return empty dict."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def main():
    st.set_page_config(
        page_title="Factuality Monitor",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 LLM Factuality Monitor")
    st.caption("Based on Google DeepMind FACTS Benchmark (Dec 2025) - 70% Ceiling")

    # Sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Overview", "Model Accuracy", "Hallucinations", "Circuit Breakers", "Backtests"],
    )

    if page == "Overview":
        render_overview()
    elif page == "Model Accuracy":
        render_model_accuracy()
    elif page == "Hallucinations":
        render_hallucinations()
    elif page == "Circuit Breakers":
        render_circuit_breakers()
    elif page == "Backtests":
        render_backtests()


def render_overview():
    """Render overview page with key metrics."""
    st.header("📊 Overview")

    # Load data
    factuality_data = load_json_file(FACTUALITY_METRICS_PATH)
    hallucination_data = load_json_file(HALLUCINATION_LOG_PATH)
    circuit_data = load_json_file(CIRCUIT_BREAKER_STATE_PATH)

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    # Total models tracked
    model_metrics = factuality_data.get("models", {})
    with col1:
        st.metric(
            "Models Tracked",
            len(model_metrics),
            help="Number of LLM models being monitored",
        )

    # Total hallucinations
    total_hallucinations = sum(
        m.get("hallucinations", 0) for m in model_metrics.values()
    )
    with col2:
        st.metric(
            "Total Hallucinations",
            total_hallucinations,
            help="Total hallucinations detected across all models",
        )

    # Overall accuracy
    total_claims = sum(m.get("total_claims", 0) for m in model_metrics.values())
    verified = sum(m.get("verified_claims", 0) for m in model_metrics.values())
    overall_accuracy = verified / total_claims if total_claims > 0 else 0
    with col3:
        st.metric(
            "Overall Accuracy",
            f"{overall_accuracy:.1%}",
            help="Overall verification accuracy across all models",
        )

    # Circuit breakers tripped
    models_data = circuit_data.get("models", {})
    disabled = sum(1 for m in models_data.values() if m.get("state") == "open")
    with col4:
        st.metric(
            "Models Disabled",
            disabled,
            help="Models disabled by circuit breaker",
        )

    st.divider()

    # FACTS Benchmark reference
    st.subheader("📈 FACTS Benchmark Scores (Reference)")
    st.caption("Per Google DeepMind Dec 2025 - No model exceeds 70%")

    facts_df_data = [
        {"Model": model, "FACTS Score": f"{score:.1%}", "Score": score}
        for model, score in FACTS_SCORES.items()
    ]

    import pandas as pd
    facts_df = pd.DataFrame(facts_df_data)
    st.bar_chart(facts_df.set_index("Model")["Score"])

    st.warning(
        "⚠️ **70% Factuality Ceiling**: All top LLMs have <70% accuracy. "
        "Always verify claims against API ground truth."
    )


def render_model_accuracy():
    """Render model accuracy tracking page."""
    st.header("📊 Model Accuracy Tracking")

    factuality_data = load_json_file(FACTUALITY_METRICS_PATH)
    predictions_data = load_json_file(PREDICTIONS_LOG_PATH)

    model_metrics = factuality_data.get("models", {})

    if not model_metrics:
        st.info("No model metrics recorded yet.")
        return

    import pandas as pd

    # Build dataframe
    rows = []
    for model, metrics in model_metrics.items():
        facts_score = FACTS_SCORES.get(model, 0.60)
        observed = metrics.get("verified_claims", 0) / max(1, metrics.get("total_claims", 1))

        rows.append({
            "Model": model.split("/")[-1],  # Short name
            "FACTS Score": facts_score,
            "Observed Accuracy": observed,
            "Total Claims": metrics.get("total_claims", 0),
            "Hallucinations": metrics.get("hallucinations", 0),
            "Last Updated": metrics.get("last_updated", "N/A"),
        })

    df = pd.DataFrame(rows)

    # Display table
    st.dataframe(
        df.style.format({
            "FACTS Score": "{:.1%}",
            "Observed Accuracy": "{:.1%}",
        }),
        use_container_width=True,
    )

    # Chart
    if len(df) > 0:
        st.subheader("FACTS vs Observed Accuracy")
        chart_df = df[["Model", "FACTS Score", "Observed Accuracy"]].set_index("Model")
        st.bar_chart(chart_df)


def render_hallucinations():
    """Render hallucination incidents page."""
    st.header("🚨 Hallucination Incidents")

    hallucination_data = load_json_file(HALLUCINATION_LOG_PATH)
    incidents = hallucination_data.get("incidents", [])

    if not incidents:
        st.success("✅ No hallucinations recorded yet!")
        return

    st.metric("Total Incidents", len(incidents))

    # Recent incidents
    st.subheader("Recent Incidents")

    for incident in incidents[-10:][::-1]:  # Last 10, newest first
        severity = incident.get("severity", "medium")
        severity_color = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }.get(severity, "⚪")

        with st.expander(
            f"{severity_color} {incident.get('hallucination_type', 'unknown')} - {incident.get('model', 'unknown')}"
        ):
            st.write(f"**Timestamp:** {incident.get('timestamp', 'N/A')}")
            st.write(f"**Model:** {incident.get('model', 'N/A')}")
            st.write(f"**Type:** {incident.get('hallucination_type', 'N/A')}")
            st.write(f"**Claimed:** {incident.get('claimed_value', 'N/A')}")
            st.write(f"**Actual:** {incident.get('actual_value', 'N/A')}")
            st.write(f"**Severity:** {severity}")

    # Breakdown by type
    st.subheader("Breakdown by Type")
    type_counts = {}
    for incident in incidents:
        t = incident.get("hallucination_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    if type_counts:
        import pandas as pd
        type_df = pd.DataFrame([
            {"Type": k, "Count": v} for k, v in type_counts.items()
        ])
        st.bar_chart(type_df.set_index("Type"))


def render_circuit_breakers():
    """Render circuit breaker status page."""
    st.header("🔌 Circuit Breaker Status")

    circuit_data = load_json_file(CIRCUIT_BREAKER_STATE_PATH)
    models = circuit_data.get("models", {})

    if not models:
        st.info("No circuit breaker data yet.")
        return

    # Status overview
    enabled = sum(1 for m in models.values() if m.get("state") != "open")
    disabled = sum(1 for m in models.values() if m.get("state") == "open")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("🟢 Enabled Models", enabled)
    with col2:
        st.metric("🔴 Disabled Models", disabled)

    st.divider()

    # Model status cards
    for model, state in models.items():
        status = state.get("state", "closed")
        accuracy = state.get("accuracy", 1.0)
        trips = state.get("trip_count", 0)

        status_color = {
            "closed": "🟢",
            "open": "🔴",
            "half_open": "🟡",
        }.get(status, "⚪")

        with st.expander(f"{status_color} {model.split('/')[-1]} - {status.upper()}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Accuracy", f"{accuracy:.1%}")
            with col2:
                st.metric("Total Trips", trips)
            with col3:
                st.metric("Consecutive Failures", state.get("consecutive_failures", 0))

            if state.get("cooldown_until"):
                st.warning(f"⏰ Cooldown until: {state['cooldown_until']}")

            if state.get("trip_reasons"):
                st.write("**Recent Trip Reasons:**")
                for reason in state["trip_reasons"][-3:]:
                    st.write(f"- {reason}")


def render_backtests():
    """Render backtest results page."""
    st.header("📈 Backtest Results")

    backtest_data = load_json_file(BACKTEST_RESULTS_PATH)
    results = backtest_data.get("results", {})

    if not results:
        st.info("No backtest results yet.")
        return

    import pandas as pd

    # Build dataframe
    rows = []
    for key, result in results.items():
        rows.append({
            "Symbol": result.get("symbol", "N/A"),
            "Direction": result.get("signal_direction", "N/A"),
            "Model": result.get("model", "N/A").split("/")[-1],
            "Win Rate": result.get("win_rate", 0),
            "Sharpe": result.get("sharpe_ratio", 0),
            "Max DD": result.get("max_drawdown", 0),
            "Valid": "✅" if result.get("is_valid") else "❌",
            "Message": result.get("validation_message", "N/A"),
        })

    df = pd.DataFrame(rows)

    # Summary
    valid_count = sum(1 for r in results.values() if r.get("is_valid"))
    st.metric("Valid Signals", f"{valid_count}/{len(results)}")

    # Table
    st.dataframe(
        df.style.format({
            "Win Rate": "{:.1%}",
            "Sharpe": "{:.2f}",
            "Max DD": "{:.1%}",
        }),
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
