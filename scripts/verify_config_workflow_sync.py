#!/usr/bin/env python3
"""
Config-Workflow Sync Validator

but still running in workflows.

This script verifies that:
1. Disabled strategies in system_state.json have corresponding flags set to false in workflows
2. Removed strategies don't have code/workflows that reference them
3. Enabled strategies have their workflows actually enabled

Usage:
    python scripts/verify_config_workflow_sync.py
    python scripts/verify_config_workflow_sync.py --strict  # Fail on any mismatch
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Strategy to workflow mapping
STRATEGY_WORKFLOW_MAPPING = {
        "config_path": "strategies.tier5.enabled",
        "workflow_files": [
        ],
        "code_files": [
        ],
    },
    "options": {
        "config_path": "strategies.options.enabled",
        "workflow_vars": [],  # Options should always be enabled
        "workflow_files": ["options-trading.yml"],
        "code_files": ["scripts/execute_options_trade.py"],
    },
}


def load_system_state() -> dict:
    """Load system state configuration."""
    state_file = Path("data/system_state.json")
    if not state_file.exists():
        print("WARNING: data/system_state.json not found")
        return {}
    with open(state_file) as f:
        return json.load(f)


def get_nested_value(data: dict, path: str):
    """Get nested dictionary value by dot-separated path."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def parse_workflow_env_vars(workflow_path: Path) -> dict:
    """Extract environment variables from workflow file."""
    if not workflow_path.exists():
        return {}

    content = workflow_path.read_text()
    env_vars = {}

    pattern = r"(\w+):\s*['\"]?(\w+)['\"]?"
    for match in re.finditer(pattern, content):
        env_vars[match.group(1)] = match.group(2)

    return env_vars


def check_workflow_exists(workflow_name: str) -> bool:
    """Check if a workflow file exists."""
    workflow_path = Path(f".github/workflows/{workflow_name}")
    return workflow_path.exists()


def check_code_exists(code_path: str) -> bool:
    """Check if a code file exists."""
    return Path(code_path).exists()


def validate_strategy(strategy_name: str, mapping: dict, state: dict) -> list:
    """Validate a single strategy's config-workflow sync."""
    errors = []

    # Get enabled status from config
    enabled = get_nested_value(state, mapping["config_path"])

    if enabled is False:
        # Strategy is DISABLED - verify workflows reflect this

        # Check workflow env vars
        for workflow_file in [
            "daily-trading.yml",
            "combined-trading.yml",
        ]:
            workflow_path = Path(f".github/workflows/{workflow_file}")
            if workflow_path.exists():
                env_vars = parse_workflow_env_vars(workflow_path)
                for var in mapping["workflow_vars"]:
                    if var in env_vars and env_vars[var].lower() == "true":
                        errors.append(
                            f"MISMATCH: {strategy_name} disabled in config but "
                            f"{var}='true' in {workflow_file}"
                        )

        # Check that dedicated workflow files don't exist
        for wf in mapping.get("workflow_files", []):
            if check_workflow_exists(wf):
                errors.append(
                    f"MISMATCH: {strategy_name} disabled but workflow {wf} still exists"
                )

        # Check that strategy code files don't exist
        for code_file in mapping.get("code_files", []):
            if check_code_exists(code_file):
                errors.append(
                    f"MISMATCH: {strategy_name} disabled but code {code_file} still exists"
                )

    elif enabled is True:
        # Strategy is ENABLED - verify it can actually run

        # Check that at least one workflow file exists
        workflow_exists = any(
            check_workflow_exists(wf) for wf in mapping.get("workflow_files", [])
        )
        if mapping.get("workflow_files") and not workflow_exists:
            errors.append(
                f"MISMATCH: {strategy_name} enabled but no workflow files exist"
            )

        # Check that code files exist
        for code_file in mapping.get("code_files", []):
            if not check_code_exists(code_file):
                errors.append(
                    f"MISMATCH: {strategy_name} enabled but code {code_file} missing"
                )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Verify config-workflow sync")
    parser.add_argument(
        "--strict", action="store_true", help="Exit with error code on any mismatch"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("CONFIG-WORKFLOW SYNC VALIDATOR")
    print("=" * 60)
    print()

    state = load_system_state()
    all_errors = []

    for strategy_name, mapping in STRATEGY_WORKFLOW_MAPPING.items():
        print(f"Checking {strategy_name}...")
        errors = validate_strategy(strategy_name, mapping, state)

        if errors:
            for error in errors:
                print(f"  ❌ {error}")
            all_errors.extend(errors)
        else:
            enabled = get_nested_value(state, mapping["config_path"])
            status = "ENABLED" if enabled else "DISABLED"
            print(f"  ✅ {strategy_name}: config and workflow in sync ({status})")

    print()
    print("=" * 60)

    if all_errors:
        print(f"RESULT: {len(all_errors)} sync error(s) found")
        print()
        print("FIX: Ensure disabled strategies have:")
        print("  1. Workflow env vars set to 'false'")
        print("  2. Dedicated workflow files deleted")
        print("  3. Strategy code files deleted")
        print()
        if args.strict:
            sys.exit(1)
    else:
        print("RESULT: All strategies in sync ✅")

    return len(all_errors)


if __name__ == "__main__":
    main()
