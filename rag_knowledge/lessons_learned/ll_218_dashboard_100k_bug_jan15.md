# LL-218: Dashboard Showing Wrong $100K Balance

**ID**: LL-218
**Date**: January 15, 2026
**Category**: Bug Fix / Data Sync
**Severity**: HIGH
**Source**: CEO Crisis Alert

## The Bug

Progress Dashboard showed paper account as **$100,000** when actual balance was **$4,959.26**.

## Root Cause

Key name mismatch between data sync and dashboard display:

| Component | Key Used | Expected Key |
|-----------|----------|--------------|
| `sync_alpaca_state.py` | `paper_account.equity` | ✅ |
| `generate_world_class_dashboard_enhanced.py` | `paper_account.current_equity` | ❌ Missing |

When `current_equity` was missing, dashboard defaulted to `100000.0`.

```python
# Dashboard code (line 60-61):
paper_equity = paper_account.get("current_equity", 100000.0)  # Defaults to 100K!
paper_starting = paper_account.get("starting_balance", 100000.0)
```

## The Fix

**sync_alpaca_state.py** - Added code to write BOTH keys for paper accounts:
- `paper_account.equity` (original)
- `paper_account.current_equity` (what dashboard expects)

## Prevention

1. Use consistent key names across all scripts
2. Validate dashboard data against Alpaca API after each sync
3. Add unit tests for key name consistency

## Impact

- CEO saw wrong portfolio value ($100K vs $4,959)
- Caused confusion about trading system performance
- Dashboard was lying for unknown duration

## Code Locations

- `scripts/sync_alpaca_state.py:151-166` - Fix applied
- `scripts/generate_world_class_dashboard_enhanced.py:60-61` - Where default was used
