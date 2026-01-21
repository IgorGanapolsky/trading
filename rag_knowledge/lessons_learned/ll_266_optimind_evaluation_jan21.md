# LL-266: OptiMind Evaluation - Not Relevant to Our System

**Date**: 2026-01-21
**Category**: Resource Evaluation
**Verdict**: FLUFF

## Summary

OptiMind is a 20B parameter model from Microsoft Research that converts natural language to MILP (Mixed Integer Linear Programming) formulations. Evaluated for potential use in our trading system.

## Why It's Not Relevant

1. **We have no optimization problems** - Our strategy is deterministic (SPY iron condors, 15-20 delta, 30-45 DTE)
2. **Position sizing is arithmetic** - `5% of equity` is not an optimization problem
3. **Single ticker strategy** - SPY ONLY per CLAUDE.md; no portfolio allocation needed
4. **Simplicity is a feature** - Phil Town Rule #1 achieved through discipline, not optimization
5. **Massive overhead** - 20B model for zero benefit

## When OptiMind Would Be Useful

- Multi-asset portfolio with allocation constraints
- Supply chain / logistics optimization
- Complex scheduling problems
- Manufacturing resource allocation

## Lesson Learned

Not every impressive technology is relevant to our system. Our $5K account with simple rules doesn't need mathematical optimization. The SOFI disaster taught us: complexity ≠ profitability.

## Tags
- evaluation
- microsoft-research
- optimization
- not-applicable
