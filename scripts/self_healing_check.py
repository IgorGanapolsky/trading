#!/usr/bin/env python3
"""
Self-Healing Health Check Script.

Runs all health checks and attempts auto-fix for common issues.

Usage:
    python3 scripts/self_healing_check.py           # Run checks only
    python3 scripts/self_healing_check.py --heal    # Run checks and auto-fix
    python3 scripts/self_healing_check.py --json    # Output JSON for CI

Created: Jan 19, 2026 (LL-249: Resilience and Self-Healing)
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.resilience.self_healer import SelfHealer, HealthStatus


def main():
    parser = argparse.ArgumentParser(description="Self-healing health check")
    parser.add_argument("--heal", action="store_true", help="Attempt auto-fix")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fail-on-unhealthy", action="store_true", help="Exit 1 if unhealthy")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    healer = SelfHealer(project_root)

    print("Running health checks...")
    healer.run_all_checks()

    if args.heal:
        print("\nAttempting auto-fix...")
        healed = healer.heal()
        if healed:
            print(f"Auto-fixed {len(healed)} issues")

    summary = healer.get_summary()

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(healer.get_report())

    # Exit code for CI
    if args.fail_on_unhealthy:
        if summary["overall_status"] == "unhealthy":
            sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
