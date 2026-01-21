# LL-269: Iron Condor Entry Signals & Timing

**Date**: January 21, 2026
**Category**: Strategy / Entry Signals
**Severity**: HIGH
**Source**: Web research on iron condor entry timing

## Problem
System not generating enough trade signals. Need clear entry criteria.

## Research Findings

### VIX Range (Optimal: 15-25)
- VIX 15-25: Ideal - premiums decent, risk manageable
- VIX < 15: Avoid - premiums too thin
- VIX > 25: Caution - volatility too high, wider strikes needed

### IV Percentile (Optimal: >50%)
- IV Percentile >67%: Best - options expensive, vol crush in your favor
- IV Percentile 50-67%: Good - adequate premium
- IV Percentile <50%: Avoid - options cheap, not worth selling

### DTE Selection
- 30-45 DTE: Standard approach (our current setting)
- 20-45 DTE: Acceptable range per research
- 0-3 DTE: Day trading approach (higher frequency, higher risk)

### Entry Checklist
1. [ ] VIX between 15-25?
2. [ ] IV Percentile >50%?
3. [ ] No earnings within 30 days?
4. [ ] Clear support/resistance levels?
5. [ ] Not in a squeeze (low IV about to expand)?

### When NOT to Enter
- VIX rising sharply (expect more turbulence)
- IV Percentile <30% (options too cheap)
- Earnings within 30 days
- Major Fed announcements pending
- Stock in a squeeze pattern

## Current Strategy Alignment

| Parameter | Research Says | Our Setting | Status |
|-----------|---------------|-------------|--------|
| DTE | 20-45 days | 30-45 days | ✅ Good |
| Delta | 10-25 | 15-20 | ✅ Good |
| IV Check | >50% percentile | 30% min | ⚠️ Too low |
| VIX Check | 15-25 | Not enforced | ⚠️ Add check |

## Recommended Improvements

1. **Add VIX gate**: Only trade when VIX is 15-25
2. **Raise IV threshold**: Change MIN_IV_PERCENTILE from 30 to 50
3. **Add earnings check**: Block trades 30 days before earnings

## Sources
- [IV Rank & Percentile for Iron Condors](https://www.tradingview.com/chart/VIX/ruLfEtZR-Watch-this-BEFORE-taking-Iron-Condors-IV-Rank-Percentile/)
- [Best Iron Condor Entry Points](https://slashtraders.com/en/blog/best-iron-condor-options/)
- [Iron Condor Strategy Guide](https://optionalpha.com/strategies/iron-condor)

## Tags
`iron-condor`, `entry-signals`, `vix`, `iv-percentile`, `timing`
