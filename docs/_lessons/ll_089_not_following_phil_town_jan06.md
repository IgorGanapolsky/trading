---
layout: post
title: "Lesson Learned #089: NOT Following Phil Town Rule #1"
date: 2026-01-06
---

# Lesson Learned #089: NOT Following Phil Town Rule #1

**Date**: January 6, 2026
**Severity**: CRITICAL
**Category**: Strategy Violation

## Summary

Deep research revealed that our trading system is **NOT following Phil Town's Rule #1 investing** despite claiming to use his strategy. We are violating the core principle: "Don't lose money."

## Evidence

### What Phil Town Teaches
1. **Rule #1**: Don't lose money
2. **Rule #2**: Don't forget Rule #1
3. **4Ms Framework**: Meaning, Moat, Management, Margin of Safety
4. **Strategy**: Buy wonderful companies at attractive prices
5. **Options**: Sell CSPs on Rule #1 stocks you want to own

### What Our System Actually Does
| Metric | Phil Town | Our System |
|--------|-----------|------------|
| Core Rule | Don't lose money | -3.04% daily avg (LOSING) |
| Stock Selection | 4Ms Framework | None |
| Entry Trigger | Margin of Safety | MACD/RSI signals |
| Options | CSPs on wonderful companies | Random directional bets |
| Win Rate | 70-80% (selling premium) | 80% (fake, only 5 trades) |

## Root Cause

We have Phil Town content in RAG (58 files) but we're NOT using it for trade decisions. The `core_strategy.py` uses MACD/RSI direction trading instead of Phil Town's value + theta approach.

## Impact

- **Financial**: Losing -3.04% daily average
- **Sharpe Ratio**: -7 to -72 (catastrophic)
- **North Star**: Not meeting $100/day target

## Corrective Actions Required

1. Implement 4Ms stock screener
2. Calculate sticker price with margin of safety
3. Switch from buying direction to selling premium (CSPs)
4. Only sell CSPs on stocks that pass 4Ms
5. Use Phil Town RAG for trade decisions

## What Top Traders Do (Jan 2026)

Research shows successful traders:
- Sell 0DTE iron condors (63-67% win rate, 7-37% returns)
- Use Wheel strategy (30-45 DTE, delta -0.30)
- Enter after 1 PM ET for max theta decay
- Position size 10% max buying power

## Links

- Phil Town RAG: `rag_knowledge/books/phil_town_rule_one.md`
- Core Strategy: `src/strategies/core_strategy.py`
- System State: `data/system_state.json`

## Tags

phil_town, rule_1, strategy_violation, losing_money, 4ms_framework
