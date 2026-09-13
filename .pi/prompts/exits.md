---
description: Sweep and evaluate 25% take-profit, stop-loss, and 7-DTE time-stop exits
---

# Manage Exits

Manage active position exits:

1. Execute `.venv/bin/python scripts/pi_trading_bridge.py manage-exits`
2. Check marks for all open SPY put credit positions against 25% profit target and 2.0x stop loss.
3. Report any triggered exits or remaining time to expiry.
