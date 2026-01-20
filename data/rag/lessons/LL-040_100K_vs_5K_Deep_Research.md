# LL-040: Deep Research - $100K Success vs $5K Failure

## Date: January 20, 2026
## Author: CTO (Claude)
## Status: CRITICAL LESSON

## Executive Summary

**The $100K account made money. The $5K account lost money.**

| Factor | $100K Account | $5K Account | Verdict |
|--------|--------------|-------------|---------|
| Ticker | SPY, AMD | SOFI | ❌ VIOLATION |
| Strategy | Iron Condors, Spreads | Naked Puts | ❌ VIOLATION |
| Position Size | ~5% per trade | 96% of account | ❌ CRITICAL |
| Risk | Defined (spreads) | Unlimited (naked) | ❌ VIOLATION |
| Earnings | Avoided blackouts | During SOFI earnings | ❌ VIOLATION |

## $100K Evidence (Dec 10, 2025)

Single day premium collection: **+$12.28**
- AMD260116P00200000 SELL @ $5.90
- SPY260123P00660000 SELL @ $6.38
- Treasury ladder (BIL, TLT, SHY, IEF) for hedge

## $5K Failure (Jan 13-14, 2026)

SOFI Disaster - ALL rules violated:
1. SOFI instead of SPY/IWM (ticker whitelist)
2. Naked puts, no spread (undefined risk)
3. 96% position size ($4,800) - max was 5% ($250)
4. SOFI earnings Jan 30 (blackout violation)
5. Doubled down while losing
6. No stop-loss defined

**Result: -$40.74 (-0.81%) + CEO emergency intervention**

## Root Cause

The $100K lessons weren't extracted until AFTER the SOFI failure.
The system learned FROM the failure, not BEFORE it.

## Current Problem: Overcorrection

After SOFI, we swung from reckless to paralyzed:
- Before: 96% position size → After: 0% trades executing
- Before: Naked puts → After: System blocked by own safety gates
- Before: Single stock bet → After: Over-positioned, can't add more
- Before: No rules → After: Too many rules blocking action

**Phil Town Rule #1 is "Don't Lose Money" - but Rule #2 is "Make Money"**

## Recommendations

1. Close excess spreads to meet position limit
2. Reset to 1 iron condor per CLAUDE.md
3. Loosen entry criteria (currently too restrictive)
4. Add AMD back as secondary underlying
5. Track daily premium vs $12/day baseline
6. Target: $6/day on $5K (same 0.12% rate as $100K)

## Tags
#root-cause #100k-analysis #5k-failure #strategy #critical
