# LL-264: Trade History Sync Bug Fix

**Date**: 2026-01-19
**Category**: Data Integrity, System Bug
**Severity**: CRITICAL

## The Bug

`sync_alpaca_state.py` was overwriting `data/system_state.json` WITHOUT the `trade_history` field. This caused ALL trade data to be lost on every sync.

**Evidence:**
```
Trade history recorded: 0
```
...despite having 6 open SPY positions.

## Root Cause

Two competing sync processes with different schemas:

| Script | trade_history | positions |
|--------|--------------|-----------|
| `sync_alpaca_state.py` | NO | YES |
| `sync-system-state.yml` | YES | YES |

The local script ran more frequently and overwrote the GitHub Actions sync data.

## The Fix (PR pending)

Added trade_history fetching to `sync_alpaca_state.py`:

1. Fetch closed orders from Alpaca API
2. Write to `state["trade_history"]`
3. Add `trades_loaded` count for monitoring
4. Preserve existing history if fetch fails (defensive)

## Why This Matters

This is EXACTLY how we lost the $100K account lessons:
- No trade recording
- No win/loss tracking
- Same mistakes repeated

Without trade_history, we cannot:
- Calculate real win rate
- Learn from past trades
- Validate strategy alignment

## Prevention

1. Single source of truth: `sync_alpaca_state.py` now handles trade_history
2. Schema validation: `trades_loaded` field enables monitoring
3. Defensive preservation: Never delete existing history if fetch fails

## Related Lessons

- LL-208: Why $5K Failed While $100K Succeeded
- LL-227: RAG System Gap Investigation
- LL-208: Why $5K Failed While $100K Succeeded

## Tags

`data-integrity`, `sync`, `trade-history`, `critical-fix`, `knowledge-capture`
