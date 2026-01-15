# LL-216: Root Cause Analysis - Why $5K Lost While $100K Won

## Date: January 15, 2026
## Loss: -$40.74 (-0.81%)
## Verdict: OPERATOR ERROR + SYSTEM GAPS

## The Simple Answer
**$100K used SPY with defined risk. $5K used SOFI with naked puts.**

## Evidence Table

| Factor | $100K Account (Worked) | $5K Account (Failed) |
|--------|------------------------|----------------------|
| Ticker | SPY, AMD | SOFI ❌ |
| Strategy | Iron Condors, Spreads | Naked Puts ❌ |
| Position Size | ~5% per trade | 96% of account ❌ |
| Defined Risk | Yes (spreads) | No (unlimited) ❌ |
| Earnings | Avoided blackouts | During SOFI blackout ❌ |

## Specific Trade That Lost Money

**January 13-14, 2026:**
- Bought SOFI shares + sold 2 naked puts
- Position grew to 96% of account ($4,800 at risk)
- CEO emergency intervention required
- Realized loss: -$40.74

## Rule #1 Violations

1. 96% position size (max allowed: 5%)
2. Naked put (required: spread with defined risk)
3. SOFI ticker (allowed: SPY/IWM only)
4. Earnings blackout violation (SOFI earns Jan 30)
5. Doubled down while losing
6. No stop-loss defined

## System Gaps Fixed

### 1. Risk Monitor Was Non-Functional
```python
# BEFORE: Always returned False (no stop-loss)
return False, "Position within risk limits"

# AFTER: Implements 2x credit stop-loss
if current_loss >= 2 * credit_received:
    return True, "2x credit stop-loss triggered"
```

### 2. Win Rate Tracking Missing
- Now tracks: win rate %, avg win, avg loss, profit factor
- Thresholds per CLAUDE.md:
  - <75%: Reassess (not profitable)
  - 75-80%: Marginally profitable
  - 80%+: Profitable, scale after 90 days

## Why RAG Lessons Weren't Applied

The $100K lessons were extracted AFTER the SOFI failure:
- Jan 13-14: SOFI trade executed
- Jan 14-15: Analysis created lessons LL-196, LL-203, LL-207, LL-208

The system learned FROM this failure, then fixed CLAUDE.md.

## Prevention

1. Ticker whitelist hardcoded: SPY/IWM only
2. Trade gateway blocks naked options
3. Pre-trade checklist validates all positions
4. 2x credit stop-loss now enforced
5. Win rate tracking active

## Key Insight

The $100K success wasn't luck - it was **SPY with defined risk**.
The $5K failure wasn't bad luck - it was **SOFI with undefined risk**.

Follow the rules. Trade SPY spreads. Stay small.

## Tags
#root-cause #failure-analysis #position-sizing #rule-1
