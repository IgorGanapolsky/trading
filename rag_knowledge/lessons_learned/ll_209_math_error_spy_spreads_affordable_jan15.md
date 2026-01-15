# LL-209: Critical Math Error - SPY Credit Spreads Were Always Affordable

**Date**: 2026-01-15
**Category**: Strategy, Math Error, Post-Mortem
**Severity**: CRITICAL

## The Error

On Day 74, we believed SPY was "too expensive" for the $5K account and switched to SOFI.

This was **WRONG**.

## The Math We Got Wrong

| What We Thought | Reality |
|-----------------|---------|
| SPY shares: $58,000 needed | TRUE but irrelevant |
| SPY CSP: $58,000 needed | FALSE - only for naked puts |
| SPY credit spread: ??? | **$500 collateral** |

## Credit Spread Collateral Formula



For a $5-wide SPY put credit spread:


**We could have traded SPY credit spreads with $500 the entire time.**

## Why We Switched to SOFI

From LL-158 (Day 74 Emergency Fix):
> "Wrong target asset: guaranteed_trader.py targeted SPY ($580/share) instead of SOFI (~$15/share)"

This reasoning only applies to:
- Buying shares outright
- Naked cash-secured puts

It does NOT apply to credit spreads, which the $100K account was using\!

## The Cascade of Errors

1. **Misunderstood collateral** → Thought SPY was unaffordable
2. **Switched to SOFI** → Individual stock with earnings risk
3. **Used naked CSP** → Instead of defined-risk spread
4. **96% position size** → Gambling, not trading
5. **Ignored blackout** → Traded through earnings period
6. **Lost $65** → When forced to close

## The Irony

The $100K account was profitable doing SPY credit spreads.
We had $5K - enough for 10 SPY credit spreads.
We never tried a single one.

## Prevention

1. **Always calculate collateral** before declaring something "too expensive"
2. **Credit spreads ≠ naked positions** - different capital requirements
3. **When in doubt, check the math** - don't assume

## Key Lesson

**The winning strategy was always affordable. We just didn't understand the math.**
