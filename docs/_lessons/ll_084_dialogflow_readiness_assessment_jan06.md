---
layout: post
title: "Lesson Learned #084: Dialogflow Webhook Returning Raw Data Instead of Analysis"
date: 2026-01-06
---

# Lesson Learned #084: Dialogflow Webhook Returning Raw Data Instead of Analysis

**Date**: 2026-01-06
**Severity**: MEDIUM
**Category**: User Experience / Dialogflow Integration

## Incident Summary

When users asked "How ready are we for today's trade?", the Dialogflow webhook returned raw portfolio data (equity, P/L numbers) instead of an actual readiness assessment. This provided no actionable insight - just data dumps.

## Root Cause

The webhook's query routing logic detected "trade" keyword in "today's trade" and routed to the trade/portfolio handler, which only returned raw data without analysis.

## Technical Details

**Before (v2.4.0):**
- Query: "How ready are we for today's trade?"
- Detection: `is_trade_query()` matched "trade" keyword
- Response: Raw portfolio status dump
- User got: Numbers with no context or recommendation

**After (v2.5.0):**
- Added `is_readiness_query()` detection (priority over trade queries)
- Added `assess_trading_readiness()` - 5-point assessment:
  1. Market status (open/closed/pre-market)
  2. System state freshness
  3. Capital levels (paper + live)
  4. Backtest validation status
  5. Win rate performance
- Added `format_readiness_response()` - actionable output
- Returns: READY/CAUTION/NOT_READY with specific recommendations

## Code Location

- `src/agents/dialogflow_webhook.py` (v2.4.0 -> v2.5.0)
- `tests/test_dialogflow_webhook.py` (17 new tests added)

## Prevention Measures

1. **Query Priority**: Readiness queries now take priority over generic trade queries
2. **Detection Keywords**: Added comprehensive keyword list for readiness detection
3. **Test Coverage**: 100% test coverage for all new functions
4. **Actionable Output**: Always provide recommendation, not just data

## Key Insight

Dialogflow agents should provide **analysis**, not just **data**. When users ask "how ready are we?", they want a verdict, not a spreadsheet.

## Tags

- dialogflow
- webhook
- user-experience
- trading-readiness
- query-routing
