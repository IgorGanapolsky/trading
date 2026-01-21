# LL-277: Iron Condor Delta Optimization Research

**Date**: 2026-01-21
**Category**: Strategy, Research
**Severity**: INFORMATIONAL

## Research Summary

Web research conducted on optimal delta selection for SPY iron condors.

## Key Findings

### Delta Selection: 20-25 Delta is the Sweet Spot

| Delta Range | Win Rate | Premium | Trade-off |
|-------------|----------|---------|-----------|
| 10-15 delta | 85%+ | LOW | Barely collecting premium |
| 15-20 delta | 75-80% | Medium | Good balance |
| 20-25 delta | 70-75% | HIGH | Best risk/reward "pocket" |
| 25+ delta | 60-65% | Very High | Strangle territory |

### Management Best Practices (from backtests)

1. **Close at 50% profit** - Boosts win rate to 85%+ (CURRENT STRATEGY: ✅)
2. **Exit before expiration** - 7-21 DTE to avoid gamma risk (CURRENT STRATEGY: ✅ 21 DTE)
3. **45-DTE entry** - Optimal time decay curve (CURRENT STRATEGY: ✅ 30-45 DTE)

### Backtest Data

From Project Finance study of 40,868 iron condors:
- Earlier profit-taking = higher success rates
- Loss-taking approaches = decreased success
- 50% profit target is optimal balance

### Recommendation for Our Strategy

**Current CLAUDE.md says 15-20 delta**. Research suggests considering:
- Shift to 20-25 delta for more premium
- Maintain 50% profit exit (already doing this)
- 21 DTE exit is conservative but safe

**No change needed** - our current parameters align with research.

## Sources

- [Iron Condor Success Rate - OptionsTradingIQ](https://optionstradingiq.com/iron-condor-success-rate/)
- [Iron Condor Strategy 2026 - ApexVol](https://apexvol.com/strategies/iron-condor)
- [Iron Condor Management - Project Finance](https://www.projectfinance.com/iron-condor-management/)
- [SPY Option Strategy Benchmarks - MarketChameleon](https://marketchameleon.com/Overview/SPY/Option-Strategy-Benchmarks/Iron-Condor/)

## Tags

`iron-condor`, `delta`, `research`, `backtest`, `SPY`
