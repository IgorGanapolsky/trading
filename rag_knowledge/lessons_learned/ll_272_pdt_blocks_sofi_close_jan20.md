# LL-272: PDT Protection Blocks SOFI Position Close

**Date**: 2026-01-20
**Category**: Trading Compliance, Risk Management
**Severity**: HIGH

## The Problem

SOFI260213P00032000 (short put) cannot be closed due to PDT (Pattern Day Trading) protection.

**Error**: `{"code":40310100,"message":"trade denied due to pattern day trading protection"}`

## Root Cause

1. Account is under $25K (~$5,069)
2. Account has accumulated 4+ day trades in the past 5 business days
3. PDT rules prevent ANY additional day trades until one falls off

## Impact

- SOFI position remains open, violating "SPY ONLY" mandate
- Position has -$80 unrealized loss
- System compliance checks will fail until position is closed
- Cannot execute new credit spreads until SOFI is closed

## Resolution

**Option 1**: Wait for a day trade to fall off (5 business days from oldest day trade)
**Option 2**: Deposit funds to reach $25K (removes PDT restriction)
**Option 3**: Accept the loss and let the option expire worthless (Feb 13, 2026)

## Prevention

1. **Check day trade count BEFORE opening positions** - query Alpaca API for day trade status
2. **Never open non-SPY positions** - this was the original violation
3. **Close positions on different days from opening** - avoid same-day round trips
4. **Track day trade count in system_state.json** - monitor approaching limits

## Alpaca PDT Rules

- Applies to accounts < $25K
- Day trade = open and close same security same day
- 4+ day trades in 5 business days = PDT flagged
- Flagged accounts cannot day trade until:
  - A day trade falls off (5 business days)
  - Account reaches $25K equity

## Tags

`pdt`, `compliance`, `sofi`, `options`, `risk-management`
