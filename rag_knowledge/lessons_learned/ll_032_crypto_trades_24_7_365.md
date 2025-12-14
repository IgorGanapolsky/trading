# Lesson Learned #032: Crypto Markets Trade 24/7/365

**Date**: December 14, 2025
**Category**: Trading / Operational
**Severity**: CRITICAL (causes missed trading opportunities)
**Status**: RESOLVED

## Executive Summary

Critical error: Claimed "markets closed (weekend)" when crypto trades 24/7/365 including weekends. This misconception must NEVER be repeated.

## Problem

On December 14, 2025 (Saturday), when asked "how much money did we make today?", the response was:

> "$0 today - markets are closed (weekend)"

This is **WRONG**. Crypto markets (BTC, ETH, etc.) trade 24 hours a day, 7 days a week, 365 days a year. Weekends are NOT closed for crypto.

## Root Cause

1. **Knowledge gap**: Not consistently remembering that crypto trades on weekends
2. **Assumption error**: Defaulting to "markets closed on weekend" without checking asset class
3. **Missing reinforcement**: The rule was in documentation but not in Critical Rules section

## Market Hours Reference

| Asset Class | Trading Hours | Trading Days |
|-------------|---------------|--------------|
| **Crypto (BTC/ETH)** | 24 hours | Every day (including weekends) |
| **US Equities** | 9:30 AM - 4:00 PM ET | Monday - Friday only |
| **US Futures** | Nearly 24/5 | Sunday 6pm - Friday 5pm ET |
| **Forex** | 24/5 | Sunday 5pm - Friday 5pm ET |

## Solution

1. **Added Critical Rule #5** to CLAUDE.md:
   ```markdown
   5. **CRYPTO TRADES 24/7/365** - Weekends included! Always check crypto positions/P/L.
   ```

2. **Added Rule #10** to MANDATORY_RULES.md with detailed table

3. **Created this lesson learned** for RAG retrieval

## Correct Behavior

When asked about money/P/L on weekends:
- **WRONG**: "Markets are closed today (weekend)"
- **RIGHT**: "Let me check crypto positions and P/L" → then query Alpaca API

## Weekend Crypto Trading Workflow

The system HAS automated weekend crypto trading:
- Workflow: `.github/workflows/weekend-crypto-trading.yml`
- Schedule: Saturdays and Sundays at 10:00 AM ET
- Budget: $25/day crypto (daily including weekends)

## Additional Context

Today's weekend crypto trading workflow ran at 15:00:58 UTC but **failed** at the "Execute weekend crypto trading" step. The infrastructure exists - the execution failed for a different reason (script error).

## Prevention

1. **Before answering P/L questions**: Check what day it is, remember crypto trades 24/7
2. **On weekends**: Explicitly check crypto positions via Alpaca API
3. **Default assumption**: There is ALWAYS something trading (crypto never stops)

## Tags

#crypto #market-hours #weekend #critical-rule #trading-fundamentals
