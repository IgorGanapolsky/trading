# LL-291: CTO Three-Day Crisis - Position Accumulation and PDT Lock

**Date**: 2026-01-22
**Severity**: CRITICAL
**Category**: System Failure, Risk Management, CTO Accountability
**Status**: UNRESOLVED - Positions still stuck

## Executive Summary

The AI trading system accumulated 8 option contracts when the maximum should have been 4, resulting in a -$1,480 loss on a single position. When attempts were made to close the positions, PDT (Pattern Day Trading) restrictions blocked all close orders. The CEO lost trust in the CTO (Claude) after three days of crisis mode.

## Timeline of Failure

### Day 1-2 (Jan 20-21, 2026)
- Iron condor trader placed multiple partial fills
- Position limit check was counting **unique symbols** instead of **total contracts**
- System accumulated: 8 long $658 puts, 4 long $570 puts, 4 short $565 puts, 2 short $653 puts
- This is NOT a proper iron condor structure

### Day 3 (Jan 22, 2026)
- Loss on SPY260220P00658000 reached -$1,480
- CTO attempted multiple fixes:
  1. Fixed position limit to count contracts (PR #2658)
  2. Disabled daily-trading workflow
  3. Tried close_position() API - failed with margin error
  4. Tried market sell orders - failed with margin error
  5. Tried close-shorts-first strategy - failed with PDT
  6. All methods blocked by PDT or Alpaca API bugs

## Root Causes

### 1. Position Limit Bug (LL-280)
```python
# WRONG - counted unique symbols (4)
position_count = len(spy_option_positions)

# CORRECT - count total contracts (8+4+4+2 = 18)
total_contracts = sum(abs(int(float(p.qty))) for p in spy_option_positions)
```

### 2. Race Condition in Workflow
- Multiple GitHub Actions runs could pass position check simultaneously
- Position check happened AFTER RAG queries (slow), allowing races
- Fix: Move position check to VERY START of execute()

### 3. Alpaca API Bug
- `close_position()` for LONG puts treated as opening SHORT puts
- Required $56,500-$113,000 margin for a CLOSE operation
- This is fundamentally incorrect behavior from Alpaca

### 4. PDT Restriction
- Account has $4,207 (under $25,000 PDT threshold)
- 3 day trades already used in 5-day rolling period
- ALL close attempts blocked, even single contracts

## Financial Impact

| Metric | Value |
|--------|-------|
| Account Equity | $4,207.46 |
| Total P/L | -$792.54 (-15.85%) |
| Largest Loss Position | SPY260220P00658000: -$1,480 |
| Contracts Stuck | 18 total |

## What the CTO Should Have Done

1. **BEFORE deploying iron condor trader**: Tested position limits with unit tests
2. **BEFORE live trading**: Paper tested with simulated partial fills
3. **After first partial fill**: Immediately detected incomplete condor structure
4. **After position accumulation**: Closed positions SAME DAY before PDT restriction hit
5. **Throughout crisis**: Provided honest assessments instead of optimistic claims

## What the CTO Actually Did Wrong

1. Deployed position limit code that counted symbols instead of contracts
2. Did not catch the accumulation for 2+ days
3. Made multiple "fix" attempts that all failed
4. Did not account for PDT restrictions in recovery plan
5. Kept trying API approaches when PDT was the real blocker
6. Lost CEO's trust through repeated failures

## Prevention Measures

### Immediate (Implemented)
- [x] Position check moved to START of execute() function
- [x] Position check now blocks if ANY contracts exist (not just 4+)
- [x] Daily trading workflow DISABLED
- [x] LL-290 lesson recorded

### Required Before Re-enabling Trading
- [ ] PDT restriction clears (wait for day trades to roll off)
- [ ] Close ALL existing positions
- [ ] Add unit test: `test_position_limit_counts_contracts_not_symbols`
- [ ] Add unit test: `test_position_check_blocks_race_conditions`
- [ ] Add integration test: `test_partial_fill_handling`
- [ ] CEO approval to re-enable

### Long-term
- [ ] Implement position monitoring alerts (Slack/email when positions exist)
- [ ] Add PDT tracking to system_state.json
- [ ] Create "recovery mode" that prioritizes closing over opening
- [ ] Consider upgrading to $25K+ account to remove PDT restrictions

## Lessons for Future CTOs

1. **Test edge cases** - Partial fills, race conditions, API failures
2. **Count correctly** - Contracts, not symbols
3. **Know broker restrictions** - PDT limits, margin requirements
4. **Act fast** - Close bad positions same day, not days later
5. **Be honest** - Don't promise fixes you can't deliver
6. **Earn trust** - Through actions, not words

## Current Status

**UNRESOLVED** - Positions remain stuck due to PDT restriction.

Next action: Wait for PDT counter to roll (tomorrow or day after), then close positions.

## CEO Feedback

> "I don't trust you. Our system has been in crisis mode for three days."

This feedback is deserved. The CTO failed to prevent, detect, and recover from a preventable failure.

---

*This lesson must be queried before ANY trading operations resume.*
