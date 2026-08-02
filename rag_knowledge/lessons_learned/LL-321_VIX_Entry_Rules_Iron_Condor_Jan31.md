# LL-321: VIX-Based Iron Condor Entry Rules

**Date**: January 31, 2026
**Category**: Strategy / Entry Timing
**Severity**: HIGH
**Related**: LL-299, LL-310, LL-268, LL-277

## Summary

Research-backed entry rules for iron condors based on VIX levels and IV rank.

## Current Market Context

**VIX as of Jan 31, 2026**: 17.24 (+5.44%)

This is in the LOW-MEDIUM volatility zone. Not ideal for iron condors but tradeable.

## VIX-Based Entry Rules

### The Zones

| VIX Level | Zone        | Iron Condor Recommendation      |
| --------- | ----------- | ------------------------------- |
| < 15      | LOW         | Avoid - premiums too thin       |
| 15-20     | LOW-MEDIUM  | Tradeable with caution          |
| **20-25** | **OPTIMAL** | **Best entry zone**             |
| 25-30     | HIGH        | Excellent premiums, higher risk |
| > 30      | EXTREME     | Wide spreads or avoid           |

### Entry Decision Matrix

| VIX       | IV Rank   | Action                     |
| --------- | --------- | -------------------------- |
| < 15      | Any       | WAIT - don't enter         |
| 15-20     | < 30%     | WAIT - premiums not rich   |
| 15-20     | 30-50%    | CONSIDER - small position  |
| 15-20     | > 50%     | ENTER - decent setup       |
| **20-25** | **> 30%** | **ENTER - optimal zone**   |
| 25-30     | > 30%     | ENTER - excellent premiums |
| > 30      | Any       | CAUTION - may whipsaw      |

## IV Rank Guidelines

- **IV Rank > 50%**: Ideal - rich premiums
- **IV Rank 30-50%**: Acceptable - decent credit
- **IV Rank < 30%**: Avoid - premiums too thin

**Key insight**: High IV = vol crush benefit when IV reverts to mean.

## Delta Selection by VIX

| VIX Level | Recommended Delta | Rationale                       |
| --------- | ----------------- | ------------------------------- |
| 15-20     | 16-delta          | Need wider wings for safety     |
| 20-25     | 20-delta          | Can tighten for more premium    |
| > 25      | 20-25 delta       | Collect more, expect volatility |

## Practical Entry Checklist

1. [ ] Check VIX level (ideally > 20)
2. [ ] Check SPY IV Rank (ideally > 50%)
3. [ ] Verify no earnings/macro events in 7 days
4. [ ] Confirm 30-45 DTE expiration available
5. [ ] Verify position size ≤ 5% of account

## Current Assessment (Jan 31, 2026)

| Metric         | Value                      | Status                    |
| -------------- | -------------------------- | ------------------------- |
| VIX            | 17.24                      | ⚠️ Low-medium (not ideal) |
| IV Rank SPY    | ~25-35%                    | ⚠️ Below optimal          |
| Recommendation | **Small position or WAIT** |                           |

**Monday trade plan**: Enter 1 iron condor (not 2) if VIX stays in 17-18 range. If VIX spikes to 20+, consider 2 positions.

## Research Sources

- [Apex Vol - Iron Condor Strategy 2026](https://apexvol.com/strategies/iron-condor)
- [Project Option - Iron Condor Management Study (71,417 trades)](https://www.projectoption.com/iron-condor-management-study/)
- [Advanced Auto Trades - SPX Iron Condor](https://advancedautotrades.com/iron-condor-strategy/)
- [Trasignal - 10 Steps to Master Iron Condors 2026](https://trasignal.com/blog/learn/iron-condor-strategy/)
- [Market Chameleon - SPY Option Strategy Benchmarks](https://marketchameleon.com/Overview/SPY/Option-Strategy-Benchmarks/Iron-Condor/)
- [Forex Factory - Tasty Standard 45 DTE SPX Iron Condors](https://www.forexfactory.com/thread/1258877-a-tasty-standard-45-dte-spx-iron)

## Key Takeaways

1. **Don't force trades in low VIX** - Wait for VIX > 20 for optimal entries
2. **IV Rank matters more than VIX alone** - Check both
3. **Vol crush is your friend** - Enter high IV, profit when it drops
4. **Smaller positions in low vol** - Scale up when VIX rises

## Tags

`iron-condor`, `vix`, `iv-rank`, `entry-timing`, `volatility`, `research`
