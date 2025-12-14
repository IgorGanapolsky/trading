#!/usr/bin/env python3
"""
Go-Live Readiness Checker

Evaluates machine-checkable criteria to determine if the trading system
is ready to transition from paper trading to live trading.

Usage:
    python3 scripts/check_go_live_readiness.py           # Human-readable report
    python3 scripts/check_go_live_readiness.py --json    # Machine-readable JSON output

Exit codes:
    0: All criteria passed, ready for go-live
    1: One or more criteria failed, NOT ready for go-live
    2: Error in execution (missing files, invalid data, etc.)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class GoLiveReadinessChecker:
    """Checks if the trading system meets go-live criteria."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_path = project_root / "config" / "go_live_checklist.json"
        self.system_state_path = project_root / "data" / "system_state.json"
        self.anomaly_log_path = project_root / "data" / "anomaly_log.json"

        self.config: Optional[dict] = None
        self.system_state: Optional[dict] = None
        self.anomaly_log: Optional[dict] = None

    def load_data(self) -> bool:
        """Load all required data files. Returns True if successful."""
        try:
            # Load checklist config
            if not self.config_path.exists():
                print(f"ERROR: Config file not found: {self.config_path}", file=sys.stderr)
                return False

            with open(self.config_path) as f:
                self.config = json.load(f)

            # Load system state
            if not self.system_state_path.exists():
                print(
                    f"ERROR: System state file not found: {self.system_state_path}", file=sys.stderr
                )
                return False

            with open(self.system_state_path) as f:
                self.system_state = json.load(f)

            # Load anomaly log (optional - create empty if missing)
            if self.anomaly_log_path.exists():
                with open(self.anomaly_log_path) as f:
                    self.anomaly_log = json.load(f)
            else:
                # Default to zero anomalies if log doesn't exist
                self.anomaly_log = {"critical_count_7d": 0, "anomalies": []}

            return True

        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in data file: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"ERROR: Failed to load data files: {e}", file=sys.stderr)
            return False

    def get_nested_value(self, data: dict, path: str) -> Any:
        """
        Extract value from nested dictionary using dot notation.

        Example: "system_state.performance.win_rate"
                 -> data["performance"]["win_rate"]
        """
        # Remove "system_state." or "anomaly_log." prefix
        if path.startswith("system_state."):
            path = path.replace("system_state.", "")
            source = self.system_state
        elif path.startswith("anomaly_log."):
            path = path.replace("anomaly_log.", "")
            source = self.anomaly_log
        else:
            raise ValueError(f"Unknown data source in path: {path}")

        # Navigate nested dict
        parts = path.split(".")
        value = source
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value

    def evaluate_criterion(self, criterion: dict) -> tuple[bool, Any, str]:
        """
        Evaluate a single criterion.

        Returns:
            Tuple of (passed: bool, current_value: Any, message: str)
        """
        criterion_id = criterion["id"]
        description = criterion["description"]
        check_expr = criterion["check"]
        threshold = criterion["threshold"]
        value_source = criterion["current_value_source"]

        # Get current value from data
        current_value = self.get_nested_value(self.system_state or self.anomaly_log, value_source)

        if current_value is None:
            return False, None, f"Data not found: {value_source}"

        # Evaluate the check expression
        try:
            # Create safe evaluation context
            # Parse the check expression and evaluate
            if ">=" in check_expr:
                var_name, threshold_str = check_expr.split(">=")
                var_name = var_name.strip()
                expected_threshold = float(threshold_str.strip())
                passed = float(current_value) >= expected_threshold

            elif "<=" in check_expr:
                var_name, threshold_str = check_expr.split("<=")
                var_name = var_name.strip()
                expected_threshold = float(threshold_str.strip())
                passed = float(current_value) <= expected_threshold

            elif ">" in check_expr:
                var_name, threshold_str = check_expr.split(">")
                var_name = var_name.strip()
                expected_threshold = float(threshold_str.strip())
                passed = float(current_value) > expected_threshold

            elif "==" in check_expr:
                var_name, threshold_str = check_expr.split("==")
                var_name = var_name.strip()
                expected_threshold = float(threshold_str.strip())
                passed = float(current_value) == expected_threshold

            else:
                return False, current_value, f"Unsupported check expression: {check_expr}"

            if passed:
                message = f"✓ PASS: {description} ({current_value} meets threshold {threshold})"
            else:
                message = (
                    f"✗ FAIL: {description} ({current_value} does not meet threshold {threshold})"
                )

            return passed, current_value, message

        except Exception as e:
            return False, current_value, f"Error evaluating criterion: {e}"

    def check_readiness(self) -> dict[str, Any]:
        """
        Check all go-live criteria.

        Returns:
            Dict with detailed results for each criterion and overall status
        """
        if not self.config or not self.system_state:
            return {"error": "Data not loaded. Call load_data() first.", "ready_for_go_live": False}

        results = {
            "timestamp": datetime.now().isoformat(),
            "config_version": self.config.get("version", "unknown"),
            "system_state_updated": self.system_state.get("meta", {}).get(
                "last_updated", "unknown"
            ),
            "criteria_results": [],
            "summary": {"total_criteria": 0, "passed": 0, "failed": 0},
            "ready_for_go_live": False,
        }

        # Evaluate each criterion
        for criterion in self.config["criteria"]:
            passed, current_value, message = self.evaluate_criterion(criterion)

            results["criteria_results"].append(
                {
                    "id": criterion["id"],
                    "description": criterion["description"],
                    "threshold": criterion["threshold"],
                    "current_value": current_value,
                    "passed": passed,
                    "message": message,
                }
            )

            results["summary"]["total_criteria"] += 1
            if passed:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

        # Overall readiness
        results["ready_for_go_live"] = results["summary"]["failed"] == 0

        return results

    def print_human_readable_report(self, results: dict[str, Any]) -> None:
        """Print a human-readable report to stdout."""
        print("=" * 80)
        print("GO-LIVE READINESS REPORT")
        print("=" * 80)
        print(f"Generated: {results['timestamp']}")
        print(f"Config Version: {results['config_version']}")
        print(f"System State Last Updated: {results['system_state_updated']}")
        print()

        print("CRITERIA EVALUATION")
        print("-" * 80)

        for result in results["criteria_results"]:
            status_icon = "✓" if result["passed"] else "✗"
            status_text = "PASS" if result["passed"] else "FAIL"

            print(f"{status_icon} [{status_text}] {result['description']}")
            print(f"   Current: {result['current_value']}")
            print(f"   Threshold: {result['threshold']}")
            print()

        print("=" * 80)
        print("SUMMARY")
        print("-" * 80)
        print(f"Total Criteria: {results['summary']['total_criteria']}")
        print(f"Passed: {results['summary']['passed']}")
        print(f"Failed: {results['summary']['failed']}")
        print()

        if results["ready_for_go_live"]:
            print("✓ RESULT: READY FOR GO-LIVE")
            print("  All criteria have been met. The system is ready to transition")
            print("  from paper trading to live trading.")
        else:
            print("✗ RESULT: NOT READY FOR GO-LIVE")
            print("  One or more criteria have not been met. Continue paper trading")
            print("  until all criteria pass.")

        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check if trading system is ready for go-live",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/check_go_live_readiness.py          # Human-readable report
  python3 scripts/check_go_live_readiness.py --json   # JSON output for automation
        """,
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON for machine parsing"
    )

    args = parser.parse_args()

    # Determine project root (parent of scripts directory)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    # Create checker and load data
    checker = GoLiveReadinessChecker(project_root)

    if not checker.load_data():
        sys.exit(2)  # Error in execution

    # Check readiness
    results = checker.check_readiness()

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        checker.print_human_readable_report(results)

    # Exit with appropriate code
    if results["ready_for_go_live"]:
        sys.exit(0)  # All criteria passed
    else:
        sys.exit(1)  # One or more criteria failed


if __name__ == "__main__":
    main()
