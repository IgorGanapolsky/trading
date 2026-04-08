#!/usr/bin/env python3
"""
Truth Dashboard: The 5-metric reality check.
Strips away the Bayesian/LLM fluff and gives the CEO the hard numbers.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"
OUT_FILE = PROJECT_ROOT / "docs" / "truth_dashboard.md"


def build_dashboard():
    if not STATE_FILE.exists():
        print("ERROR: system_state.json not found.")
        return

    with open(STATE_FILE) as f:
        state = json.load(f)

    # 1. Equity & P/L
    paper_state = state.get("paper_account", {})
    equity = paper_state.get("equity", "Unknown")
    daily_pnl = paper_state.get("daily_pnl", "Unknown")

    # 2. Positions
    positions = state.get("positions", [])
    open_positions = len(positions)
    unrealized_pl = sum(float(p.get("unrealized_pl", 0)) for p in positions)

    # 3. Market Signals (The "Eyes")
    signals = state.get("market_signals", {})
    credit_stress = signals.get("ai_credit_stress", {}).get("status", "unknown")
    usd_macro = signals.get("usd_macro_sentiment", {}).get("status", "unknown")
    ai_cycle = signals.get("ai_cycle", {}).get("status", "unknown")

    # 4. System Mode
    mode = state.get("mode", "unknown").upper()

    def _fmt_money(val):
        try:
            return f"${float(val):,.2f}"
        except (ValueError, TypeError):
            return "Unknown"

    # Render
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    dashboard = f"""# 📈 TRUTH DASHBOARD
*Generated: {now}*

## 💰 The Bottom Line
- **System Mode:** `{mode}`
- **Total Equity:** `{_fmt_money(equity)}`
- **Daily P/L:** `{_fmt_money(daily_pnl)}`
- **Open Positions:** `{open_positions}` (Unrealized P/L: `{_fmt_money(unrealized_pl)}`)

## 👁️ Market Signals (System Vision)
*If any of these are UNKNOWN, the system is flying blind.*
- **Credit Stress:** `{credit_stress.upper()}`
- **USD Macro:** `{usd_macro.upper()}`
- **AI Cycle:** `{ai_cycle.upper()}`

## 🚨 Alerts
"""

    # Alert logic
    alerts = []
    if "unknown" in (credit_stress, usd_macro, ai_cycle):
        alerts.append("CRITICAL: Market signals are UNKNOWN. Data ingestion failure.")
    if float(equity) < 95000:
        alerts.append("WARNING: Equity below $95k threshold.")

    if not alerts:
        dashboard += "✅ All systems nominal. Vision clear.\n"
    else:
        for alert in alerts:
            dashboard += f"⚠️ {alert}\n"

    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write(dashboard)

    print(f"Truth Dashboard generated at {OUT_FILE}")
    print(dashboard)


if __name__ == "__main__":
    build_dashboard()
