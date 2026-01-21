# LL-242: Adversarial Audit - Strategy Mismatch Crisis

**Date**: 2026-01-19
**Category**: System Bug, Strategy, Audit
**Severity**: RESOLVED
**Resolution Date**: 2026-01-21
**Resolution**: Disabled guaranteed_trader, simple_daily_trader, rule_one_trader in daily-trading.yml

## Summary

Adversarial audit discovered CRITICAL mismatches between documented strategy (CLAUDE.md) and actual code execution.

## Finding #1: CLAUDE.md vs Code Contradiction

**CLAUDE.md states:**
- "CREDIT SPREADS on SPY/IWM ONLY - defined risk"
- "NO NAKED PUTS"
- "1 spread at a time"

**Actual code behavior:**

| Script | What It Does | Violation |
|--------|-------------|-----------|
| `guaranteed_trader.py` | Buys SPY shares ($100/day) | NOT credit spreads |
| `simple_daily_trader.py` | Sells NAKED cash-secured puts | NO defined risk |
| `rule_one_trader.py` | Trades F, SOFI, T, INTC, BAC, VZ | Individual stocks, not SPY/IWM |

## Finding #2: Cash-Secured Put != Credit Spread

**Critical misconception in code:**
- `simple_daily_trader.py` line 8: "SPY CREDIT SPREADS ONLY"
- But executes `execute_cash_secured_put()` (line 549)

**Risk comparison:**
| Strategy | Max Loss | Risk Type |
|----------|----------|-----------|
| Cash-Secured Put (CSP) | Strike × 100 - Premium | UNLIMITED* |
| Credit Spread | Spread Width - Premium | DEFINED |

*Example: SPY $570 put = $57,000 max loss vs $200 for $2-wide spread

## Finding #3: Multiple Uncoordinated Traders

`daily-trading.yml` runs FOUR traders in sequence:
1. Line 916: `guaranteed_trader.py` (buys SPY shares)
2. Line 969: `autonomous_trader.py` (main orchestrator)
3. Line 1222: `simple_daily_trader.py` (sells naked puts)
4. Line 1244: `rule_one_trader.py` (individual stocks)

**Problem:** Each trader makes independent decisions with NO knowledge of others.

**Impact:**
- Position sizing violations (each uses its own 5-10% calculation)
- Combined exposure could exceed 20-30% of portfolio
- No centralized state between traders

## Finding #4: Missing Holiday Validation

Workflows running on weekday cron (`1-5`) without holiday check:
- `daily-trading.yml` - MAIN TRADING WORKFLOW
- `cancel-stale-orders.yml`
- `sync-system-state.yml`

Only `execute-credit-spread.yml` has proper Alpaca calendar validation.

## Root Cause

1. **Organic Growth**: Traders added piecemeal without holistic review
2. **Naming Confusion**: "credit spread" used loosely to mean any option strategy
3. **Documentation Drift**: CLAUDE.md updated but code not refactored
4. **No Integration Tests**: No test validates CLAUDE.md rules match code behavior

## Recommended Fixes

### Immediate (P0)
1. **Consolidate to single trader** - Remove redundant trader scripts
2. **Enforce credit spreads** - Replace all CSP logic with proper spread execution
3. **Add holiday check** - Add calendar validation to daily-trading.yml

### Short-term (P1)
1. **Position coordinator** - Centralized service to track combined exposure
2. **CLAUDE.md compliance test** - CI job that validates code matches strategy rules
3. **Spread-only mode** - Feature flag to disable all non-spread trading

### Long-term (P2)
1. **Single strategy engine** - Replace 4 traders with one configurable engine
2. **Rule #1 validator** - Pre-trade check that validates against CLAUDE.md limits

## Phil Town Rule #1 Impact

**THIS IS A RULE #1 VIOLATION.**

The documented strategy (defined-risk credit spreads) was chosen specifically to limit losses. The actual code (naked puts) exposes the account to catastrophic loss scenarios:

- One bad CSP assignment could lose 100% of strike value
- Example: SPY drops to $400, $570 put assigned = $17,000 loss on a $5K account

## Finding #5: Data Staleness and Corruption

**system_state.json issues:**
- `last_updated`: 2026-01-16 (3 DAYS OLD)
- `sync_mode`: "skipped_no_keys" (failing silently)
- **6 positions** when CLAUDE.md says "1 spread at a time"
- **Corrupt data**: Trade entries with `symbol: null` and negative prices

**Position count violation:**
```
Current: 3 active spreads (6 option positions)
Allowed: 1 spread at a time (CLAUDE.md)
```

**Corrupt trades (system_state.json lines showing NULL symbols):**
```json
{
  "symbol": null,
  "side": "None",
  "price": "-0.05"
}
```

## Finding #6: Silent Sync Failures

The `sync_mode: "skipped_no_keys"` indicates the sync workflow is failing silently. The system is operating on 3-day-old data without warning.

## Tags
`critical`, `strategy-mismatch`, `audit`, `rule-1-violation`, `naked-puts`, `credit-spreads`, `data-staleness`, `corruption`
