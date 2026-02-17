#!/usr/bin/env python3
"""
Generate Wiki Home Page with Current Account Data

Pulls live data from Alpaca and generates an accurate wiki home page.
Called by .github/workflows/update-wiki.yml
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient

# Config
API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
STARTING_CAPITAL = 100000.0  # $100K account started Jan 30, 2026
PHASE1_REQUIRED_TRADES = 30  # Phase 1: Validate with 30 trades
PHASE1_WIN_RATE_TARGET = 0.75  # >75% win rate required
SYSTEM_STATE_PATH = Path("data/system_state.json")
TRADES_PATH = Path("data/trades.json")


def get_account_data() -> dict:
    """Fetch current account data from Alpaca."""
    if not API_KEY or not SECRET_KEY:
        # Fallback: read from system_state.json instead of hardcoded values
        if SYSTEM_STATE_PATH.exists():
            try:
                state = json.loads(SYSTEM_STATE_PATH.read_text())
                portfolio = state.get("portfolio", {})
                positions = state.get("positions", [])
                # Parse IC positions from system state
                iron_condors = []
                expiries: dict[str, dict] = {}
                for pos in positions:
                    sym = pos.get("symbol", "")
                    if len(sym) > 10:
                        expiry = sym[3:9]
                        if expiry not in expiries:
                            expiries[expiry] = {"puts": [], "calls": []}
                        strike = int(sym[10:18]) / 1000
                        opt_type = "puts" if "P" in sym[9:10] else "calls"
                        expiries[expiry][opt_type].append(
                            {"strike": strike, "qty": int(float(pos.get("qty", 0)))}
                        )
                for expiry, legs in expiries.items():
                    if legs["puts"] and legs["calls"]:
                        put_strikes = sorted([p["strike"] for p in legs["puts"]])
                        call_strikes = sorted([c["strike"] for c in legs["calls"]])
                        exp_date = datetime.strptime(f"20{expiry}", "%Y%m%d")
                        iron_condors.append(
                            {
                                "expiry": exp_date.strftime("%b %d, %Y"),
                                "put_spread": f"{put_strikes[0]:.0f}/{put_strikes[-1]:.0f}"
                                if len(put_strikes) >= 2
                                else str(put_strikes[0]),
                                "call_spread": f"{call_strikes[0]:.0f}/{call_strikes[-1]:.0f}"
                                if len(call_strikes) >= 2
                                else str(call_strikes[0]),
                            }
                        )
                return {
                    "equity": portfolio.get("equity", STARTING_CAPITAL),
                    "cash": portfolio.get("cash", STARTING_CAPITAL),
                    "buying_power": portfolio.get("cash", STARTING_CAPITAL) * 2,
                    "positions": positions,
                    "iron_condors": iron_condors,
                }
            except (json.JSONDecodeError, KeyError):
                pass
        return {
            "equity": STARTING_CAPITAL,
            "cash": STARTING_CAPITAL,
            "buying_power": STARTING_CAPITAL * 2,
            "positions": [],
        }

    client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    account = client.get_account()
    positions = client.get_all_positions()

    # Parse iron condors
    iron_condors = []
    options = [p for p in positions if len(p.symbol) > 10]

    # Group by expiry
    expiries = {}
    for pos in options:
        symbol = pos.symbol
        expiry = symbol[3:9]  # YYMMDD
        if expiry not in expiries:
            expiries[expiry] = {"puts": [], "calls": []}

        strike = int(symbol[10:18]) / 1000
        opt_type = "puts" if "P" in symbol[9:10] else "calls"
        qty = int(float(pos.qty))
        expiries[expiry][opt_type].append({"strike": strike, "qty": qty})

    # Format iron condors
    for expiry, legs in expiries.items():
        if legs["puts"] and legs["calls"]:
            put_strikes = sorted([p["strike"] for p in legs["puts"]])
            call_strikes = sorted([c["strike"] for c in legs["calls"]])
            exp_date = datetime.strptime(f"20{expiry}", "%Y%m%d")
            iron_condors.append(
                {
                    "expiry": exp_date.strftime("%b %d, %Y"),
                    "put_spread": (
                        f"{put_strikes[0]:.0f}/{put_strikes[-1]:.0f}"
                        if len(put_strikes) >= 2
                        else str(put_strikes[0])
                    ),
                    "call_spread": (
                        f"{call_strikes[0]:.0f}/{call_strikes[-1]:.0f}"
                        if len(call_strikes) >= 2
                        else str(call_strikes[0])
                    ),
                }
            )

    return {
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "iron_condors": iron_condors,
    }


def get_phase1_metrics() -> dict:
    """Load Phase 1 validation metrics from trades.json."""
    defaults = {
        "closed_trades": 0,
        "win_rate": 0.0,
        "realized_pl": 0.0,
    }
    if not TRADES_PATH.exists():
        return defaults
    try:
        trades_data = json.loads(TRADES_PATH.read_text())
        stats = trades_data.get("stats", {})
        closed = stats.get("closed_trades", 0)
        wins = stats.get("winning_trades", 0)
        return {
            "closed_trades": closed,
            "win_rate": (wins / closed * 100) if closed > 0 else 0.0,
            "realized_pl": stats.get("total_realized_pnl", 0.0),
        }
    except (json.JSONDecodeError, KeyError):
        return defaults


def generate_wiki_home(data: dict) -> str:
    """Generate wiki home page markdown."""
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    date_str = now.strftime("%b %d, %Y")

    equity = data["equity"]
    net_gain = equity - STARTING_CAPITAL
    net_gain_pct = (net_gain / STARTING_CAPITAL) * 100
    iron_condors = data.get("iron_condors", [])

    # Phase 1 validation metrics
    p1 = get_phase1_metrics()

    # Generate iron condor table
    ic_table = ""
    if iron_condors:
        ic_table = "| Expiry | Put Spread | Call Spread |\n|--------|------------|-------------|\n"
        for ic in iron_condors:
            ic_table += f"| {ic['expiry']} | {ic['put_spread']} | {ic['call_spread']} |\n"
    else:
        ic_table = "*No open iron condor positions*\n"

    wiki = f"""# 🤖 AI Trading System Wiki

Welcome to the **AI-Powered Automated Trading System** wiki!

---

## 📊 [Progress Dashboard](Progress-Dashboard)

**👉 [View Live Progress Dashboard →](https://igorganapolsky.github.io/trading/)**

    The system tracks progress toward financial independence:
    - North Star goal: **$6K/month after-tax financial independence (execute as fast as safely possible)**
    - Current strategy: **SPY iron condors (15-20 delta, $10-wide wings, up to 5 concurrent positions)**
- Phil Town Rule #1: **Don't lose money**

---

## 🚀 Quick Links

### Documentation
- [CLAUDE.md](https://github.com/IgorGanapolsky/trading/blob/main/.claude/CLAUDE.md) - Strategy & directives
- [System State](https://github.com/IgorGanapolsky/trading/blob/main/data/system_state.json) - Live account data

### System Status
- [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions) - Execution logs
- [RAG Chat](https://igorganapolsky.github.io/trading/rag-query/) - Query lessons learned

### Key Features
- **Iron Condor Guardian**: Automated Rule #1 enforcement (stop loss, 7 DTE exit, 50% profit take)
- **RLHF System**: Thompson Sampling + ShieldCortex memory
- **CI/CD**: 1300+ tests, self-healing workflows
- **Multi-Agent Swarm**: Analysis, execution, and monitoring agents

---

## 📈 Current Status ({date_str})

| Metric | Value |
|--------|-------|
| **Account Equity** | ${equity:,.2f} |
| **Starting Capital** | ${STARTING_CAPITAL:,.0f} (Jan 30, 2026) |
| **Net Gain** | ${net_gain:+,.2f} ({net_gain_pct:+.2f}%) |
| **Open Positions** | {len(iron_condors)} Iron Condor(s) |
| **Strategy** | SPY Iron Condors (15-20 delta, $10-wide, max 5 concurrent) |

### Open Iron Condors
{ic_table}
---

## 🎯 North Star Goal

**Vision**: Build a reliable autonomous SPY iron condor engine that reaches $6K/month after-tax as fast as safely possible.

| Phase | Timeline | Target | Status |
|-------|----------|--------|--------|
| **Phase 1: Validate** | Now → Jun 2026 | 30 trades, >75% win rate | 🔄 In progress ({p1["closed_trades"]}/{PHASE1_REQUIRED_TRADES}) |
| **Phase 2: Scale** | Jul → Dec 2026 | 3 concurrent ICs, $500/mo | ⏳ Pending |
| **Phase 3: Grow** | 2027 | 5 ICs + credit spreads, $1,500/mo | ⏳ Pending |
| **Phase 4: Open** | 2028 | Packaged system for accounts $10K+ | ⏳ Pending |

**Strategy Parameters** (updated Feb 2026 — positive EV):
- Profit target: **75%** of max profit (let winners run)
- Stop loss: **100%** of credit (cut losers fast)
- Expected value per trade: **+$94** at 80% win rate

---

## 🛡️ Phil Town Rule #1 Enforcement

The **Iron Condor Guardian** runs every 30 minutes during market hours to enforce:

1. **Stop Loss**: Exit if loss reaches 200% of credit received
2. **7 DTE Exit**: Close positions at 7 days to expiration (gamma risk)
3. **50% Profit Take**: Lock in profits at 50% of max profit

*Automation ensures rules are followed without human intervention.*

---

*Last updated: {now.strftime("%Y-%m-%d %H:%M ET")} by GitHub Actions*
"""
    return wiki


def main():
    """Main entry point."""
    print("Fetching account data from Alpaca...")
    data = get_account_data()
    print(f"Equity: ${data['equity']:,.2f}")
    print(f"Iron Condors: {len(data.get('iron_condors', []))}")

    print("Generating wiki home page...")
    wiki_content = generate_wiki_home(data)

    # Write to file for workflow to pick up
    output_path = Path("wiki_home.md")
    output_path.write_text(wiki_content)
    print(f"Wiki home page written to {output_path}")


if __name__ == "__main__":
    main()
