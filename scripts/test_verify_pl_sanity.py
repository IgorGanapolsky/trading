#!/usr/bin/env python3
"""
Test script for verify_pl_sanity.py

Creates various scenarios to verify all alert conditions work correctly.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# Test scenarios
DATA_DIR = Path("data")
PERF_LOG_FILE = DATA_DIR / "performance_log.json"
PERF_LOG_BACKUP = DATA_DIR / "performance_log.json.backup"


def backup_performance_log():
    """Backup existing performance log if it exists."""
    if PERF_LOG_FILE.exists():
        PERF_LOG_FILE.rename(PERF_LOG_BACKUP)
        print(f"✅ Backed up existing performance log to {PERF_LOG_BACKUP}")


def restore_performance_log():
    """Restore original performance log."""
    if PERF_LOG_BACKUP.exists():
        PERF_LOG_BACKUP.rename(PERF_LOG_FILE)
        print("✅ Restored original performance log")
    elif PERF_LOG_FILE.exists():
        PERF_LOG_FILE.unlink()
        print("✅ Cleaned up test performance log")


def create_test_log(scenario: str) -> list[dict]:
    """Create test performance log for different scenarios."""
    base_date = datetime.now() - timedelta(days=7)

    if scenario == "stuck_equity":
        # Equity unchanged for 5 trading days
        return [
            {
                "date": (base_date + timedelta(days=i)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=i)).isoformat(),
                "equity": 100000.00,  # Stuck at exactly same value
                "pl": 0.0,
            }
            for i in range(5)
        ]

    elif scenario == "zero_pl":
        # P/L exactly 0 for multiple days
        return [
            {
                "date": (base_date + timedelta(days=i)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=i)).isoformat(),
                "equity": 100000.00 + i * 0.5,  # Tiny changes
                "pl": 0.0,  # But P/L stays at 0
            }
            for i in range(5)
        ]

    elif scenario == "anomalous_change":
        # Large daily P/L change (>5%)
        return [
            {
                "date": (base_date + timedelta(days=0)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=0)).isoformat(),
                "equity": 100000.00,
                "pl": 0.0,
            },
            {
                "date": (base_date + timedelta(days=1)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=1)).isoformat(),
                "equity": 107000.00,  # 7% jump - anomalous
                "pl": 7000.0,
            },
        ]

    elif scenario == "drawdown":
        # Equity drops >10% from peak
        return [
            {
                "date": (base_date + timedelta(days=0)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=0)).isoformat(),
                "equity": 110000.00,  # Peak
                "pl": 10000.0,
            },
            {
                "date": (base_date + timedelta(days=1)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=1)).isoformat(),
                "equity": 105000.00,
                "pl": 5000.0,
            },
            {
                "date": (base_date + timedelta(days=2)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=2)).isoformat(),
                "equity": 98000.00,  # 10.9% drawdown from peak
                "pl": -2000.0,
            },
        ]

    elif scenario == "healthy":
        # Normal healthy progression
        return [
            {
                "date": (base_date + timedelta(days=i)).date().isoformat(),
                "timestamp": (base_date + timedelta(days=i)).isoformat(),
                "equity": 100000.00 + i * 50 + i * i * 2,  # Natural variation
                "pl": i * 50 + i * i * 2,
            }
            for i in range(5)
        ]

    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def run_test_scenario(scenario: str):
    """Run a test scenario and check results."""
    print(f"\n{'=' * 70}")
    print(f"TEST SCENARIO: {scenario.upper()}")
    print(f"{'=' * 70}")

    # Create test log
    test_data = create_test_log(scenario)
    DATA_DIR.mkdir(exist_ok=True)
    with open(PERF_LOG_FILE, "w") as f:
        json.dump(test_data, f, indent=2)

    print(f"Created test log with {len(test_data)} entries")

    # Run verification
    import subprocess

    result = subprocess.run(
        ["python3", "scripts/verify_pl_sanity.py"],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode


def main():
    """Run all test scenarios."""
    print("P/L Sanity Check - Test Suite")
    print("=" * 70)

    # Backup existing log
    backup_performance_log()

    try:
        scenarios = [
            "healthy",
            "stuck_equity",
            "zero_pl",
            "anomalous_change",
            "drawdown",
        ]

        results = {}

        for scenario in scenarios:
            exit_code = run_test_scenario(scenario)
            results[scenario] = exit_code

        # Summary
        print(f"\n{'=' * 70}")
        print("TEST SUMMARY")
        print(f"{'=' * 70}")

        for scenario, exit_code in results.items():
            status = (
                "✅ PASS"
                if (
                    (scenario == "healthy" and exit_code == 0)
                    or (scenario != "healthy" and exit_code == 1)
                )
                else "❌ FAIL"
            )

            print(f"{scenario:20s} -> exit code {exit_code} -> {status}")

        print(f"\n{'=' * 70}")

    finally:
        # Restore original log
        restore_performance_log()


if __name__ == "__main__":
    main()
