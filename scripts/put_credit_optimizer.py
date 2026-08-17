#!/usr/bin/env python3
"""CLI wrapper for put credit optimization.

Usage:
    python scripts/put_credit_optimizer.py --candidates data/put_credit_candidates.json --capital 10000 --json
"""

import sys
from pathlib import Path

# Add src to path - must be before other local imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk.put_credit_optimizer import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
