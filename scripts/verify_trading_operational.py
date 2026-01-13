#!/usr/bin/env python3
"""
Verify Trading System is Operational

This script performs a comprehensive check of the trading system
to ensure all components are working and ready for execution.

Created: 2026-01-13
Author: Claude CTO
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_alpaca_connectivity():
    """Verify Alpaca API connection."""
    print("=" * 60)
    print("1. ALPACA API CONNECTIVITY")
    print("=" * 60)

    api_key = os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_PAPER_TRADING_5K_API_SECRET")

    if not api_key or not secret_key:
        print("❌ FAILED: API keys not configured")
        return False

    try:
        from alpaca.trading.client import TradingClient

        paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
        client = TradingClient(api_key, secret_key, paper=paper)

        account = client.get_account()
        print(f"✅ Connected to Alpaca ({'paper' if paper else 'live'})")
        print(f"   Equity: ${float(account.equity):,.2f}")
        print(f"   Cash: ${float(account.cash):,.2f}")
        print(f"   Buying Power: ${float(account.buying_power):,.2f}")
        print(f"   Options Buying Power: ${float(getattr(account, 'options_buying_power', 0) or 0):,.2f}")

        positions = client.get_all_positions()
        print(f"   Open Positions: {len(positions)}")

        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False


def check_recent_trades():
    """Check if trades have been executed recently."""
    print("\n" + "=" * 60)
    print("2. RECENT TRADE ACTIVITY")
    print("=" * 60)

    # Check local trade files
    data_dir = Path(__file__).parent.parent / "data"
    trade_files = list(data_dir.glob("trades_*.json"))

    if not trade_files:
        print("⚠️ WARNING: No trade files found")
        return False

    # Find most recent trade file
    latest_file = max(trade_files, key=lambda f: f.stat().st_mtime)
    print(f"   Latest trade file: {latest_file.name}")

    try:
        with open(latest_file) as f:
            trades = json.load(f)
        print(f"   Trades in file: {len(trades)}")

        # Check age of trades
        file_date = latest_file.name.replace("trades_", "").replace(".json", "")
        trade_date = datetime.strptime(file_date, "%Y-%m-%d")
        age_days = (datetime.now() - trade_date).days

        if age_days > 3:
            print(f"❌ WARNING: Last trade was {age_days} days ago!")
            print("   System may be in zombie mode (running but not trading)")
            return False
        else:
            print(f"✅ Last trade: {age_days} days ago")
            return True
    except Exception as e:
        print(f"❌ Error reading trade file: {e}")
        return False


def check_workflow_health():
    """Check if workflows are running successfully."""
    print("\n" + "=" * 60)
    print("3. WORKFLOW HEALTH")
    print("=" * 60)

    # Check system state for workflow tracking
    state_file = Path(__file__).parent.parent / "data" / "system_state.json"

    if not state_file.exists():
        print("⚠️ WARNING: system_state.json not found")
        return False

    try:
        with open(state_file) as f:
            state = json.load(f)

        last_updated = state.get("meta", {}).get("last_updated", "unknown")
        print(f"   System state last updated: {last_updated}")

        # Check for sync mode issues
        sync_mode = state.get("meta", {}).get("sync_mode", "")
        if "skipped" in sync_mode.lower():
            print(f"❌ WARNING: Sync mode = '{sync_mode}'")
            print("   This indicates API key configuration issues")
            return False

        print("✅ System state looks healthy")
        return True
    except Exception as e:
        print(f"❌ Error reading system state: {e}")
        return False


def check_rag_integration():
    """Check RAG database integration."""
    print("\n" + "=" * 60)
    print("4. RAG DATABASE INTEGRATION")
    print("=" * 60)

    rag_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"

    if not rag_dir.exists():
        print("⚠️ WARNING: RAG lessons directory not found")
        return False

    lessons = list(rag_dir.glob("*.md"))
    print(f"   Local RAG lessons: {len(lessons)}")

    if lessons:
        latest = max(lessons, key=lambda f: f.stat().st_mtime)
        print(f"   Latest lesson: {latest.name}")

    # Check for Vertex AI RAG connection
    gcp_key = os.getenv("GCP_SA_KEY") or os.getenv("GOOGLE_API_KEY")
    if gcp_key:
        print("✅ Vertex AI credentials configured")
        return True
    else:
        print("⚠️ No Vertex AI credentials - using local RAG only")
        return True  # Local RAG still works


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("TRADING SYSTEM OPERATIONAL VERIFICATION")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "alpaca": check_alpaca_connectivity(),
        "trades": check_recent_trades(),
        "workflow": check_workflow_health(),
        "rag": check_rag_integration(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = all(results.values())
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check}: {status}")

    print("=" * 60)

    if all_passed:
        print("✅ ALL CHECKS PASSED - System is operational")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Action required")
        return 1


if __name__ == "__main__":
    sys.exit(main())
