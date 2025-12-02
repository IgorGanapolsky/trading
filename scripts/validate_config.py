#!/usr/bin/env python3
"""Validate environment configuration with basic safety checks."""

from __future__ import annotations

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.config import load_config


def main() -> int:
    try:
        cfg = load_config()
        # Print minimal summary using correct attribute names
        print("Config OK:")
        print(f"  daily_investment={cfg.daily_investment}")
        print(f"  paper_trading={cfg.paper_trading}")
        print(f"  max_position_size={cfg.max_position_size}")
        return 0
    except Exception as exc:
        print(f"Config invalid: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
