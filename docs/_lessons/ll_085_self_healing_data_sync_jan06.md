# Lesson Learned #085: Self-Healing Data Sync via GitHub API

**Date**: January 6, 2026
**Severity**: HIGH
**Category**: Infrastructure
**Status**: RESOLVED

## Incident Summary

Trading data (trades_2026-01-06.json, system_state.json) failed to sync to GitHub main branch, causing dashboard and Dialogflow to show zero trades for the day despite successful trade execution.

## Root Cause

Git push in the workflow failed twice due to concurrent PR merges causing rebase conflicts. The retry logic (3 attempts with rebase) was insufficient because:

1. Multiple PRs were being merged simultaneously
2. Each rebase attempt fetched new commits, but more PRs merged in between
3. The rebase cycle couldn't converge

## Impact

- Dashboard showed zero trades for Jan 6, 2026
- Dialogflow reported "no trades yet"
- CEO frustrated about repeated operational failures
- 14 days of similar issues (Dec 23 - Jan 6) due to various sync failures

## Solution Implemented

Created a **self-healing** fallback mechanism using the GitHub Contents API:

### 1. New Utility Script (`scripts/sync_data_to_github.py`)
- Uses GitHub API PUT `/repos/{owner}/{repo}/contents/{path}`
- Atomic operation - bypasses git conflicts entirely
- Handles SHA resolution for file updates
- Retry logic with exponential backoff (2s, 4s, 8s, 16s)
- Conflict resolution: re-fetches SHA and retries on 409

### 2. Workflow Enhancement (`.github/workflows/daily-trading.yml`)
- Added "API Fallback - Sync trading data" step
- Runs after git push attempt (whether success or failure)
- Syncs critical files: system_state.json, trades_YYYY-MM-DD.json, performance_log.json

### 3. Test Coverage
- 16 unit tests covering all edge cases
- Tests for: token retrieval, API requests, SHA resolution, conflict handling

## Key Insight

**Git push vs API PUT**:
| Aspect | Git Push | GitHub API PUT |
|--------|----------|----------------|
| Conflicts | Yes (rebase needed) | No (atomic operation) |
| Concurrent safety | Poor | Excellent |
| Performance | Fast | Slightly slower |
| Complexity | High (merge logic) | Low (direct update) |

For data files that are **machine-generated** (not human-edited), GitHub API is superior because it eliminates conflict resolution entirely.

## Prevention

1. **Primary**: Use GitHub API for all automated data file updates
2. **Secondary**: Keep git push with retry as first attempt (faster when no conflicts)
3. **Monitoring**: Dashboard should alert when sync fails

## Files Changed

- `scripts/sync_data_to_github.py` (NEW) - GitHub API sync utility
- `.github/workflows/daily-trading.yml` - Added API fallback step
- `tests/test_sync_data_to_github.py` (NEW) - 16 unit tests

## Verification

```bash
# Test the sync utility locally
export GITHUB_TOKEN="your-token"
python3 scripts/sync_data_to_github.py --file data/system_state.json

# Run tests
python3 -m pytest tests/test_sync_data_to_github.py -v
```

## Related Lessons

- LL-084: RAG Blocking Trading (same time period)
- LL-074: ChromaDB Installation Issues
- LL-051: Calendar Awareness for Trading AI
