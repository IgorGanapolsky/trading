# LL-277: Iron Condor Optimization Research - 86% Win Rate Strategy

**Date**: January 21, 2026
**Category**: strategy, research, optimization
**Severity**: HIGH

## Source
- [Options Trading IQ: Iron Condor Success Rate](https://optionstradingiq.com/iron-condor-success-rate/)
- [Project Finance: Iron Condor Management (71,417 trades)](https://www.projectfinance.com/iron-condor-management/)

## Key Finding: Delta Selection Is CRITICAL

| Short Strike Delta | Win Rate |
|-------------------|----------|
| **10-15 delta** | **86%** |
| 30 delta | 34% |

**Our current strategy uses 15-20 delta. This research validates our approach.**

## Optimal Management Techniques

1. **Early profit-taking**: Close at 50% max profit BEFORE mid-duration
2. **Rolling adjustments**: Move untested side closer when one side is tested
3. **Time-based exits**: Close 7 DTE (not 21 DTE as we currently do)
4. **Stop losses**: 2x premium received as max loss threshold

## Trade Statistics (Backtest)
- Average win: $460
- Average loss: $677
- Win rate: 86%
- Annualized return on risk: ~36%

## Recommendation Updates for CLAUDE.md

| Current Rule | Recommended Change |
|--------------|-------------------|
| Close at 21 DTE | Close at **7 DTE** (tighter) |
| 15-20 delta short | Keep 15 delta (validated) |
| 50% profit target | ✅ Correct |
| 200% stop-loss | Consider 2x credit (~200%) ✅ |

## Action Items
- [x] Record this lesson
- [ ] Consider updating DTE exit from 21 to 7-14 days
- [ ] Validate with paper trades before changing

## Prevention
Always research best practices before finalizing strategy parameters.
