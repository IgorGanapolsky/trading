# Lesson Learned: Alpaca Paper Trading Options Buying Power Shows $0 Despite Cash Available

**ID**: ll_134_options_buying_power_zero_jan12
**Date**: 2026-01-12
**Severity**: HIGH

## Problem
Alpaca paper trading account shows options_buying_power=$0 even with $5K cash and options_approved_level=3. This blocks new CSP orders.

## Root Cause
Pending sell-to-open orders AND existing short put positions consume buying power as collateral. Paper trading may have margin calculation bugs.

## Solution
1) Check open orders before placing new ones. 2) Cancel stale orders to free buying power. 3) Use credit spreads when buying power is tight. 4) Consider closing existing positions before opening new ones.

## Impact
Blocked BAC, F, and other CSP trades despite STRONG BUY signals.

## Prevention
Add buying_power check BEFORE submitting options orders. Auto-cancel stale orders older than 1 day.
