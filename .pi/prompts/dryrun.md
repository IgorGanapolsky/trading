---
description: Check IV rank regime gate and compute next SPY put credit spread dry-run plan
---

# Trading Dry Run

Plan next SPY bull put credit opportunity:

1. Execute `.venv/bin/python scripts/pi_trading_bridge.py dry-run`
2. Check if IV rank proxy >= 30 and VIX <= 30.
3. If regime gate passes, display the selected short/long strike delta, credit, and wing width.
4. If blocked, state the exact reason (e.g., low IV rank filter).
