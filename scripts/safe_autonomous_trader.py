#!/usr/bin/env python3
"""Safe wrapper for autonomous_trader that catches import errors."""

import os
import sys
import traceback

# Ensure logs directory
os.makedirs("logs", exist_ok=True)


def safe_run():
    """Import and run the main module with full error capture."""
    try:
        # Try importing the main module - this is where errors usually happen
        print("Importing autonomous_trader module...", flush=True)
        from scripts import autonomous_trader_core as trader

        print("Import successful, running main()...", flush=True)
        trader.main()
    except SystemExit:
        # Preserve exit codes
        raise
    except BaseException as e:
        tb = traceback.format_exc()

        # GHA annotations for visibility
        print("=" * 80, flush=True)
        print("::error::TRADING SCRIPT FAILED", flush=True)
        print(f"::error::Exception: {type(e).__name__}: {str(e)[:300]}", flush=True)

        # Print traceback as annotations
        for line in tb.split("\n"):
            if line.strip():
                print(f"::error::{line}", flush=True)

        # Write to file
        try:
            with open("logs/trading_crash.log", "w") as f:
                f.write(f"Exception: {type(e).__name__}: {e}\n\n{tb}")
        except:
            pass

        sys.exit(2)


if __name__ == "__main__":
    safe_run()
