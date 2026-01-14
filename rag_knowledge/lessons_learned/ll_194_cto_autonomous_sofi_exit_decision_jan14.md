# LL-194: CTO Autonomous SOFI Exit Decision

**Date**: January 14, 2026
**Severity**: HIGH
**Category**: Risk Management, Autonomous Decision

## Context
CEO directive: "Be autonomous and make the decisions."

## Research Findings
Deep research conducted on January 2026 market conditions:

### SOFI Earnings Risk Analysis
| Factor | Value | Source |
|--------|-------|--------|
| Earnings Date | Jan 30, 2026 | NASDAQ, MarketBeat |
| Expected Move | 12.2% ($3.22) | Barchart options pricing |
| Current IV | 55% | AlphaQuery |
| Position | -2 puts @ $24, exp Feb 6 | System state |
| Stock Position | 24.7 shares @ $27.09 | System state |

### Problem
- Feb 6 expiration is AFTER Jan 30 earnings
- 12.2% expected move = stock could drop to $23.21 (put ITM)
- Assignment risk: $4,800 (96% of portfolio!)
- CLAUDE.md blackout rule: "AVOID until Feb 1"

## CTO Decision
**EXIT ALL SOFI POSITIONS ON JAN 14 MARKET OPEN**

### Actions Taken
1. Updated `scheduled-close-put.yml` to close ALL SOFI (not just put)
2. Changed condition: Close regardless of P/L (avoid earnings risk)
3. Updated CLAUDE.md strategy:
   - ATM → 30-delta (Phil Town margin of safety)
   - F,SOFI,T → SPY,IWM first (best liquidity)
   - $100 premium target → $60-80 (realistic for VIX 15)

## Strategy Revisions
| Before | After | Reason |
|--------|-------|--------|
| Sell ATM put | Sell 30-delta put | Phil Town Rule #1 compliance |
| F, SOFI, T targets | SPY, IWM priority | Best liquidity, no individual earnings |
| 2-3 spreads/week | 1 spread at a time | 5% max risk per trade |
| $100 premium | $60-80 premium | VIX at 15 = low IV environment |

## Expected Outcome
- Lock in SOFI gains (~$40 total P/L)
- Avoid 12.2% earnings volatility
- Capital freed for SPY/IWM spreads starting Jan 15

## Lesson for RAG
- Always check option expiration vs earnings dates
- 30-delta spreads provide margin of safety
- SPY/IWM have no individual earnings risk
- Exit positions 2+ weeks before earnings, not just during blackout

## Tags
`credit-spreads`, `sofi`, `earnings`, `risk-management`, `autonomous-decision`, `phil-town`
