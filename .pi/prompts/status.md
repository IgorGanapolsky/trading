---
description: Check system health, broker account balances, and open option positions
---

# Trading Status

Run deterministic trading status checks:

1. Execute `.venv/bin/python scripts/pi_trading_bridge.py status`
2. Audit open option inventory to ensure all legs match journal records.
3. Report current paper account equity, buying power, and active positions.
