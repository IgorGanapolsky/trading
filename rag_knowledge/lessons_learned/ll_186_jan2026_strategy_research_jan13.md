# Strategic Research: January 2026 Credit Spread Optimization

**ID:** LL-186
**Date:** January 13, 2026
**Severity:** CRITICAL
**Category:** strategy-research

## Research Summary

Deep research conducted on January 2026 best practices for credit spreads on small accounts ($5K).

## Key Findings

### 1. Position Sizing (CRITICAL)
- **Old**: 10 spreads = 80% account risk (EXCESSIVE)
- **New**: 5 spreads max = 40% account risk (survivable)
- Research shows 5-7 concurrent positions optimal for $5K

### 2. Ticker Selection
- **SPY/IWM** superior to F/SOFI/T due to liquidity
- SOFI: BLACKOUT until Feb 1 (earnings Jan 30, IV at 55%)
- F: Avoid Feb 3-10 (earnings Feb 10)
- T: Safest but lowest premiums (weak moat)

### 3. Strike Selection
- **Old**: ATM puts (zero margin of safety)
- **New**: 30-delta puts (more cushion, lower premium)

### 4. Premium Reality Check
- VIX at 15 = low IV environment
- $100/spread unrealistic; $60-80 is achievable
- Revised weekly target: $350/week (not $1,000)

### 5. Phil Town Conflict
Credit spreads violate Rule #1 (risk $400 to make $80).
Mitigation: Use OTM strikes, strict stops, fewer positions.

## Ticker Analysis

| Ticker | Moat | Management | Rule #1? |
|--------|------|------------|----------|
| F | Narrow/Declining | Mixed | Maybe |
| SOFI | Emerging | Strong | Promising |
| T | Weak | Concerning | NO |

## Action Items Implemented

1. Updated CLAUDE.md with revised strategy
2. Changed position limit from 10 to 5
3. Added earnings blackout calendar
4. Prioritized SPY/IWM over individual stocks

## Prevention

Before any trade:
1. Check earnings calendar (avoid 7 days before)
2. Verify IV environment (VIX level)
3. Confirm position count < 5
4. Use 30-delta strikes (not ATM)

## Tags

`strategy`, `research`, `credit-spreads`, `position-sizing`, `earnings-risk`
