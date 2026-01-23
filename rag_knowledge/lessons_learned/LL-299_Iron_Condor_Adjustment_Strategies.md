# LL-299: Iron Condor Adjustment Strategies

**Date**: January 23, 2026
**Category**: Strategy / Risk Management
**Severity**: HIGH
**Related**: LL-268, LL-277, LL-293

## Problem

When an iron condor is tested (price moves toward one of the short strikes), we need a systematic adjustment strategy to manage risk while preserving profit potential.

## Research Findings

### Primary Adjustment: Roll the Untested Side Closer

**When to adjust:**
- One short strike reaches 25-30 delta (getting tested)
- Price breaks through expected move range
- Position delta exceeds ±15

**How to adjust:**
1. Leave the tested side alone (don't chase)
2. Roll the untested side closer to current price
3. Collect additional credit to lower cost basis
4. Re-center the position around current price

### Adjustment Decision Matrix

| Scenario | Action | Rationale |
|----------|--------|-----------|
| Call side tested (price up) | Roll put spread up | Collect more credit, widen breakeven |
| Put side tested (price down) | Roll call spread down | Collect more credit, widen breakeven |
| Both sides threatened | Close position | Too much risk, take the loss |
| 7 DTE reached | Close regardless | Gamma risk too high |

### Delta Management Rules

| Untested Side Delta | Action |
|---------------------|--------|
| > 15 delta | Hold, no adjustment needed |
| 10-15 delta | Consider rolling closer |
| < 10 delta | Must roll - losing hedge value |

**Key insight**: Low delta positions don't offset tested side movement effectively.

### Rolling Mechanics

**Example: SPY at $590, Call side tested (price rallied to $605)**

Original Position:
- Short 575 put / Long 570 put (untested)
- Short 610 call / Long 615 call (tested)

Adjustment:
1. Close 575/570 put spread for small debit (~$0.10)
2. Open new 595/590 put spread for larger credit (~$1.00)
3. Net credit: ~$0.90

**Result**: Lower cost basis, wider profit zone, re-centered position

### When NOT to Adjust

1. **Within 7 DTE**: Just close the position (gamma risk)
2. **Tested side already breached short strike**: Take the loss
3. **Adjustment would exceed max risk**: Close instead
4. **Market reverses quickly**: The move may be temporary

### Adjustment Timing

| Time to Expiration | Adjustment Approach |
|-------------------|---------------------|
| 30-45 DTE | Aggressive - roll untested side closer |
| 21-30 DTE | Moderate - small adjustments only |
| 7-21 DTE | Defensive - consider closing |
| < 7 DTE | Exit - no adjustments, close position |

### Cost-Benefit Analysis

**Benefits of rolling untested side:**
- Collect additional credit (reduces cost basis)
- Widen breakeven points
- Re-center position delta to neutral
- Maintain profit potential

**Risks:**
- Market could reverse and test the moved side
- Transaction costs (4 more legs to close/open)
- May lock in smaller profit zone

### Alternative: Convert to Iron Butterfly

If highly confident in direction, convert to iron butterfly:
- Roll untested side so both short strikes match
- Significantly higher credit
- Much narrower profit zone
- Higher risk if wrong

**Recommendation**: Avoid this for SPY iron condors (too risky)

## Implementation for Our Strategy

### Adjustment Checklist

1. [ ] Is tested side short strike at 25+ delta?
2. [ ] Is untested side at < 15 delta?
3. [ ] Are we > 7 DTE?
4. [ ] Will adjustment cost be covered by new credit?
5. [ ] Does new position stay within 5% max risk?

### Automated Alert Thresholds

```python
IC_ADJUSTMENT_THRESHOLDS = {
    "tested_delta_trigger": 0.25,  # Alert when short delta reaches 25
    "untested_delta_min": 0.15,    # Must maintain 15+ delta on untested
    "min_dte_for_adjustment": 7,   # No adjustments below 7 DTE
    "max_adjustment_cost_pct": 0.30,  # Max 30% of credit for adjustment
}
```

## Current Strategy Alignment

| Parameter | Research Says | Our Setting | Status |
|-----------|---------------|-------------|--------|
| Adjustment strategy | Roll untested | Roll untested | ✅ Aligned |
| Adjustment DTE cutoff | 7-10 DTE | 7 DTE | ✅ Aligned |
| Delta trigger | 25-30 delta | Not automated | ⚠️ Manual |

## Action Items

1. **Monitor manually** for now (paper trading phase)
2. **Document each adjustment** in trade log
3. **Track adjustment outcomes** to refine thresholds
4. **Consider automation** after 90-day validation

## Sources

- [Option Alpha - Iron Condor Adjustments](https://optionalpha.com/lessons/iron-condor-adjustments)
- [Options Trading IQ - Condor Adjustment Strategies](https://optionstradingiq.com/condor-adjustment-strategies/)
- [Steady Options - Iron Condor Adjustment](https://steadyoptions.com/articles/iron-condor-adjustment/)
- [Data Driven Options - Rolling Iron Condors](https://datadrivenoptions.com/rolling-iron-condors/)
- [Barchart - How to Adjust Iron Condors](https://www.barchart.com/story/news/29998131/how-to-adjust-iron-condors-when-tested)

## Tags

`iron-condor`, `adjustment`, `roll-untested`, `risk-management`, `delta-management`
