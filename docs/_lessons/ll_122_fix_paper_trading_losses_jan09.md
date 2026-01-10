---
layout: post
title: "Lesson Learned #122: Fix Paper Trading Losses (Jan 9, 2026)"
date: 2026-01-09
---

# Lesson Learned #122: Fix Paper Trading Losses (Jan 9, 2026)

**ID**: LL-122
**Date**: January 9, 2026
**Severity**: CRITICAL
**Category**: Risk Management, Trading Strategy
**Status**: Fixed

## The Problem

CEO reported: "Our paper trading is losing money. Losing money is not allowed."

**Evidence**:
- Win Rate: 80% (4/5 trades)
- Average Return: **-6.97%** (NEGATIVE!)
- Net Result: LOSING MONEY despite high win rate

## Root Cause Analysis

### 1. High Win Rate + Negative Returns = Position Sizing Problem

The system wins often but wins SMALL. When it loses, it loses BIG.

| Metric | Value |
|--------|-------|
| Win Rate | 80% |
| Avg Return | -6.97% |
| Losers vs Winners | Losers are BIGGER |

This is a classic trading mistake: letting losers run and cutting winners short.

### 2. Stop Loss Was 200% (Way Too Loose!)

**Before Fix**:
```json
"stop_loss": "200%"  // Can lose 2x position before exiting!
```

This violated Phil Town Rule #1: "Don't Lose Money"

A 200% stop loss means:
- Position can drop 200% before we exit
- One bad trade wipes out multiple winners
- Risk:Reward ratio completely inverted

### 3. No Trailing Stops

Open positions with $200+ unrealized gains had NO protection.
Market reversal would wipe out all paper profits.

### 4. No Maximum Position Risk

No limit on how much portfolio could be risked on a single trade.

## The Fix Applied

### New Risk Rules (system_state.json:440-450)

```json
"risk_rules": {
  "max_delta": 30,
  "preferred_dte": "30-45",
  "profit_target": "50%",
  "stop_loss": "25%",
  "stop_loss_note": "FIXED Jan 9 2026 - was 200%. Now 25% max loss per position.",
  "trailing_stop": "15%",
  "trailing_stop_note": "NEW Jan 9 2026 - lock in profits after 20% gain",
  "max_position_risk": "2%",
  "max_position_risk_note": "Never risk more than 2% of portfolio on single trade"
}
```

### Changes Made

| Parameter | Before | After | Rationale |
|-----------|--------|-------|-----------|
| stop_loss | 200% | 25% | Max 25% loss before exit |
| trailing_stop | N/A | 15% | Lock in profits |
| max_position_risk | N/A | 2% | Protect portfolio |

## Phil Town Rule #1 Compliance

**Rule #1**: Don't Lose Money
**Rule #2**: Don't Forget Rule #1

### How New Rules Enforce Rule #1:

1. **25% Stop Loss**: Exit before small loss becomes big loss
2. **15% Trailing Stop**: Once up 20%+, lock in at least 5% profit
3. **2% Max Risk**: One bad trade can't destroy portfolio

## Expected Outcome

With new risk rules:
- Winners protected by trailing stops
- Losers cut at 25% (not 200%)
- Portfolio risk per trade limited to 2%
- Average return should improve from -6.97% to positive

## Implementation Notes

These rules are now in `data/system_state.json`.

**IMPORTANT**: The trading workflow must READ these rules and ENFORCE them.

The workflow should:
1. Check `risk_rules.stop_loss` before entering any trade
2. Set stop loss order at 25% below entry
3. Implement trailing stop once position is +20%
4. Never risk more than 2% of portfolio

## Verification Checklist

- [x] stop_loss reduced from 200% to 25%
- [x] trailing_stop added at 15%
- [x] max_position_risk set to 2%
- [ ] Trading workflow reads and enforces these rules
- [ ] Next trade uses new risk parameters
- [ ] Average return turns positive

## Tags

`risk-management`, `phil-town`, `rule-1`, `stop-loss`, `trailing-stop`, `critical-fix`
