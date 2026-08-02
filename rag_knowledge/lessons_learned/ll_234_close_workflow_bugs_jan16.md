# LL-234: Close Position Workflow Bugs Discovered

**Date**: 2026-01-16 14:30 ET
**Category**: Bug, Risk Management
**Severity**: HIGH
**Session**: CEO requested position reduction

## Incident Summary

Attempted to close 653/658 spread and orphan put to reduce position sizing from 30% to comply with 5% rule.

## Bugs Discovered

### Bug 1: Loose Symbol Matching

**File**: `.github/workflows/close-put-position.yml`
**Code**: `if symbol in pos.symbol or pos.symbol in symbol`
**Problem**: Input "SPY260220P00658000" matched "SPY" stock because "SPY" is in both strings
**Impact**: Accidentally sold 0.576 SPY shares (~$399) instead of closing option

### Bug 2: Fallback Uses Wrong Side

**Problem**: When close_position() fails (PDT protection), fallback always uses `OrderSide.BUY`
**Impact**: For long positions, this ADDS to position instead of closing
**Result**: SPY260220P00653000 went from 1 to 2 contracts

### Bug 3: No PDT Pre-Check

**Problem**: Workflow does not check PDT status before attempting close
**Impact**: Operations fail silently or use broken fallback

## Outcomes

| Action                   | Result                        |
| ------------------------ | ----------------------------- |
| Close SPY260220P00658000 | ❌ Closed SPY stock instead   |
| Close SPY260220P00653000 | ❌ Added position (now qty=2) |
| Close SPY260220P00660000 | ✅ Success                    |

## Current State (Broken)

- 653/658 spread: 2 long / 1 short (UNBALANCED)
- SPY stock: GONE (accidentally sold)
- Cash increased: $4,761 (was $4,302)

## Required Fixes

1. **Exact symbol matching**: Use `if pos.symbol == symbol` not substring matching
2. **Smart side detection**: Check position qty sign to determine BUY vs SELL
3. **PDT pre-check**: Query account.pattern_day_trader before attempting intraday close
4. **Spread-aware close**: New workflow to close both legs of spread atomically

## Workaround

Use Alpaca dashboard manually to:

1. SELL 1 SPY260220P00653000 (fix broken spread)
2. Monitor PDT status before any intraday closes

## Phil Town Alignment

This incident reinforces Rule #1 - automation bugs can lose money.
Manual verification required until workflows are fixed.

## Related Issues

- GitHub Issue #2033

## Tags

`bug`, `workflow`, `pdt-protection`, `position-management`
