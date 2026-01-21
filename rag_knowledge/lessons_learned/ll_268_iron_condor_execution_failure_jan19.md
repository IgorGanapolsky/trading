# LL-268: Iron Condor Execution Failure - Call Legs Missing

**Date**: 2026-01-19
**Updated**: 2026-01-21 (Prevention items IMPLEMENTED)
**Category**: Trading, Execution, Strategy
**Severity**: RESOLVED
**Resolution Date**: 2026-01-21
**Resolution**: All 4 fixes implemented - dynamic pricing, call spread execution verified

## Summary

The $5K paper account has ZERO call spreads despite CLAUDE.md mandating iron condors. All 6 positions are PUT options only, meaning we're running bull put spreads (directionally bullish) instead of iron condors (neutral).

## Evidence

Current positions (from system_state.json):
```
SPY260220P00565000: +1 (long put)  -> 565/570 put spread
SPY260220P00570000: -1 (short put) ->
SPY260220P00595000: +1 (long put)  -> 595/600 put spread
SPY260220P00600000: -1 (short put) ->
SPY260220P00653000: +2 (long put)  -> 653/658 put spread (UNBALANCED)
SPY260220P00658000: -1 (short put) ->
```

**Missing**: ANY call options (SPY...C...) for bear call spreads.

## Root Causes

### 1. Options Buying Power = $0
When `options_buying_power=$0`, the workflow (`daily-trading.yml:1054-1065`) skips iron condors entirely and runs credit spread fallback that only executes PUT spreads.

### 2. Hardcoded SPY Price
`iron_condor_trader.py:98`:
```python
return 595.0  # Approximate SPY price Jan 2026
```
This hardcoded value means strike calculations are wrong when SPY moves.

### 3. Hardcoded Limit Price
`iron_condor_trader.py:293`:
```python
limit_price=0.50,  # Will need real pricing
```
All 4 legs use $0.50 limit regardless of actual market prices. Call options likely need higher prices to fill.

### 4. Credit Spread Fallback
`daily-trading.yml:1067-1089` runs `execute_credit_spread.py` which ONLY executes PUT credit spreads, not iron condors.

## Impact

- No premium collected from CALL side
- Directionally biased (bullish only)
- Violates CLAUDE.md iron condor mandate
- Lower win rate than true iron condors
- Exposed to downside moves without upside protection

## Fix Required

1. **Fix options buying power issue** - Investigate why it's $0
2. **Add real market data** - Replace hardcoded SPY price with API call
3. **Use market prices for limits** - Get actual bid/ask before submitting
4. **Add call spread execution** - Ensure both PUT and CALL spreads execute

## Temporary Mitigation

`close_excess_spreads.py` scheduled for Jan 20, 9:35 AM ET to close 2 of 3 spreads and comply with 1-position limit.

## Prevention (IMPLEMENTED Jan 21, 2026)

1. ✅ **CI test added**: `tests/test_iron_condor_validation.py` validates BOTH put AND call spreads
2. ✅ **Execution verification added**: `iron_condor_trader.py` now checks `len(order_ids) == 4`
3. ✅ **Alert added**: Logs "🚨 INCOMPLETE IRON CONDOR" with filled/missing legs if partial fill
4. ✅ **close_excess_spreads.py fixed**: Now uses proper Alpaca API instead of non-existent methods

## Phil Town Alignment

This violates Rule #1: "Don't Lose Money"
- Iron condors are defined-risk on BOTH sides
- PUT-only spreads have unlimited loss if market crashes
- Must fix before next trading day

## Tags

`resolved`, `execution`, `iron-condor`, `strategy-mismatch`, `rule-1`, `fixed-jan21`
