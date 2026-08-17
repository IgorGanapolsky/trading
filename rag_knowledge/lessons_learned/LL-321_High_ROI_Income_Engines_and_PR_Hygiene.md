# LL-321: High-ROI Income Engines, PLAN Framework & PR Hygiene

**ID**: LL-321
**Date**: 2026-08-17
**Severity**: LOW
**Category**: Strategy Evaluation, Tax Optimization, PR Hygiene
**Status**: ACTIVE

## Context

During PR management and autonomous strategy development sessions, extracted and implemented high-ROI frameworks from Rico Nasol's Freedom Builder (3-Bucket passive income, P.L.A.N. ETF evaluation, $10k scenario stress test), Ian Dunlap's core asset rules, and EYL tax sheltering strategies (Section 1256 60/40 blended tax rate, PTET state tax bypass).

## High-ROI Engines Codified

1. **StrategyResearchCritic** (`src/evals/research_critic.py`): Adversarial audit against 7 empirical failure modes (10-wide wings, IC complexity, sub-24h churn, unhedged shorts, missing regime gates).
2. **IncomeBucketEngine** (`src/strategies/income_bucket_engine.py`): 3-Bucket cashflow model with deficit-weighted DCA and 50% bear market survival simulation.
3. **FreedomNumberCalculator & CLI** (`src/strategies/freedom_number_calculator.py`, `scripts/calculate_freedom_number.py`): Projects timeline in months to North Star (,000/mo net by Nov 14, 2029) modeling business retainer surplus + options alpha + passive distributions.
4. **DistributionCalendarEngine** (`src/strategies/distribution_calendar.py`): 12-month forward cashflow schedules with automated Windfall Profit Sweeps into the 3-Bucket foundation.
5. **PlanETFEvaluator** (`src/evals/plan_etf_evaluator.py`): Sequential P.L.A.N. scoring (Payout, Liquidity, Asset quality, NAV trend) to fail closed on YieldMax-style synthetic yield traps.

## PR Management & Hygiene Actions

- Merged PR #4417 cleanly into `main` (commit `9420627da` / `0de47b700`).
- Cleaned up 6 merged/stale worktrees using the coordination hygiene wrapper (`scripts/worktree_hygiene.sh`).
- Aligned CodeQL subactions across workflows to `v4.37.7`.
- All 63 targeted unit tests passing.
