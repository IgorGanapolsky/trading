#!/usr/bin/env python3
"""
DAILY TRADING REPORT

Generates comprehensive daily summary:
- Trades executed
- P/L for the day
- Agent decisions
- RL learning progress
- Circuit breaker status
- Win rate tracking

Runs automatically after trading completes
"""
import os
import sys
import json
from pathlib import Path
from datetime import date, datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import alpaca_trade_api as tradeapi

from src.utils.error_monitoring import init_sentry

# Configuration
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError(
        "ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set"
    )

DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def load_todays_trades() -> List[Dict[str, Any]]:
    """Load today's trade log."""
    today = date.today().isoformat()
    trades_file = DATA_DIR / f"trades_{today}.json"

    if not trades_file.exists():
        return []

    try:
        with open(trades_file, "r") as f:
            return json.load(f)
    except:
        return []


def get_portfolio_status() -> Dict[str, Any]:
    """Get current portfolio status from Alpaca."""
    try:
        api = tradeapi.REST(
            ALPACA_KEY, ALPACA_SECRET, "https://paper-api.alpaca.markets"
        )
        account = api.get_account()

        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "pl_today": float(account.equity) - 100000.0,  # Assuming $100K start
        }
    except Exception as e:
        return {"error": str(e)}


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def load_trend_snapshot() -> Optional[Dict[str, Any]]:
    return _load_json(DATA_DIR / "trend_snapshot.json")


def load_guardrail_summary() -> Optional[Dict[str, Any]]:
    return _load_json(DATA_DIR / "economic_guardrails.json")


def get_rl_stats() -> Dict[str, Any]:
    """Get RL policy learning stats."""
    rl_file = DATA_DIR / "rl_policy_state.json"

    if not rl_file.exists():
        return {"states_learned": 0, "action_distribution": {}}

    try:
        with open(rl_file, "r") as f:
            data = json.load(f)
            q_table = data.get("q_table", {})

            # Count actions
            action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
            for state_actions in q_table.values():
                best_action = max(state_actions, key=state_actions.get)
                action_counts[best_action] += 1

            return {
                "states_learned": len(q_table),
                "action_distribution": action_counts,
                "exploration_rate": data.get("exploration_rate", 0.2),
            }
    except:
        return {"states_learned": 0, "action_distribution": {}}


def get_manual_trading_status() -> Dict[str, Any]:
    """Get manual trading status from SoFi and crowdfunding platforms."""
    manual_trades_file = DATA_DIR / "manual_trades.json"

    if not manual_trades_file.exists():
        return {"positions": [], "total_equity": 0.0, "total_pl": 0.0, "trade_count": 0}

    try:
        with open(manual_trades_file, "r") as f:
            data = json.load(f)
            positions = data.get("positions", [])

            # Calculate totals
            total_equity = 0.0
            total_pl = 0.0
            for pos in positions:
                value = pos["quantity"] * pos["current_price"]
                cost = pos["quantity"] * pos["avg_price"]
                total_equity += value
                total_pl += value - cost

            return {
                "positions": positions,
                "total_equity": total_equity,
                "total_pl": total_pl,
                "trade_count": len(data.get("trades", [])),
            }
    except:
        return {"positions": [], "total_equity": 0.0, "total_pl": 0.0, "trade_count": 0}


def get_circuit_breaker_status() -> Dict[str, Any]:
    """Get circuit breaker status."""
    try:
        from src.safety.circuit_breakers import CircuitBreaker

        breaker = CircuitBreaker()
        return breaker.get_status()
    except:
        return {"error": "Could not load circuit breaker status"}


def generate_report() -> str:
    """Generate daily report."""
    today = date.today().isoformat()

    # Load data
    trades = load_todays_trades()
    portfolio = get_portfolio_status()
    manual_trading = get_manual_trading_status()
    rl_stats = get_rl_stats()
    cb_status = get_circuit_breaker_status()
    trend_snapshot = load_trend_snapshot()
    guardrails = load_guardrail_summary()

    # Build report
    report = f"""
{'=' * 80}
📊 DAILY TRADING REPORT - {today}
{'=' * 80}

🤖 SYSTEM STATUS
{'=' * 80}
Multi-Agent Trading System (2025 Standard)
- MetaAgent + Research + Signal + Risk + Execution + RL

{'=' * 80}
💰 PORTFOLIO (Multi-Platform Summary)
{'=' * 80}

ALPACA (Automated - Tiers 1-2):
  Equity:        ${portfolio.get('equity', 0):,.2f}
  Cash:          ${portfolio.get('cash', 0):,.2f}
  Buying Power:  ${portfolio.get('buying_power', 0):,.2f}
  P/L Today:     ${portfolio.get('pl_today', 0):+,.2f}

MANUAL TRADING (Tiers 3-4):
  Total Value:   ${manual_trading['total_equity']:,.2f}
  Positions:     {len(manual_trading['positions'])}
  P/L:           ${manual_trading['total_pl']:+,.2f}
  Trades Total:  {manual_trading['trade_count']}

COMBINED TOTAL:
  Total Equity:  ${portfolio.get('equity', 0) + manual_trading['total_equity']:,.2f}
  Total P/L:     ${portfolio.get('pl_today', 0) + manual_trading['total_pl']:+,.2f}

{'=' * 80}
📈 TRADES EXECUTED
{'=' * 80}
Total Trades: {len(trades)}

"""

    if trades:
        for i, trade in enumerate(trades, 1):
            report += f"\nTrade {i}:\n"
            report += f"  Symbol: {trade.get('symbol', 'N/A')}\n"
            report += f"  Action: {trade.get('action', 'N/A')}\n"
            report += f"  Amount: ${trade.get('position_size', 0):,.2f}\n"
            report += f"  Time: {trade.get('timestamp', 'N/A')}\n"
            if "order_id" in trade:
                report += f"  Order ID: {trade['order_id']}\n"
    else:
        report += "No trades executed today\n"

    # Add manual trading positions section
    report += f"""
{'=' * 80}
📊 MANUAL POSITIONS (SoFi + Crowdfunding)
{'=' * 80}
"""

    if manual_trading["positions"]:
        # Platform mapping
        platform_names = {
            "sofi": "SoFi",
            "wefunder": "Wefunder",
            "republic": "Republic",
            "startengine": "StartEngine",
        }

        for pos in manual_trading["positions"]:
            platform = platform_names.get(pos["platform"], pos["platform"])
            value = pos["quantity"] * pos["current_price"]
            cost = pos["quantity"] * pos["avg_price"]
            pl = value - cost
            pl_pct = (pl / cost * 100) if cost > 0 else 0
            status = "✅" if pl > 0 else "❌" if pl < 0 else "➖"

            report += f"""
{status} {pos['symbol']} ({platform} - {pos['tier'].upper()})
  Quantity:      {pos['quantity']}
  Avg Price:     ${pos['avg_price']:.2f}
  Current Price: ${pos['current_price']:.2f}
  Total Value:   ${value:.2f}
  P/L:           ${pl:+.2f} ({pl_pct:+.2f}%)
"""
    else:
        report += "No manual positions yet\n"
        report += (
            "\n💡 Use 'python scripts/manual_trade_entry.py' to log manual trades\n"
        )

    report += f"""
{'=' * 80}
📈 TREND SNAPSHOT (Core ETFs)
{'=' * 80}
"""
    if trend_snapshot and trend_snapshot.get("symbols"):
        report += (
            f"Generated: {trend_snapshot.get('generated_at', 'N/A')}\n"
        )
        for symbol in sorted(trend_snapshot["symbols"].keys()):
            entry = trend_snapshot["symbols"][symbol]
            gate = "OPEN ✅" if entry.get("gate_open") else "CLOSED ❌"
            report += (
                f"{symbol:<4} {gate} | SMA20={entry.get('sma20', 0):.2f} "
                f"SMA50={entry.get('sma50', 0):.2f} 5d={entry.get('return_5d', 0):+.2f}% "
                f"21d={entry.get('return_21d', 0):+.2f}% ({entry.get('regime_bias', 'n/a')})\n"
            )
    else:
        report += "Trend snapshot unavailable (generate after next trading run)\n"

    report += f"""
{'=' * 80}
🛡️ ECONOMIC GUARDRAILS
{'=' * 80}
"""
    if guardrails:
        market_blockers = guardrails.get("market_blockers") or []
        symbol_blockers = guardrails.get("symbol_blockers") or {}

        if market_blockers:
            for blocker in market_blockers:
                report += (
                    f"Market: {blocker.get('date', 'N/A')} - "
                    f"{blocker.get('description', 'Unknown')} "
                    f"(impact: {blocker.get('impact', 'n/a')})\n"
                )
        else:
            report += "Market: No blocking events detected\n"

        if symbol_blockers:
            for symbol in sorted(symbol_blockers.keys()):
                for entry in symbol_blockers[symbol]:
                    report += (
                        f"{symbol}: {entry.get('date', 'N/A')} - "
                        f"{entry.get('description', 'Event')}\n"
                    )
        else:
            report += "Symbols: No blockers for watched tickers\n"
    else:
        report += "Guardrail cache unavailable\n"

    report += f"""
{'=' * 80}
🎓 REINFORCEMENT LEARNING
{'=' * 80}
States Learned:     {rl_stats['states_learned']}
Exploration Rate:   {rl_stats.get('exploration_rate', 0.2):.2%}
Action Preferences:
  BUY:  {rl_stats['action_distribution'].get('BUY', 0)} states
  SELL: {rl_stats['action_distribution'].get('SELL', 0)} states
  HOLD: {rl_stats['action_distribution'].get('HOLD', 0)} states

{'=' * 80}
🛡️ CIRCUIT BREAKERS
{'=' * 80}
Status:             {'🚨 TRIPPED' if cb_status.get('is_tripped') else '✅ OK'}
Consecutive Losses: {cb_status.get('consecutive_losses', 0)}
API Errors Today:   {cb_status.get('api_errors_today', 0)}
"""

    if cb_status.get("is_tripped"):
        report += f"\n⚠️  TRIP REASON: {cb_status.get('trip_reason', 'Unknown')}\n"
        report += f"⚠️  DETAILS: {cb_status.get('trip_details', 'N/A')}\n"
        report += f"⚠️  ACTION REQUIRED: Manual reset needed\n"

    report += f"""
{'=' * 80}
📁 LOG FILES
{'=' * 80}
Trading Log:  logs/advanced_trading.log
Trade Data:   data/trades_{today}.json
RL Policy:    data/rl_policy_state.json
CB State:     data/circuit_breaker_state.json

{'=' * 80}
Generated: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}
{'=' * 80}
"""

    return report


def main():
    """Generate and save daily report."""
    init_sentry()
    today = date.today().isoformat()
    report = generate_report()

    # Print to console
    print(report)

    # Save to file
    report_file = REPORTS_DIR / f"daily_report_{today}.txt"
    with open(report_file, "w") as f:
        f.write(report)

    print(f"\n📁 Report saved to: {report_file}\n")


if __name__ == "__main__":
    main()
