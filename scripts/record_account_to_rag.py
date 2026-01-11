#!/usr/bin/env python3
"""
Record Account Balances to RAG - MANDATORY FOR OPERATIONAL INTEGRITY

This script fetches LIVE account data from Alpaca and records it to:
1. RAG knowledge file (rag_knowledge/account_history/YYYY-MM-DD.json)
2. system_state.json (updates live values)
3. performance_log.json (appends daily snapshot)

CEO DIRECTIVE (Jan 11, 2026): Account values MUST be recorded in RAG at all times.
This was a major operational breach - stale data was being used for 4+ days.

Usage:
    python3 scripts/record_account_to_rag.py

Runs in CI via daily-trading.yml and claude-agent-utility.yml
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_alpaca_client(paper: bool = False):
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        print("ERROR: alpaca-py not installed. Run: pip install alpaca-py")
        return None

    if paper:
        api_key = os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
        api_secret = os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")
    else:
        api_key = os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY")
        api_secret = os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET")

    if not api_key or not api_secret:
        print(f"ERROR: Missing Alpaca {'paper' if paper else 'brokerage'} credentials")
        return None

    return TradingClient(api_key, api_secret, paper=paper)


def fetch_account_data(client) -> dict:
    """Fetch account data from Alpaca."""
    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "last_equity": float(account.last_equity),
            "daytrade_count": account.daytrade_count,
            "pattern_day_trader": account.pattern_day_trader,
            "status": account.status.value if hasattr(account.status, 'value') else str(account.status),
        }
    except Exception as e:
        print(f"ERROR fetching account: {e}")
        return None


def fetch_positions(client) -> list:
    """Fetch current positions from Alpaca."""
    try:
        positions = client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "current_price": float(p.current_price),
                "avg_entry_price": float(p.avg_entry_price),
            }
            for p in positions
        ]
    except Exception as e:
        print(f"ERROR fetching positions: {e}")
        return []


def record_to_rag(data: dict, account_type: str):
    """Record account snapshot to RAG knowledge directory."""
    rag_dir = Path("rag_knowledge/account_history")
    rag_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today}_{account_type}.json"
    filepath = rag_dir / filename

    # Add metadata
    data["recorded_at"] = datetime.now().isoformat()
    data["account_type"] = account_type
    data["recording_source"] = "record_account_to_rag.py"

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ Recorded {account_type} account to RAG: {filepath}")
    return filepath


def update_system_state(brokerage_data: dict, paper_data: dict):
    """Update system_state.json with fresh values."""
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        print("WARNING: system_state.json not found")
        return

    with open(state_file) as f:
        state = json.load(f)

    now = datetime.now().isoformat()

    # Update brokerage account
    if brokerage_data:
        state["account"]["current_equity"] = brokerage_data["equity"]
        state["account"]["cash"] = brokerage_data["cash"]
        state["account"]["buying_power"] = brokerage_data["buying_power"]
        state["account"]["positions_value"] = brokerage_data["equity"] - brokerage_data["cash"]

    # Update paper account if exists
    if paper_data and "paper_account" in state:
        state["paper_account"]["current_equity"] = paper_data["equity"]
        state["paper_account"]["cash"] = paper_data["cash"]
        state["paper_account"]["buying_power"] = paper_data["buying_power"]

    # Update metadata
    state["meta"]["last_updated"] = now
    state["meta"]["last_sync"] = now
    state["meta"]["sync_mode"] = "live_alpaca"

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print(f"✅ Updated system_state.json at {now}")


def append_to_performance_log(brokerage_data: dict, paper_data: dict):
    """Append daily snapshot to performance log."""
    log_file = Path("data/performance_log.json")

    if log_file.exists():
        with open(log_file) as f:
            log = json.load(f)
    else:
        log = []

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()

    # Check if we already have an entry for today
    existing_idx = next((i for i, entry in enumerate(log) if entry.get("date") == today), None)

    entry = {
        "date": today,
        "timestamp": now,
        "equity": brokerage_data["equity"] if brokerage_data else 0,
        "cash": brokerage_data["cash"] if brokerage_data else 0,
        "buying_power": brokerage_data["buying_power"] if brokerage_data else 0,
        "pl": 0,  # Will be calculated from previous entry
        "pl_pct": 0,
        "account_type": "live",
        "paper_equity": paper_data["equity"] if paper_data else 0,
        "note": f"Auto-recorded by record_account_to_rag.py",
    }

    # Calculate P/L from previous entry
    if log and len(log) > 0:
        prev = log[-1] if existing_idx is None else log[existing_idx - 1] if existing_idx > 0 else None
        if prev and prev.get("equity", 0) > 0:
            entry["pl"] = entry["equity"] - prev["equity"]
            entry["pl_pct"] = (entry["pl"] / prev["equity"]) * 100

    if existing_idx is not None:
        log[existing_idx] = entry
        print(f"✅ Updated today's performance_log entry")
    else:
        log.append(entry)
        print(f"✅ Appended new entry to performance_log.json")

    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)


def main():
    """Main entry point."""
    print("=" * 60)
    print("ACCOUNT BALANCE RAG RECORDER")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Fetch brokerage account
    print("\n📊 Fetching BROKERAGE account...")
    brokerage_client = get_alpaca_client(paper=False)
    brokerage_data = None
    brokerage_positions = []

    if brokerage_client:
        brokerage_data = fetch_account_data(brokerage_client)
        brokerage_positions = fetch_positions(brokerage_client)
        if brokerage_data:
            brokerage_data["positions"] = brokerage_positions
            record_to_rag(brokerage_data, "brokerage")
            print(f"   Equity: ${brokerage_data['equity']:,.2f}")
            print(f"   Cash: ${brokerage_data['cash']:,.2f}")
            print(f"   Positions: {len(brokerage_positions)}")

    # Fetch paper account
    print("\n📊 Fetching PAPER ($5K) account...")
    paper_client = get_alpaca_client(paper=True)
    paper_data = None
    paper_positions = []

    if paper_client:
        paper_data = fetch_account_data(paper_client)
        paper_positions = fetch_positions(paper_client)
        if paper_data:
            paper_data["positions"] = paper_positions
            record_to_rag(paper_data, "paper_5k")
            print(f"   Equity: ${paper_data['equity']:,.2f}")
            print(f"   Cash: ${paper_data['cash']:,.2f}")
            print(f"   Positions: {len(paper_positions)}")

    # Update system state and performance log
    if brokerage_data or paper_data:
        print("\n📝 Updating local state files...")
        update_system_state(brokerage_data, paper_data)
        append_to_performance_log(brokerage_data, paper_data)

    print("\n" + "=" * 60)
    print("✅ ACCOUNT RECORDING COMPLETE")
    print("=" * 60)

    # Summary for RAG
    summary = {
        "recorded_at": datetime.now().isoformat(),
        "brokerage_equity": brokerage_data["equity"] if brokerage_data else None,
        "paper_equity": paper_data["equity"] if paper_data else None,
        "brokerage_positions": len(brokerage_positions),
        "paper_positions": len(paper_positions),
    }
    print(f"\nSummary: {json.dumps(summary)}")

    return 0 if (brokerage_data or paper_data) else 1


if __name__ == "__main__":
    sys.exit(main())
