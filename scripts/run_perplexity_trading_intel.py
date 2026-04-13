#!/usr/bin/env python3
"""Run the Perplexity trading intelligence loop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.analytics.perplexity_trading_intel import main

    main()


if __name__ == "__main__":
    _run()
