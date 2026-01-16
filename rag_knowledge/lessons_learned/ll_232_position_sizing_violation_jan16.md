# LL-232: Position Sizing Violation - $5-Wide Spreads Exceed 5% Rule

**Date**: 2026-01-16
**Category**: Risk Management, Rule #1
**Severity**: HIGH

## Discovery

During Ralph Mode iteration, CTO discovered current positions violate CLAUDE.md position sizing rules.

## The Violation

| Rule | CLAUDE.md Requirement | Actual |
|------|----------------------|--------|
| Spread Width | $3-wide | **$5-wide** |
| Max Risk | $248 (5% of $4,977) | **$500 per spread** |
| Position Limit | 1 spread at a time | **3 spreads open** |

## Current Positions (All $5-wide)

1. SPY 565/570 put spread - $500 max risk
2. SPY 595/600 put spread - $500 max risk
3. SPY 653/658 put spread - $500 max risk

Total potential exposure: $1,500 (30% of account)

## Why This Matters

Phil Town Rule #1: Don't lose money.

If SPY drops significantly, losing all 3 spreads = $1,500 loss = 30% drawdown.

This contradicts the 5% max position size rule designed to protect capital.

## Mitigating Factors

1. SPY is currently at $693 - all spreads are far OTM
2. Spreads expire Feb 20 (35 DTE) - time for theta decay
3. Current P/L is +$19 (positions are profitable)
4. Stop-loss rules should trigger before max loss

## Action Required

For FUTURE trades:
1. Use $3-wide spreads maximum
2. Max risk = $248 per trade (5% of current equity)
3. Only 1 spread at a time until account grows
4. Close existing positions at 50% profit or 2x loss

## Lesson

Strategy rules exist for a reason. Even profitable positions can violate risk management.

**Better to follow the rules and make less than break the rules and risk more.**
