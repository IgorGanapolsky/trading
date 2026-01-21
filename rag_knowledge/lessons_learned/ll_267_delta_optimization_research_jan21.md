# LL-267: Delta Optimization Research - Validated Strategy Parameters

**Date**: 2026-01-21
**Category**: Strategy Research
**Severity**: HIGH

## Summary

Research confirms our CLAUDE.md iron condor parameters are well-aligned with industry best practices and backtesting data.

## Research Findings

### Option Alpha 0DTE Study (25,000+ trades)
- Iron condors: 63% win rate
- Average return: 7.94%
- Iron condors held to expiration: **94% full winners**
- Trades opened outside first 2 hours: **67% win rate, 37% avg return**

### Options Trading IQ Backtesting (50 trades)
- Properly managed iron condors: **86% success rate**
- Key: Most assume 70%, reality is 86% with proper management

### Optimal Parameters (Research Consensus)
| Parameter | Recommended | Our Setting | Status |
|-----------|-------------|-------------|--------|
| Short delta | 15-20 | 15-20 | ✅ ALIGNED |
| DTE | 30-45 | 30-45 | ✅ ALIGNED |
| Profit target | 50% | 50% | ✅ ALIGNED |
| Exit timing | 21 DTE | 21 DTE | ✅ ALIGNED |
| Premium/Width | ~1/3 | ~1/3 | ✅ ALIGNED |

### IV Environment
- Iron condors work best when IV Rank > 50%
- Target 10-20% ROI per trade
- 65-70% base win rate, 86% with management

## Validation

Our CLAUDE.md strategy is **research-validated**:
- 15-20 delta short strikes
- 30-45 DTE expiration
- 50% profit target OR 21 DTE exit
- $5-wide wings (defined risk)
- SPY only (best liquidity)

## Sources
- Option Alpha: 0DTE Options Study (25k trades)
- Options Trading IQ: Iron Condor Success Rate
- Data Driven Options: Best Delta for Spreads
- QuantStrategy.io: Iron Condor Monthly Income Guide

## Action Items
- [x] Validate current parameters against research
- [x] Document findings in RAG
- [ ] Monitor real trades for deviation from backtested results
- [ ] Consider IV rank filter before trade entry

## Tags
- strategy-validation
- delta-optimization
- iron-condor
- research
