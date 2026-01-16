# LL-197: SOFI Ticker Blackout Violation

**ID**: LL-197
**Date**: January 14, 2026
**Severity**: CRITICAL
**Category**: Configuration / Risk Management

## What Happened
Trading workflow was configured to execute credit spreads and CSPs on SOFI, despite CLAUDE.md explicitly stating SOFI was on blackout until Feb 1 (earnings Jan 30, IV 55%).

This caused:
1. Workflow failures when SOFI options couldn't be found or executed
2. Zero trades executing despite workflow "success"
3. $40.74 realized loss from emergency SOFI position closure

## Root Cause
Hardcoded ticker lists in `.github/workflows/daily-trading.yml`:
- Line 1033: `TICKERS="SOFI F BAC"` (credit spreads)
- Line 1053: `for TICKER in SOFI PLTR F BAC AMD SPY` (CSPs)
- Line 202: `--symbol SPY --symbol SOFI --symbol AMD --symbol PLTR` (RAG query)
- `execute_credit_spread.py` default: `--symbol default="SOFI"`

## Resolution
PR #1796 removed SOFI from all ticker lists:
- Credit spreads: `SPY IWM F`
- CSPs: `SPY IWM F T PLTR AMD`
- RAG query: `SPY IWM AMD PLTR`
- Default symbol: `SPY`

## Prevention
1. **ALWAYS cross-reference CLAUDE.md ticker hierarchy before adding tickers**
2. **Use dynamic blackout checking** - read from CLAUDE.md or config, not hardcoded
3. **Add pre-trade validation** - check if ticker is in blackout period
4. **CI check** - validate workflow ticker lists against CLAUDE.md

## Phil Town Rule #1 Impact
Earnings blackout exists to prevent losses from high-IV events. Violating blackout = violating Rule #1.

## Linked PRs
- PR #1796 - Fix: Remove SOFI from tickers until Feb 1
