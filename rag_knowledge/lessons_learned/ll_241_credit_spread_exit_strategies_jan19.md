# LL-241: Credit Spread Exit Strategies - Data-Backed Rules for Win Rate Improvement

**Date**: 2026-01-19
**Category**: Strategy, Options Education, Risk Management
**Severity**: HIGH
**Tags**: `exit-strategy`, `credit-spreads`, `win-rate`, `tastytrade`, `backtest`
**Source**: TastyTrade methodology, Option Alpha backtests, industry best practices

## Summary

Weekend research synthesized best practices for credit spread exit strategies. Key finding: **mechanical exit rules at 50% profit significantly improve win rates** and capital efficiency.

## The Three Exit Rules

### Rule 1: 50% Profit Target (Primary)
- **Action**: Close position when profit reaches 50% of maximum (credit received)
- **Why**: Frees capital for redeployment, reduces exposure to reversals
- **Example**: Sold for $90 credit → Close at $45 debit = $45 profit (50%)
- **Win Rate Impact**: Increases win rate from ~70% to ~80%+ (per TastyTrade research)

### Rule 2: 21 DTE Exit (Time-Based)
- **Action**: Close position at 21 days to expiration regardless of P/L
- **Why**: After 21 DTE, gamma risk increases dramatically; theta decay benefit diminishes
- **Decision Matrix at 21 DTE**:
  - Profit or breakeven → Close immediately
  - Small loss (<50% of max loss) → Close and move on
  - Large loss → Evaluate roll vs. close based on thesis

### Rule 3: 2x Credit Stop Loss (Defensive)
- **Action**: Close if spread price reaches 2x the credit received
- **Example**: Sold for $90 → Close if spread reaches $180 = $90 loss
- **Why**: Limits max loss to ~1:1 risk/reward, prevents catastrophic losses
- **Note**: This is MANDATORY per CLAUDE.md strategy

## Backtest Evidence (Option Alpha SPY Research)

| Strategy | Win Rate | Avg Return | Notes |
|----------|----------|------------|-------|
| Hold to expiration | 65% | Higher per trade | High variance, stress |
| 50% profit target | 80%+ | Lower per trade | Consistent, scalable |
| 75% profit target | 72% | 9% higher RoR | More risk exposure |

**Key Insight**: 50% target has highest win rate; higher targets increase RoR but at cost of consistency.

## Capital Efficiency Math

Scenario: $5,000 account, 45 DTE trades

**Without Early Exit (Hold to Expiration)**:
- Trades per year: ~8 (45 DTE each)
- Capital tied up: Full duration

**With 50% Profit Exit**:
- Average hold time: ~20-25 days
- Trades per year: ~15-18
- Capital turns faster = more opportunity for profits

## Implementation Checklist

1. [ ] Set GTC limit order at 50% profit immediately after entry
2. [ ] Calendar reminder at 21 DTE for position review
3. [ ] Stop-loss alert at 2x credit
4. [ ] Log exit reason for every trade (profit target, time, stop)

## Our System Alignment

From CLAUDE.md:
> **Expiration**: 30-45 DTE, close at 50% max profit (improves win rate to ~80%)
> **Stop-loss**: Close at 2x credit received ($120 max loss) - MANDATORY

This lesson confirms our strategy aligns with industry best practices.

## Action Items

1. Ensure trading system automatically sets limit orders at 50% profit
2. Add 21 DTE monitoring to position management
3. Track exit reasons in trade history for optimization

## Sources

- [TastyTrade Short Put Vertical Spread](https://tastytrade.com/learn/options/short-put-vertical-spread/)
- [Option Alpha SPY Backtest](https://optionalpha.com/blog/spy-put-credit-spread-backtest)
- [Data Driven Options - Credit Put Spread](https://datadrivenoptions.com/strategies-for-option-trading/favorite-strategies/credit-put-spread/)
- [Options Auto Trader - Exit Rules](https://optionsautotrader.medium.com/key-exit-rules-for-higher-win-rates-credit-spreads-course-88f4f01c65ce)

## Prevention/Future Learning

- Always have exit plan before entry
- Trust the backtest data over emotions
- Capital efficiency > maximum profit per trade
