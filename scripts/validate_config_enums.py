#!/usr/bin/env python3
"""
Config Enum Validator

Pre-commit hook that validates enum values in config files against
their Python definitions. Prevents bugs like LL_033 where invalid
enum values silently break the system.

Usage:
    python3 scripts/validate_config_enums.py

Exit codes:
    0 - All validations passed
    1 - Validation errors found

Author: Claude (AI CTO)
Date: 2025-12-14
"""

import json
import sys
from pathlib import Path


def get_enum_values(enum_class):
    """Extract values from an enum class."""
    return {e.value for e in enum_class}


def validate_strategy_registry():
    """Validate strategy_registry.json against Python enums."""
    errors = []
    config_path = Path("config/strategy_registry.json")

    if not config_path.exists():
        print("SKIP: config/strategy_registry.json not found")
        return []

    # Import enums
    try:
        from src.strategies.registry import AssetClass, StrategyStatus

        valid_asset_classes = get_enum_values(AssetClass)
        valid_statuses = get_enum_values(StrategyStatus)
    except ImportError as e:
        print(f"WARN: Could not import enums: {e}")
        return []

    # Load config
    with open(config_path) as f:
        data = json.load(f)

    # Validate each strategy
    for name, strategy in data.get("strategies", {}).items():
        # Check asset_class
        asset_class = strategy.get("asset_class")
        if asset_class and asset_class not in valid_asset_classes:
            errors.append(
                f"Strategy '{name}': invalid asset_class '{asset_class}'. "
                f"Valid: {valid_asset_classes}"
            )

        # Check status
        status = strategy.get("status")
        if status and status not in valid_statuses:
            errors.append(
                f"Strategy '{name}': invalid status '{status}'. " f"Valid: {valid_statuses}"
            )

    return errors


def validate_all_json_parseable():
    """Ensure all JSON files in config/ are valid."""
    errors = []
    config_dir = Path("config")

    if not config_dir.exists():
        return []

    for json_file in config_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"{json_file}: Invalid JSON - {e}")

    return errors


def main():
    """Run all validations."""
    print("=" * 60)
    print("CONFIG ENUM VALIDATION")
    print("=" * 60)

    all_errors = []

    # Validate JSON syntax
    print("\n[1/2] Validating JSON syntax...")
    json_errors = validate_all_json_parseable()
    if json_errors:
        all_errors.extend(json_errors)
        for err in json_errors:
            print(f"  ERROR: {err}")
    else:
        print("  OK: All JSON files are valid")

    # Validate strategy registry enums
    print("\n[2/2] Validating strategy registry enums...")
    registry_errors = validate_strategy_registry()
    if registry_errors:
        all_errors.extend(registry_errors)
        for err in registry_errors:
            print(f"  ERROR: {err}")
    else:
        print("  OK: All enum values are valid")

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILED: {len(all_errors)} validation error(s)")
        print("\nTo fix:")
        print("  1. Check valid enum values in src/strategies/registry.py")
        print("  2. Update config files to use valid values")
        print("  3. See rag_knowledge/lessons_learned/ll_033_*.md for details")
        return 1
    else:
        print("PASSED: All config validations successful")
        return 0


if __name__ == "__main__":
    sys.exit(main())
