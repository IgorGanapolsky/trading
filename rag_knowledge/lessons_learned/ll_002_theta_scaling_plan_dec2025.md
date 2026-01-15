# Lesson Learned: Theta Scaling Plan - December 2025

**ID**: LL-002
**Date**: December 2, 2025
**Severity**: MEDIUM
**Category**: Strategy / Scaling

## Historical Context

This lesson documents the theta scaling strategy from December 2, 2025 when account equity was $6,000.

## Equity-Gated Strategy Tiers

| Tier | Capital Required | Strategies Enabled |
|------|------------------|-------------------|
| 1 | $6,000 | Poor Man's Covered Call (PMCC) |
| 2 | $10,000 | Iron Condors |
| 3 | $25,000+ | Full Suite |

## Configuration at $6K

- **Account Equity**: $6,000
- **Daily Premium Target**: $10/day ($200/month)
- **Regime**: Calm
- **Theta Enabled**: Yes

## Opportunities Identified

### SPY Poor Man's Covered Call
- Contracts: 2
- Estimated Premium: $70
- IV Percentile: 63.9%

### QQQ Poor Man's Covered Call
- Contracts: 2
- Estimated Premium: $70
- IV Percentile: 73.5%

**Total Estimated Premium**: $20/day

## Key Lessons

1. **Equity gates protect capital** - Don't attempt advanced strategies without sufficient capital
2. **$10/day is achievable at $6K** - Conservative target with PMCC strategy
3. **SPY/QQQ are preferred underlyings** - High liquidity, tight spreads
4. **IV percentile guides timing** - Higher IV = better premium

## Why This Failed to Execute

The December 2025 system had strategy identification but lacked:
- Trade execution automation
- Position management
- Risk monitoring

This led to the system generating signals but not acting on them.

## Application to Current $5K Account

- Current capital ($4,959) is below the $6K Tier 1 threshold
- Focus on accumulation until reaching $6K
- When ready: Start with credit spreads on SPY/IWM (simpler than PMCC)
- Target: $150-250/month (3-5%) is more realistic than $200/day

## Tags

`theta`, `scaling`, `historical`, `december-2025`, `pmcc`, `strategy-evolution`
