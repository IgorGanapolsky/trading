---
layout: post
title: "Lesson Learned #080: Dialogflow Trade Query Detection Fix"
date: 2026-01-05
---

# Lesson Learned #080: Dialogflow Trade Query Detection Fix

**ID**: LL-080
**Date**: January 5, 2026
**Severity**: HIGH
**Category**: System Integration, Dialogflow, RAG

## The Incident

User asked Dialogflow: "How much money we made today?"

Dialogflow responded with lessons learned (ll_023, ll_074) about past incidents instead of actual portfolio P/L data.

## Root Cause

1. **Missing Keywords**: `is_trade_query()` function lacked common money-related words: "money", "made", "earn", "earned", "today", "balance", "account", "equity", "gains", "returns"

2. **No Fallback**: When ChromaDB had no trade history, webhook fell back to lessons RAG instead of reading current state from `system_state.json`

## The Fix (PR #1071)

1. Added 9 new trade keywords to `is_trade_query()`:
   - money, made, earn, earned, today, gains, returns, equity, balance, account

2. Added `get_current_portfolio_status()` function that reads from `system_state.json`

3. When trade query detected but no trades found → return formatted portfolio status:
   ```
   📊 Current Portfolio Status (Day 50/90)
   
   **Live Account:**
   - Equity: $30.00
   - Total P/L: $0.00 (0.00%)
   
   **Paper Account (R&D):**
   - Equity: $101,083.86
   - Total P/L: $1,083.86 (1.08%)
   - Win Rate: 80.0%
   ```

## Prevention

1. **Keyword Coverage**: Always test query detection with natural language variations
2. **Graceful Fallbacks**: Always have a data source fallback (system_state.json) when primary (ChromaDB) is empty
3. **Test Coverage**: Added 6 new tests for trade query detection and portfolio status (PR #1074)

## Evidence

- PR #1071: https://github.com/IgorGanapolsky/trading/pull/1071
- PR #1074: https://github.com/IgorGanapolsky/trading/pull/1074
- Tests: All 24 tests passing

## Keywords

dialogflow, trade query, money, portfolio, system_state, fallback, webhook
