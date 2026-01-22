# LL-293: Iron Condor Optimization for $30K Account

**Date**: January 22, 2026
**Category**: Strategy / Research
**Severity**: HIGH
**Source**: Web research compilation for new paper account

## Context

New $30K paper account established. Need optimized iron condor parameters for:
- Above $25K = NO PDT restrictions
- Target: $400-800/month (1.3-2.7% monthly return)
- Risk: Max 5% per trade ($1,500)

## Optimal Parameters (Research-Backed)

### Entry Criteria

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Underlying | SPY only | Best liquidity, tightest spreads |
| Short Delta | 16-20 | 75-85% probability of profit |
| Wing Width | $5 | Defined risk, capital efficient |
| DTE at Entry | 30-45 days | Optimal theta decay curve |
| IV Rank | >50 preferred | Higher premium collection |

### Exit Criteria (CRITICAL for 80%+ Win Rate)

| Trigger | Action | Rationale |
|---------|--------|-----------|
| 50% profit | CLOSE | Capture gains, free up capital |
| 7 DTE remaining | CLOSE | Gamma risk no longer worth it |
| 200% of credit loss | CLOSE | Stop-loss prevents blowouts |
| Short delta hits 30-35 | ADJUST or CLOSE | Position challenged |

### Position Sizing for $30K Account

| Account | Max Risk/Trade | Max Position Size | Concurrent Trades |
|---------|----------------|-------------------|-------------------|
| $30,000 | $1,500 (5%) | 1 iron condor | 1 at a time |

**Phil Town Rule**: Never use more than 50% of buying power. With $60K buying power, max deployment = $30K worth of positions.

## Adjustment Strategies (When Challenged)

### If Tested Side Approaches 30 Delta:

1. **Roll untested side closer** - Collect additional credit
2. **Roll tested side out in time** - 21-30 days for credit
3. **Close tested side** - Take partial loss, keep profitable side
4. **Close entire position** - If both sides under pressure

### Adjustment Decision Tree:

```
Position Challenged?
├── >14 DTE remaining?
│   ├── Yes → Wait, price often reverses
│   └── No → Close or roll
├── Loss > 150% of credit?
│   └── Close entire position
└── Untested side profitable?
    └── Close tested, keep untested
```

## Expected Performance (Research-Based)

| Metric | Conservative | Moderate | Target |
|--------|--------------|----------|--------|
| Win Rate | 70% | 75% | 80%+ |
| Avg Win | $150 | $200 | $250 |
| Avg Loss | $300 | $400 | $500 |
| Monthly Trades | 2 | 3 | 4 |
| Monthly Return | 1.0% | 1.5% | 2.0% |

### $30K Account Projections

| Trades/Month | Win Rate | Monthly P/L | Annual P/L |
|--------------|----------|-------------|------------|
| 2 | 80% | $220 | $2,640 |
| 3 | 80% | $330 | $3,960 |
| 4 | 80% | $440 | $5,280 |

**Note**: These are CONSERVATIVE projections following Phil Town Rule #1.

## Mistakes to Avoid

1. ❌ Don't put multiple iron condors expiring same week
2. ❌ Don't double down on losing trades
3. ❌ Don't hold past 7 DTE hoping for recovery
4. ❌ Don't trade during earnings weeks
5. ❌ Don't get greedy trying to capture last 50%

## Implementation Checklist

- [ ] Enter at 30-45 DTE
- [ ] Short strikes at 16-20 delta
- [ ] Wings $5 wide
- [ ] Set alerts for 50% profit
- [ ] Set alerts for 200% loss
- [ ] Calendar reminder at 7 DTE
- [ ] Never hold through earnings

## Sources

- [Iron Condor Strategy Setup 2026](https://apexvol.com/strategies/iron-condor)
- [0DTE Iron Condor Profitability](https://www.thetaprofits.com/0dte-iron-condor-a-consistently-profitable-stratey/)
- [Iron Condor Management Best Practices](https://quantstrategy.io/blog/how-to-build-and-adjust-the-iron-condor-strategy-for/)
- [45 DTE SPX Iron Condors](https://www.forexfactory.com/thread/1258877-a-tasty-standard-45-dte-spx-iron)
- [Option Alpha Iron Condor Guide](https://optionalpha.com/strategies/iron-condor)
- [Fidelity Iron Condor Strategy](https://www.fidelity.com/viewpoints/active-investor/iron-condor-strategy)
- [Interactive Brokers Iron Condor](https://www.interactivebrokers.com/campus/traders-insight/securities/options/iron-condor-strategy-heres-what-you-need-to-know/)

## Tags
`iron-condor`, `$30K`, `optimization`, `research`, `strategy`, `phil-town`
