# LL-272: SOFI Position Blocked All Trading - Buying Power Crisis

**ID**: LL-272
**Date**: 2026-01-21
**Severity**: CRITICAL
**Category**: Trading Operations

## Incident Summary
On Jan 21, 2026, the daily trading workflow executed successfully but placed **ZERO trades** because a rogue SOFI short put position was consuming all options buying power.

## Root Cause Analysis

### The Problem
1. SOFI260213P00032000 (short put) was open with -$685 market value
2. This position consumed 100% of options buying power
3. Workflow check: `if OPTIONS_BP == $0` → **BLOCKED ALL TRADING**
4. Position was also underwater: -$80 unrealized loss

### Why This Position Existed
- Sold on Jan 20, 2026 at $6.05
- **VIOLATED CLAUDE.md**: "SPY ONLY" mandate was clear
- Iron condor strategy should ONLY trade SPY

### The Silent Failure Mode
```yaml
# From daily-trading.yml lines 1126-1136
if (( $(echo "$OPTIONS_BP == 0" | bc -l) )); then
    echo "🚨 OPTIONS BUYING POWER = $0 - CANNOT TRADE TODAY"
    echo "⏭️ Equity fallback DISABLED"
```

The workflow "succeeded" but executed no trades. This is a **zombie mode failure**.

## Impact
- Lost 1 full trading day
- Potential premium collection lost: ~$50-75
- System appeared healthy but was non-functional

## Resolution
1. Triggered `close-non-spy-positions.yml` workflow
2. Triggered `daily-trading.yml` with `force_trade=true`
3. SOFI position will be closed, freeing buying power

## Prevention Measures

### Immediate
- [x] Create `close-non-spy-positions.yml` workflow (already exists)
- [x] Trigger emergency close workflow

### Long-term
1. Add pre-trade check: Validate only SPY positions exist
2. Add alert when non-SPY positions detected
3. Block `iron_condor_trader.py` from accepting non-SPY symbols
4. Add options_buying_power > $500 assertion before skipping

## Code Fix Needed
In `daily-trading.yml`, change the $0 buying power check to ALERT, not silently skip:

```yaml
# BEFORE (silent skip)
echo "⏭️ Equity fallback DISABLED"

# AFTER (alert and fail)
echo "::error::OPTIONS BUYING POWER = $0 - INVESTIGATE IMMEDIATELY"
exit 1
```

## Lessons Learned
1. "SPY ONLY" means SPY ONLY - no exceptions
2. Workflow success != trades executed
3. Options buying power = $0 should FAIL workflow, not silently skip
4. Need daily assertion: "positions are SPY only"

## Tags
critical, trading, options, buying-power, sofi, spy-only, workflow, zombie-mode
