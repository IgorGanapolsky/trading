# Lesson Learned #111: Paper Trading Capital Must Match Real Account

**Date**: January 7, 2026
**Category**: Strategy / Risk Management
**Severity**: CRITICAL
**Source**: CEO Insight

## The Problem

Paper trading account was configured with $100,000 starting balance while real account target is $500.

This creates a **fundamentally false simulation** because:

1. **Strategy Mismatch**: Paper account can sell AMD $200 strike CSPs (requires ~$20,000 collateral). Real account with $500 can ONLY sell $5 strike CSPs (F, SOFI).

2. **Position Sizing Doesn't Translate**:
   - Paper: 10% position = $10,000
   - Real: 10% position = $50
   - Completely different risk dynamics

3. **False Confidence**: 80% win rate on $100k paper account means nothing when strategies are impossible to replicate with $500.

4. **Diversification Illusion**: Paper account can hold 5+ positions simultaneously. Real account can hold 1 CSP max.

## Current vs Required

| Metric | Current Paper | Should Be |
|--------|---------------|-----------|
| Starting Capital | $100,000 | $500 |
| Max Strike Price | $200+ | $5 |
| Eligible Underlyings | Any | F, SOFI only |
| Positions at Once | 4-5 | 1 |
| Commission Impact | Negligible | ~1% per trade |

## The Fix

Paper trading should simulate EXACTLY what we can do with real capital:

1. **Start paper account at $500** (not $100,000)
2. **Only allow $5 strike CSPs** (F, SOFI)
3. **Single position maximum** until capital grows
4. **Account for commission impact** (~$0.65/contract = 0.13% on $500)

## Validation Test

Before going live, paper trading must prove profitability with SAME constraints:
- Same capital level
- Same position limits
- Same underlying universe
- Same strategy parameters

## Key Insight

"Simulating with $100,000 when trading with $500 is like practicing golf with unlimited mulligans then expecting to score the same in a real tournament."

## Action Items

- [ ] Reset paper account to $500 starting balance
- [ ] Limit paper trading to F/SOFI $5 strike CSPs only
- [ ] Re-run win rate calculations with constrained strategy
- [ ] Update backtest configs to use $500 starting capital

## Tags
#paper-trading #capital-alignment #risk-management #simulation-fidelity #ceo-insight
