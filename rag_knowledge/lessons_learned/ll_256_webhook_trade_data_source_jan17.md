# LL-256: Webhook Trade Data Source Mismatch (Jan 17, 2026)

## Severity: HIGH

## Summary
The Dialogflow webhook was showing `trades_loaded=0` on Cloud Run because it looked for local `trades_*.json` files first, but on Cloud Run these files don't exist. The actual Alpaca trade data was being synced to `system_state.json -> trade_history` by the GitHub Actions workflow.

## Root Cause
**Data flow mismatch between sync and read paths:**

| Component | Writes To | Environment |
|-----------|-----------|-------------|
| `sync-system-state.yml` workflow | `data/system_state.json -> trade_history` | GitHub Actions |
| `trade_sync.py` | `data/trades_{date}.json` | Local/CI |
| `dialogflow_webhook.py` (BROKEN) | Reads `trades_*.json` first | Cloud Run (no local files!) |

The webhook tried to read `trades_*.json` first, which ONLY exists locally. On Cloud Run, it fell back to GitHub API, but by then the logic was already confused.

## Fix Applied
Changed `query_trades()` in `dialogflow_webhook.py` v3.9.0 to:
1. Check `system_state.json` FIRST (the Alpaca source of truth synced via workflow)
2. Fall back to `trades_*.json` only for legacy/local development

## Verification
- Before: `/health` endpoint showed `trades_loaded: 0`
- After: `/health` endpoint shows `trades_loaded: 38` (actual Alpaca trades)

## Lessons
1. **Single source of truth**: When data is synced from an external API (Alpaca), ALL consumers should read from the same synced location
2. **Cloud vs Local**: Code that works locally may fail on Cloud Run due to missing files - always check the Cloud Run environment
3. **Debug with `/health`**: The `/health` endpoint immediately revealed `trades_loaded=0` which pointed to the data source issue

## Prevention
- Add explicit logging that shows which data source is being used
- Add `source` metadata to each trade record to trace data origin
- Test webhook locally with NO local `trades_*.json` files to simulate Cloud Run

## Related
- PR: fix/webhook-trade-source-20260117-001207
- Previous fix: v3.7.0 added fallback but didn't prioritize correctly
