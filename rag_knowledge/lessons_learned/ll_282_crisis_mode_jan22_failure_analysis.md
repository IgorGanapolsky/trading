# LL-282: Crisis Mode Failure Analysis - Jan 22, 2026

**ID**: LL-282
**Date**: 2026-01-22
**Severity**: CRITICAL
**Category**: System Failure, Position Management, Trust Breach

## Executive Summary

The AI trading system failed catastrophically over three days (Jan 20-22, 2026):
- Accumulated 8 contracts of SPY260220P00658000 when max should be 4
- Unrealized loss grew to -$1,472 (35% of account equity)
- All attempts to close positions blocked by Alpaca API bug + PDT restriction
- CEO lost trust in the system

## What Went Wrong

### Root Cause 1: Individual vs Cumulative Risk
The trade gateway checked individual trade risk (5% max) but NOT cumulative exposure.
- Trade 1: $248 risk (5% of $4,986) - APPROVED
- Trade 2: $248 risk (5% of $4,986) - APPROVED
- Trade 3: $248 risk (5% of $4,986) - APPROVED
- ...continued until 8 contracts ($1,984 risk = 40% exposure)

**Fix Applied**: `_check_cumulative_position_risk()` added to trade_gateway.py

### Root Cause 2: No Circuit Breaker
When positions started bleeding, the system continued evaluating new trades.
There was no hard stop that said "STOP - portfolio in crisis mode."

**Fix Applied**: CIRCUIT BREAKER check at start of evaluate() method:
1. TRADING_HALTED flag file check
2. Block when unrealized loss > 25% of equity
3. Block when option positions > 4

### Root Cause 3: Over-reliance on RAG
CEO quote: "Our system has been in crisis mode for three days. I don't trust you."
The system was designed to "learn from RAG" but:
- RAG lessons are advisory, not preventive
- Hard-coded risk limits are the actual safety net
- RAG can't override code that doesn't exist

## Timeline

| Date | Event | P/L |
|------|-------|-----|
| Jan 20 | First excess position opened | -$200 |
| Jan 21 | More positions accumulated, no closure | -$800 |
| Jan 22 | 8 contracts, PDT + API bug blocks close | -$1,472 |

## Fixes Implemented

1. **Circuit Breaker in Trade Gateway** (trade_gateway.py:578-630)
   - Hard stop before any position-opening trade
   - Checks TRADING_HALTED flag file
   - Blocks when unrealized loss > 25% of equity
   - Blocks when option positions > 4

2. **TRADING_HALTED Flag** (data/TRADING_HALTED)
   - Manual halt mechanism
   - Must be explicitly removed to resume trading

3. **Scheduled Position Close** (.github/workflows/scheduled-position-close.yml)
   - Runs Jan 23, 9:45 AM ET
   - Attempts close_position() then market order fallback

4. **Daily Trading Disabled** (.github/workflows/daily-trading.yml:401)
   - `if: false` prevents any new trading
   - Must be manually re-enabled

## Prevention Measures

1. **Never trust advisory systems for risk control**
   - RAG lessons = learning
   - Hard-coded limits = safety
   - Both are needed

2. **Cumulative risk must be checked**
   - Individual trade risk is not enough
   - Sum existing + new position risk

3. **Circuit breakers must exist**
   - When portfolio is bleeding, STOP
   - Don't try to trade your way out

4. **Trust must be earned**
   - CEO lost trust due to 3 days of crisis
   - System must prove reliability over time

## Recovery Plan

1. **Jan 23**: Close all bleeding positions via scheduled workflow
2. **Jan 24-27**: Monitor for fills and updated P/L
3. **Jan 28**: If portfolio healthy, consider removing TRADING_HALTED
4. **Feb**: 30-day observation period before resuming live trading

## Metrics to Track

- Days since last position accumulation incident: 0 (reset today)
- Maximum positions opened in a day: Should be 4 (1 iron condor)
- Circuit breaker triggers: Track for false positives

## Tags
`critical`, `trust-breach`, `circuit-breaker`, `risk-management`, `position-accumulation`, `pdt`, `crisis-mode`
