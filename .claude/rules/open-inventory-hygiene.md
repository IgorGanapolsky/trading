# Open Inventory Hygiene (2026-07-22)

## Problem
SPY 2026-08-21 was journaled as a 1-lot IC (`IC_260821` P703-708/C776-781) but the
broker book had a 2-lot call vertical plus an orphan put vertical on the same expiry.
Validation could still open more risk on top of garbage, and exit/stop mapping failed.

## Prevention
1. `src/risk/open_inventory_audit.py` — structure audit (lot size, journal match, extras).
2. `scripts/audit_open_inventory.py` — CLI; exit 2 when unclean.
3. `TradeGateway` rejects new risk with `UNCLEAN_INVENTORY` until book matches journal.
4. Buy-to-close / sell-to-close of existing legs remain allowed so guardian can clean.

## Operator
```bash
.venv/bin/python scripts/audit_open_inventory.py
```
Do not open new validation ICs while this returns unclean.
Do not freehand-close outside the guardian workflow.
