# LL-281: Position Accumulation Crisis - 8 Contracts Instead of Max 4

**Date:** January 22, 2026
**Severity:** CRITICAL
**Status:** RESOLVED

## Summary
On January 21-22, 2026, 8 contracts of SPY260220P00658000 accumulated when the maximum allowed was 4. This violated the "1 iron condor at a time" rule from CLAUDE.md and resulted in significant unrealized losses.

## Root Causes Identified

### 1. Race Condition in Position Checks
- Multiple trades could evaluate position count simultaneously
- Each trade saw "< 4 positions" and passed the check
- All trades then executed, resulting in 8 contracts

### 2. No Global Workflow Concurrency
- 10+ GitHub Actions workflows could execute trades
- Each had separate (or no) concurrency groups
- Multiple workflows ran simultaneously on Jan 21

### 3. No Automatic Trading Halt
- TRADING_HALTED file was only created manually
- No automated detection of crisis conditions
- System kept accumulating despite danger

### 4. Dashboard Data Duplication
- LIVE and PAPER accounts showed identical data
- Dashboard read PAPER data for both accounts
- Masked the true state of accounts

## Timeline of Crisis
```
Jan 21, 16:18 - BUY 1 contract
Jan 21, 16:23 - BUY 1 contract (5 min later)
Jan 21, 16:39 - BUY 1 contract
Jan 21, 16:44 - BUY 1 contract (4 in 26 minutes!)
Jan 21, 17:32 - BUY 1 contract
Jan 21, 19:37 - BUY 1 contract
Jan 22, 14:50 - BUY 1 contract
Jan 22, 15:07 - BUY 1 contract
```

## Solutions Implemented

### 1. Trade Mutex Lock (`src/safety/trade_lock.py`)
- File-based exclusive lock prevents concurrent trade evaluation
- 30-second timeout prevents deadlocks
- Auto-clears stale locks after 5 minutes

### 2. Crisis Monitor (`src/safety/crisis_monitor.py`)
- Auto-creates TRADING_HALTED when:
  - Position count > 4
  - Unrealized loss > 25% of equity
  - Single position loss > 50%
- Logs all crises for analysis

### 3. Global Workflow Concurrency
- All 12 trade workflows updated with:
  ```yaml
  concurrency:
    group: global-trade-execution
    cancel-in-progress: false
  ```
- Only ONE trade workflow can run at a time

### 4. Dashboard LIVE/PAPER Separation
- `sync_alpaca_state.py` now fetches both accounts
- `live_account` section stores brokerage data
- Dashboard reads from correct data source

### 5. Single Source of Truth (`src/core/trading_constants.py`)
- MAX_POSITIONS = 4
- CRISIS_LOSS_PCT = 0.25
- All modules import from here

## Prevention Checklist
- [ ] Trade lock acquired before evaluating position count
- [ ] Global workflow concurrency prevents parallel execution
- [ ] Crisis monitor auto-halts on threshold breach
- [ ] Position limits imported from single source of truth
- [ ] Dashboard shows separate LIVE and PAPER data

## Commits
- fb8bd66: Add race condition prevention and auto-halt triggers
- 129031b: Consolidate position limits to single source of truth
- db205ef: Add global trade concurrency to workflows
- 1830d2f: Fix dashboard LIVE/PAPER separation
- PR #2700: Merged all fixes to main

## Key Learnings
1. **CI can't catch runtime race conditions** - need workflow-level controls
2. **Multiple workflows = multiple race condition vectors** - use global concurrency
3. **Manual circuit breakers fail** - automate crisis detection
4. **Dashboard bugs mask reality** - verify data sources independently

## Related Lessons
- LL-220: Credit spread win rates
- LL-246: Position count enforcement
- LL-268: Exit timing research
