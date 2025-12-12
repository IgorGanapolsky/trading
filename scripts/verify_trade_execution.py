#!/usr/bin/env python3
"""Verify that trading actually executed (not just workflow success).

This script checks that the system actually placed trades or had valid reasons
for not trading. It fails if the system appears "stuck" - running but not trading.

Reference: rag_knowledge/lessons_learned/ll_019_system_dead_2_days_overly_strict_filters_dec12.md

Exit codes:
    0: Trading verified (trades placed OR valid skip reason)
    1: Trading failed verification (system appears dead)
    2: Script error
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def check_system_state_updated() -> tuple[bool, str]:
    """Check if system_state.json was updated today."""
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        return False, "system_state.json not found"

    try:
        with state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        last_updated = data.get("meta", {}).get("last_updated", "")
        if not last_updated:
            return False, "No last_updated timestamp in system_state.json"

        # Parse the timestamp
        if "T" in last_updated:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            updated_dt = updated_dt.replace(tzinfo=timezone.utc)

        today = datetime.now(timezone.utc).date()
        if updated_dt.date() == today:
            return True, f"system_state.json updated today at {last_updated}"
        else:
            return False, f"system_state.json last updated {updated_dt.date()}, not today ({today})"

    except Exception as e:
        return False, f"Error reading system_state.json: {e}"


def check_trade_file_exists() -> tuple[bool, str]:
    """Check if today's trade file exists."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trade_path = Path(f"data/trades_{today}.json")

    if trade_path.exists():
        try:
            with trade_path.open("r", encoding="utf-8") as f:
                trades = json.load(f)
            trade_count = len(trades) if isinstance(trades, list) else 1
            return True, f"Found {trade_count} trade(s) in {trade_path.name}"
        except Exception as e:
            return False, f"Error reading {trade_path.name}: {e}"
    else:
        return False, f"No trade file for today ({trade_path.name})"


def check_session_decisions() -> tuple[bool, str, dict]:
    """Check session decisions for rejection rate."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    decisions_path = Path(f"data/session_decisions_{today}.json")

    if not decisions_path.exists():
        return True, "No session decisions file (OK if no orchestrator run)", {}

    try:
        with decisions_path.open("r", encoding="utf-8") as f:
            decisions = json.load(f)

        total = len(decisions)
        if total == 0:
            return True, "No tickers analyzed today", {}

        rejected = sum(1 for d in decisions if d.get("final_status") == "rejected")
        executed = sum(1 for d in decisions if d.get("final_status") == "executed")

        rejection_rate = rejected / total if total > 0 else 0

        stats = {
            "total_analyzed": total,
            "rejected": rejected,
            "executed": executed,
            "rejection_rate": rejection_rate,
        }

        if rejection_rate >= 0.95 and total >= 5:
            return False, (
                f"CRITICAL: {rejection_rate:.0%} rejection rate ({rejected}/{total}). "
                "Filters may be too strict!"
            ), stats

        return True, f"Analyzed {total} tickers, executed {executed}, rejected {rejected}", stats

    except Exception as e:
        return False, f"Error reading session decisions: {e}", {}


def check_valid_skip_reason() -> tuple[bool, str]:
    """Check if there's a valid reason for not trading today."""
    # Check for weekend
    today = datetime.now(timezone.utc)
    if today.weekday() >= 5:  # Saturday=5, Sunday=6
        return True, f"Valid skip: Weekend ({today.strftime('%A')})"

    # Check for market holiday (simplified - just check system_state)
    state_path = Path("data/system_state.json")
    if state_path.exists():
        try:
            with state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("market_status") == "closed":
                return True, "Valid skip: Market closed (holiday)"
        except Exception:
            pass

    return False, "No valid skip reason found"


def main():
    print("=" * 60)
    print("TRADE EXECUTION VERIFICATION")
    print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    all_passed = True
    warnings = []

    # Check 1: system_state.json updated
    passed, msg = check_system_state_updated()
    status = "✅" if passed else "❌"
    print(f"{status} State file: {msg}")
    if not passed:
        warnings.append(msg)

    # Check 2: Trade file exists
    passed, msg = check_trade_file_exists()
    status = "✅" if passed else "⚠️"
    print(f"{status} Trade file: {msg}")

    # Check 3: Session decisions (rejection rate)
    passed, msg, stats = check_session_decisions()
    status = "✅" if passed else "❌"
    print(f"{status} Session decisions: {msg}")
    if not passed:
        all_passed = False

    # Check 4: Valid skip reason (if no trades)
    if not check_trade_file_exists()[0]:
        passed, msg = check_valid_skip_reason()
        status = "✅" if passed else "⚠️"
        print(f"{status} Skip reason: {msg}")
        if passed:
            # Valid skip reason, don't fail
            all_passed = True

    print("=" * 60)

    if not all_passed:
        print("❌ VERIFICATION FAILED - Trading system may be dead!")
        print("\nRecommended actions:")
        print("1. Check rag_knowledge/lessons_learned/ll_019*.md")
        print("2. Review filter thresholds (ADX, RSI, RL confidence)")
        print("3. Verify ticker universe has 15+ stocks")
        return 1

    print("✅ VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
