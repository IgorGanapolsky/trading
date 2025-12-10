#!/usr/bin/env python3
"""
Reset Circuit Breaker State
"""

import sys
from pathlib import Path


def main():
    state_file = Path("data/circuit_breaker_state.json")
    if state_file.exists():
        print(f"Removing {state_file}...")
        state_file.unlink()
        print("✅ Circuit breaker state reset.")
    else:
        print("ℹ️  Circuit breaker state file not found (already reset).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
