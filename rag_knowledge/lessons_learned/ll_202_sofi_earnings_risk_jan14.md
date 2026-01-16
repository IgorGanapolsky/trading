# LL-202: SOFI Earnings Risk - Emergency Close

**ID:** LL-192
**Date:** January 14, 2026
**Severity:** CRITICAL
**Category:** risk-management

## Incident

Short puts on SOFI (strike $24, exp Feb 6) held through earnings date (Jan 30).

## Violation

CLAUDE.md clearly states:
> "SOFI | **AVOID until Feb 1** | Jan 23-30 (earnings Jan 30, IV 55%)"

Position was opened despite this directive.

## Risk Analysis

| Factor | Status |
|--------|--------|
| Position | -2 SOFI260206P00024000 |
| Strike | $24.00 |
| Expiration | Feb 6, 2026 (AFTER earnings) |
| Buying Power | $16.34 |
| Assignment Cost | $4,800 |
| **CAN COVER?** | **NO** |

## Potential Outcomes

1. **If SOFI stays above $24**: Recover ~$157
2. **If SOFI drops to $24**: Lose $400-800
3. **If SOFI drops to $22**: Lose $800-1,200 OR forced liquidation

## Action Taken

1. Created `scripts/emergency_close_sofi.py`
2. Created `.github/workflows/run-emergency-close-sofi.yml`
3. Documented in RAG for future prevention

## Prevention Rules

1. **NEVER** open positions crossing earnings dates
2. **CHECK** CLAUDE.md ticker blackout dates before ANY trade
3. **VERIFY** buying power covers worst-case assignment
4. **EXIT** positions BEFORE earnings blackout begins

## Phil Town Alignment

Rule #1: Don't lose money.

Holding short options through earnings = gambling, not investing. This violates the fundamental principle.

## Tags

`risk-management`, `options`, `earnings`, `critical`, `sofi`
