# Lesson Learned #090: North Star Must Scale with Capital

**Date**: January 6, 2026
**Severity**: CRITICAL
**Category**: Strategy, Capital Management

## Summary

The $100/day North Star target is IMPOSSIBLE with $200 capital. This would require 50% daily returns - a guaranteed path to losing money (violating Phil Town Rule #1).

## The Math

| Capital | Required Return for $100/day |
|---------|------------------------------|
| $200 | 50% daily (IMPOSSIBLE) |
| $500 | 20% daily (EXTREMELY RISKY) |
| $1,000 | 10% daily (VERY RISKY) |
| $2,000 | 5% daily (AGGRESSIVE) |
| $5,000 | 2% daily (REALISTIC) |

## Realistic Targets by Capital Tier

| Capital | Daily Target | Strategy | Return % |
|---------|--------------|----------|----------|
| $200 | $5 | Single CSP on SPY | 2.5% |
| $500 | $15 | 2 CSPs or 1 Iron Condor | 3.0% |
| $1,000 | $30 | Wheel strategy on SPY | 3.0% |
| $2,000 | $60 | Multiple wheels + 0DTE | 3.0% |
| $5,000 | $100 | Full Phil Town portfolio | 2.0% |

## Phil Town Rule #1 Reminder

> "Rule #1: Don't lose money. Rule #2: Don't forget Rule #1."

Chasing unrealistic returns is the fastest way to LOSE money.

## Accelerated Path to $100/day

To reach the capital needed for $100/day:

| Daily Deposit | Days to $200 | Days to $2,000 | Days to $5,000 |
|---------------|--------------|----------------|----------------|
| $10 (current) | 17 | 197 | 497 |
| $20 | 9 | 99 | 249 |
| $50 | 4 | 40 | 100 |
| $100 | 2 | 20 | 50 |

**Recommendation**: Increase deposits to $50/day to reach trading capital in ~40 days.

## Changes Made

1. Updated `system_state.json` with tiered North Star targets
2. Added Phil Town strategy configuration to paper account
3. Created accelerated deposit plan options
4. Paper account will validate strategy before live deployment

## Key Insight

The paper account ($101K) should be used to:
- Test Phil Town Rule #1 strategies
- Build 30+ trade track record
- Validate 70%+ win rate
- THEN deploy proven strategy to live account

## Tags

north_star, capital_requirements, phil_town, rule_1, realistic_targets
