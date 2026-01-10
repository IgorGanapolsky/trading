# Lesson Learned #129: Small Account Options Strategies for 2026

**ID**: LL-129
**Date**: January 10, 2026
**Severity**: HIGH
**Category**: strategy, options, small-account, research

## Research Summary

Synthesized from top options trading sources (Jan 10, 2026 weekend research session).

## Key Finding: Credit Spreads > Cash-Secured Puts for Small Accounts

**Problem with CSPs for $5K account:**
- CSPs require enough cash to buy 100 shares if assigned
- F at $10 strike needs $1,000 collateral (20% of account)
- Limited diversification possible

**Better Alternative: Credit Spreads**
- Bull put spreads require significantly less capital
- Defined risk, similar probability of profit
- Can do multiple positions for diversification

## Recommended Strategies for $5K Account

### 1. Credit Spreads (Primary)
- **Vehicles**: SPY, QQQ, IWM (liquid ETFs)
- **Timing**: 15-30 DTE
- **Target**: 30-45% probability ITM (0.30-0.45 delta short strike)
- **Premium rule**: Collect minimum 33% of spread width
  - Example: $5 wide spread = collect at least $1.65

### 2. Iron Condors (Market Neutral)
- Short strikes at 15 delta each side
- ~85% probability of profit
- Good for low-volatility environments

### 3. Poor Man's Covered Call (Capital Efficient)
- Requires only 20-30% of traditional covered call capital
- Buy deep ITM LEAP call (70-80 delta)
- Sell short-term OTM calls against it
- Example: Ford PMCC needs ~$400 vs $1,200 for shares

## Position Sizing Rules

| Rule | Limit |
|------|-------|
| Max risk per position | 5% of account |
| Max portfolio delta dollars | 50% of account |
| Per spread position size | 2-3% |
| Per iron condor | 5% |

## Risk Management

- **Profit target**: 50% of max profit
- **Stop loss**: 100% of credit received (2x risk)
- **Monthly max loss**: 10% of account
- **Focus**: 65%+ probability of profit trades

## Action Items for Our System

1. **Shift from CSPs to credit spreads** for $5K paper account
2. **Update `rule_one_trader.py`** to use bull put spreads
3. **Add position sizing validation** (5% max per trade)
4. **Target SPY/QQQ** instead of individual stocks (more liquid)

## Capital Tier Strategy (Updated)

| Capital | Strategy | Max Position |
|---------|----------|--------------|
| $500-$1K | Single credit spread on SPY | $50 risk |
| $1K-$2K | 2-3 credit spreads | $100 risk each |
| $2K-$5K | Iron condors + spreads | $250 risk each |
| $5K+ | Full wheel strategy | $500 risk each |

## Sources

- [OptionsTradingIQ](https://optionstradingiq.com/best-option-strategies-for-small-accounts/)
- [InsiderFinance Wheel Guide](https://www.insiderfinance.io/resources/complete-guide-to-wheel-options-trading-strategy)
- [SteadyOptions](https://steadyoptions.com/articles/options-strategies-for-small-accounts-r725/)

## Tags

`small-account`, `credit-spreads`, `iron-condors`, `pmcc`, `risk-management`, `2026-research`
