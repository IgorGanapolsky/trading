#!/usr/bin/env python3
"""
System Health Verification Framework

Prevents silent failures like the Dec 10-11 CI blockage that
stopped trading for 2 days without anyone noticing.

Usage:
    python scripts/verify_system_health.py
    python scripts/verify_system_health.py --json
    python scripts/verify_system_health.py --alert-on-failure
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def check_last_trade_date() -> tuple[bool, str]:
    """Check if trading has happened recently."""
    try:
        state_path = Path("data/system_state.json")
        if not state_path.exists():
            return False, "system_state.json not found"

        with open(state_path) as f:
            state = json.load(f)

        last_updated = state.get("meta", {}).get("last_updated")
        if not last_updated:
            return False, "No last_updated timestamp"

        last_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_since = (now - last_dt).days

        if days_since > 2:
            return False, f"Last update was {days_since} days ago ({last_updated})"
        return True, f"Last update: {last_updated} ({days_since} days ago)"
    except Exception as e:
        return False, f"Error checking last trade: {e}"


def check_ci_health() -> tuple[bool, str]:
    """Check if CI workflows are passing."""
    try:
        import requests

        resp = requests.get(
            "https://api.github.com/repos/IgorGanapolsky/trading/actions/workflows/daily-trading.yml/runs?per_page=5",
            timeout=10,
        )
        if resp.status_code != 200:
            return False, f"GitHub API error: {resp.status_code}"

        runs = resp.json().get("workflow_runs", [])
        if not runs:
            return False, "No workflow runs found"

        # Check last 5 runs
        failures = sum(1 for r in runs if r.get("conclusion") == "failure")
        sum(1 for r in runs if r.get("conclusion") == "success")

        if failures >= 3:
            return False, f"CI unhealthy: {failures}/5 recent runs failed"

        last_run = runs[0]
        return True, f"Last run: {last_run.get('conclusion')} at {last_run.get('created_at')}"
    except Exception as e:
        return False, f"Error checking CI: {e}"


def check_positions_exist() -> tuple[bool, str]:
    """Check if we have any positions."""
    try:
        state_path = Path("data/system_state.json")
        if not state_path.exists():
            return False, "system_state.json not found"

        with open(state_path) as f:
            state = json.load(f)

        positions_value = state.get("account", {}).get("positions_value", 0)
        if positions_value > 0:
            return True, f"Positions value: ${positions_value:,.2f}"
        return False, "No positions found"
    except Exception as e:
        return False, f"Error checking positions: {e}"


def check_rag_health() -> tuple[bool, str]:
    """Check if RAG system has documents."""
    try:
        rag_path = Path("data/rag/in_memory_store.json")
        if not rag_path.exists():
            return False, "RAG store not found"

        with open(rag_path) as f:
            data = json.load(f)

        doc_count = len(data.get("documents", []))
        if doc_count > 0:
            return True, f"RAG has {doc_count} documents"
        return False, "RAG store is empty"
    except Exception as e:
        return False, f"Error checking RAG: {e}"


def check_ml_models() -> tuple[bool, str]:
    """Check if ML models exist."""
    try:
        models_dir = Path("models/ml")
        if not models_dir.exists():
            return False, "models/ml directory not found"

        model_files = list(models_dir.glob("*.json")) + list(models_dir.glob("*.pt"))
        if model_files:
            return True, f"Found {len(model_files)} model files"
        return False, "No model files found"
    except Exception as e:
        return False, f"Error checking ML models: {e}"


def run_all_checks() -> dict:
    """Run all health checks and return results."""
    checks = {
        "last_trade": check_last_trade_date(),
        "ci_health": check_ci_health(),
        "positions": check_positions_exist(),
        "rag_health": check_rag_health(),
        "ml_models": check_ml_models(),
    }

    results = {}
    all_pass = True

    for name, (passed, message) in checks.items():
        results[name] = {
            "passed": passed,
            "message": message,
        }
        if not passed:
            all_pass = False

    results["overall"] = {
        "passed": all_pass,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Verify trading system health")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--alert-on-failure", action="store_true", help="Exit 1 if any check fails")
    args = parser.parse_args()

    results = run_all_checks()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 50)
        print("TRADING SYSTEM HEALTH CHECK")
        print("=" * 50)

        for name, result in results.items():
            if name == "overall":
                continue
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {name}: {result['message']}")

        print("-" * 50)
        overall = results["overall"]
        if overall["passed"]:
            print("✅ ALL CHECKS PASSED")
        else:
            print("❌ SOME CHECKS FAILED - INVESTIGATE IMMEDIATELY")
        print(f"Timestamp: {overall['timestamp']}")

    if args.alert_on_failure and not results["overall"]["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
