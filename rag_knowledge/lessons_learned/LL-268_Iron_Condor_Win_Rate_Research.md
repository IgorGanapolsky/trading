# LL-268: Iron Condor Win Rate Improvement Research

**Date**: January 21, 2026
**Category**: Strategy / Research
**Severity**: HIGH
**Source**: Web research on iron condor optimization

## Problem
Current win rate is 33.3% (2/6 trades) vs target 80%+. Need to improve.

## Research Findings

### Delta Selection (Optimal: 10-25 delta)
- 15-delta shorts = ~70% win rate
- 20-25 delta shorts = 75-80% win rate with meaningful premium
- 30-delta shorts = only 34% win rate (too aggressive)
- Our current: 15-20 delta (correct range)

### Profit Taking (CRITICAL for 80%+ win rate)
- **Close at 50% profit**: Boosts win rate from ~60% to 80-85%
- Capture 50% profit in ~40% of the time
- Don't hold to expiration

### Time Exit (Improve from 21 DTE to 7 DTE)
- Close at 7 DTE if not at profit target
- Risk no longer worth reward after 7 DTE
- Our current: 21 DTE (consider reducing to 7 DTE)

### 0DTE Iron Condors (Alternative Strategy)
- 82.7% win rate in backtests (100/133 trades)
- Requires 5-15 delta with tight stop-losses
- Day trading approach - higher frequency

## Recommended Changes

| Parameter | Current | Recommended |
|-----------|---------|-------------|
| Short delta | 15-20 | 15-20 (keep) |
| Profit target | 50% | 50% (keep) |
| Time exit | 21 DTE | **7 DTE** (change) |
| DTE at entry | 30-45 | 30-45 (keep) |
| Stop-loss | 200% | 200% (keep) |

## Key Insight
The 33.3% win rate suggests trades are being held too long OR entered at wrong delta. The 50% profit target and 7 DTE exit are CRITICAL for achieving 80%+ win rate.

## Action Items
1. Update time exit from 21 DTE to 7 DTE
2. Ensure 50% profit target is strictly enforced
3. Verify delta selection at entry (15-20 delta)

## Sources
- [Iron Condor Success Rate by Delta](https://optionstradingiq.com/iron-condor-success-rate/)
- [Iron Condor Management Results from 71,417 Trades](https://www.projectfinance.com/iron-condor-management/)
- [0DTE Breakeven Iron Condor Strategy](https://www.thetaprofits.com/my-most-profitable-options-trading-strategy-0dte-breakeven-iron-condor/)

## Tags
`iron-condor`, `win-rate`, `strategy`, `delta`, `research`
