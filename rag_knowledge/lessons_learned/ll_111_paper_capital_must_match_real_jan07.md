# Lesson Learned #111: Paper Trading Capital Must Be Realistic

**Date**: January 7, 2026
**Category**: Strategy / Risk Management
**Severity**: CRITICAL
**Source**: CEO Insight

## The Problem

Paper trading account was configured with $100,000 starting balance while real account target is $500 (growing to $5,000 by June 2026).

This 200x mismatch creates a **fundamentally false simulation** because:

1. **Strategy Mismatch**: Paper tests AMD $200 CSPs (needs $20k collateral) - impossible with real capital
2. **False Confidence**: 80% win rate on $100k means nothing when testing impossible strategies
3. **Diversification Illusion**: Paper holds 4-5 positions; real can hold 1-2 max

## The Correct Approach

Paper trading capital should match **next realistic milestone**, not current capital:

| Milestone | Target Date | Paper Capital | Valid Strategies |
|-----------|-------------|---------------|------------------|
| $500 | Feb 2026 | $500 | F/SOFI $5 CSPs only |
| $1,000 | Mar 2026 | $1,000 | INTC/BAC $10 CSPs |
| **$5,000** | Jun 2026 | **$5,000** | Quality stocks $50 CSPs |
| $50,000 | Future | $50,000 | Full strategy suite |

## Recommended Paper Account: $5,000

Why $5,000 is the sweet spot:
1. **Realistic 6-month target** - achievable with $10/day deposits + compounding
2. **Tests real strategies** - CSPs on quality stocks ($50 strike max)
3. **Forces discipline** - 1-2 positions max, proper sizing
4. **North Star path** - builds toward $100/day goal (needs ~$50k)

## What's Wrong with Current $100k Paper

| What Paper Tests | Collateral Needed | When Realistic? |
|------------------|-------------------|-----------------|
| AMD $200 CSP | $20,000 | 2+ years away |
| SPY $660 CSP | $66,000 | Never (unrealistic) |
| INTC $35 CSP | $3,500 | ~6 months |

## Action Items

- [ ] Reset Alpaca paper account to $5,000
- [ ] Close current paper positions
- [ ] Only test CSPs with strikes ≤ $50
- [ ] Limit to 1-2 positions maximum
- [ ] Re-run backtests with $5,000 starting capital

## Key Insight

"Test strategies you'll ACTUALLY USE when you reach the next milestone, not strategies that require 200x more capital than you'll ever have."

The goal isn't to paper trade at current capital ($30) - that's too restrictive to learn anything useful. The goal is to paper trade at the **next achievable tier** ($5,000) to validate strategies before deploying real capital.

## Tags
#paper-trading #capital-alignment #risk-management #simulation-fidelity #ceo-insight
