#!/usr/bin/env python3
"""
Strategy Integration Verifier

Ensures all active strategies in system_state.json are actually
integrated and called in autonomous_trader.py.

This prevents the ll_012 scenario where strategy code exists
but is never executed.

Usage:
    python3 scripts/verify_strategy_integration.py

Returns:
    Exit code 0: All strategies integrated
    Exit code 1: Missing strategy integrations detected
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Map strategy tiers to expected function patterns
STRATEGY_EXECUTION_PATTERNS = {
    "tier1": ["orchestrator.run", "TradingOrchestrator"],  # Core momentum
    "tier2": ["orchestrator.run", "TradingOrchestrator"],  # Part of core
    "tier3": ["treasury", "bond"],  # Treasury ladder
    "tier4": ["options", "theta"],  # Options strategies
    "tier5": ["crypto", "execute_crypto"],  # Crypto trading
    "tier6": ["prediction", "execute_prediction", "kalshi"],  # Prediction markets
    "tier7": ["reit", "execute_reit"],  # REIT strategy
    "tier8": ["precious_metals", "execute_precious_metals", "gld", "slv"],  # Precious metals
}


def load_system_state() -> dict:
    """Load system_state.json."""
    path = Path("data/system_state.json")
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_autonomous_trader() -> str:
    """Load autonomous_trader.py source code."""
    path = Path("scripts/autonomous_trader.py")
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    with open(path) as f:
        return f.read()


def get_active_strategies(state: dict) -> list[tuple[str, dict]]:
    """Get list of active strategies from system_state."""
    strategies = state.get("strategies", {})
    active = []
    for tier, config in strategies.items():
        # Strategy is active if status is "active" or enabled is True
        is_active = config.get("status") == "active" or config.get("enabled", False)
        if is_active:
            active.append((tier, config))
    return active


def verify_strategy_integrated(tier: str, config: dict, trader_code: str) -> tuple[bool, str]:
    """Verify a strategy is integrated in autonomous_trader.py."""
    patterns = STRATEGY_EXECUTION_PATTERNS.get(tier, [])

    # If no patterns defined, use the tier name as pattern
    if not patterns:
        patterns = [tier.lower()]

    # Check if any pattern matches
    code_lower = trader_code.lower()
    for pattern in patterns:
        if pattern.lower() in code_lower:
            return True, f"Found '{pattern}' in autonomous_trader.py"

    # Strategy name from config
    name = config.get("name", tier)

    return False, f"Strategy '{tier}' ({name}) not found in autonomous_trader.py"


def verify_all_strategies() -> tuple[bool, list[str]]:
    """Verify all active strategies are integrated."""
    state = load_system_state()
    trader_code = load_autonomous_trader()
    active = get_active_strategies(state)

    print("=" * 60)
    print("STRATEGY INTEGRATION VERIFICATION")
    print("=" * 60)
    print(f"\nFound {len(active)} active strategies in system_state.json\n")

    errors = []
    for tier, config in active:
        name = config.get("name", tier)
        integrated, msg = verify_strategy_integrated(tier, config, trader_code)

        if integrated:
            print(f"  [OK] {tier}: {name}")
        else:
            print(f"  [MISSING] {tier}: {name}")
            errors.append(msg)

    print()

    if errors:
        print("=" * 60)
        print("ERRORS FOUND:")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        print()
        print("FIX: Add execute_{tier}_trading() to autonomous_trader.py")
        print("REF: See ll_012_reit_strategy_not_activated_dec12.md")
        return False, errors

    print("=" * 60)
    print("ALL STRATEGIES INTEGRATED")
    print("=" * 60)
    return True, []


def verify_strategy_registry() -> tuple[bool, list[str]]:
    """Verify all strategies have registry entries."""
    path = Path("config/strategy_registry.json")
    if not path.exists():
        return True, []  # No registry required

    with open(path) as f:
        registry = json.load(f)

    state = load_system_state()
    active = get_active_strategies(state)

    errors = []
    registered_names = set(registry.get("strategies", {}).keys())

    # Check if active strategies have some form of registry entry
    # This is a soft check since registry names may differ from tier names

    print("\nStrategy Registry Check:")
    for tier, config in active:
        name = config.get("name", tier)
        # Look for any registry entry that might match
        found = False
        for reg_name in registered_names:
            if tier.lower() in reg_name.lower() or reg_name.lower() in name.lower():
                found = True
                break
        if found:
            print(f"  [OK] {tier} has registry entry")
        else:
            print(f"  [WARN] {tier} may not have registry entry")
            # Don't fail on this - it's a soft check

    return True, errors


def main() -> int:
    """Main entry point."""
    success, errors = verify_all_strategies()

    # Also check registry (soft check)
    verify_strategy_registry()

    if not success:
        print("\n" + "!" * 60)
        print("VERIFICATION FAILED - SEE ERRORS ABOVE")
        print("!" * 60)
        return 1

    print("\nVerification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
