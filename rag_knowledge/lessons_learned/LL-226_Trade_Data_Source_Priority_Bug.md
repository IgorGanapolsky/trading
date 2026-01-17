# LL-226: Trade Data Source Priority Bug - Webhook Missing Alpaca Data

**Date**: January 16, 2026
**Severity**: HIGH
**Category**: Integration Bug
**Status**: FIXED

## Summary

The Dialogflow webhook was showing `trades_loaded=0` despite having 38 trades in `system_state.json`. Root cause: incorrect data source priority order.

## The Bug

### Data Flow Mismatch

| Component | Writes To | Source |
|-----------|-----------|--------|
| `sync-system-state.yml` | `data/system_state.json` → `trade_history` | Alpaca API ✓ |
| `trade_sync.py` | `data/trades_{date}.json` | Local code calls |
| `dialogflow_webhook.py` | Reads from | `trades_*.json` FIRST, then `system_state.json` |

### The Problem

1. On **Cloud Run**, the webhook has no access to local `trades_*.json` files
2. The `query_trades()` function checked `trades_*.json` FIRST
3. Found nothing (files don't exist on Cloud Run)
4. Only then fell back to `system_state.json` via GitHub API
5. But the fallback logic was inside the `if not trades:` block, so it worked - BUT the logging said "local_json" as source

### Why It Appeared Broken

The `/health` endpoint showed `trade_history_source: "local_json"` which was misleading. The actual data came from GitHub API → `system_state.json`, but the hardcoded string said "local_json".

## The Fix

**Reversed the priority order in `query_trades()`:**

### Before (v3.8.0)
```python
# First try trades_*.json files
for trades_file in data_dir.glob("trades_*.json"):
    # ... load local files
    
# If no local trades, fetch from GitHub API
if not trades:
    # ... fetch system_state.json
```

### After (v3.9.0)
```python
# PRIORITY 1: system_state.json - source of truth from Alpaca
# Try local first, then GitHub API
if state_path.exists():
    # ... load local system_state.json
if not state:
    # ... fetch from GitHub API
    
# Extract trade_history from system_state.json
if state:
    trade_history = state.get("trade_history", [])
    # ... process trades

# PRIORITY 2: Fallback to trades_*.json (legacy)
if not trades:
    # ... load from trades_*.json files
```

## Key Insight

**`system_state.json` is the source of truth** because:
- It's synced directly from Alpaca API via `sync-system-state.yml` workflow
- It contains the `trade_history` array with all filled orders
- It's committed to Git and accessible via GitHub API from anywhere

**`trades_*.json` files are redundant** because:
- Written by `trade_sync.py` during local execution
- Not synced to Cloud Run
- Not the authoritative source

## Prevention

1. **Single source of truth**: Use Alpaca API data (via `system_state.json`) as primary
2. **Consistent logging**: Update `trade_history_source` to reflect actual source
3. **Cloud-first thinking**: Always consider what data is available on Cloud Run vs local

## Related Files

- `src/agents/dialogflow_webhook.py` - Fixed
- `src/observability/trade_sync.py` - Legacy, consider deprecating
- `.github/workflows/sync-system-state.yml` - Source of truth sync
- `data/system_state.json` - Authoritative trade data

## Verification

After deployment, check:
```bash
curl https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app/health
# Should show: "trade_history_source": "system_state.json (Alpaca)"
# Should show: "trades_loaded": 38 (or current count)
```

## Lesson

**When debugging "missing data" bugs:**
1. Trace the full data flow from source to consumer
2. Check what environment the consumer runs in (local vs cloud)
3. Verify the actual source being used, not just what the code says
