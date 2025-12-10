# Iteration Roadmap - Path to $100/day

This roadmap tracks the next 3-5 branches/PRs prioritized by expected P&L impact toward the $100/day net income target.

**Last Updated**: 2025-12-02

## Current Status

- **Current Avg Daily P&L**: See latest backtest results
- **Target**: $100/day net income
- **Gap**: TBD (run `python scripts/run_core_strategy_reference_backtest.py` to update)

## Next 3 Branches/PRs (Prioritized by P&L Impact)

### 1. [Branch/PR Name]
- **Expected P&L Impact**: +$X/day
- **Rationale**: [Why this will move us closer to $100/day]
- **Status**: [pending/in_progress/completed]
- **Dependencies**: [Any blocking work]
- **Metrics to Track**:
  - Avg daily P&L: Baseline → Target
  - % days ≥ $100: Baseline → Target
  - Sharpe ratio: Baseline → Target

### 2. [Branch/PR Name]
- **Expected P&L Impact**: +$X/day
- **Rationale**: [Why this will move us closer to $100/day]
- **Status**: [pending/in_progress/completed]
- **Dependencies**: [Any blocking work]
- **Metrics to Track**:
  - Avg daily P&L: Baseline → Target
  - % days ≥ $100: Baseline → Target
  - Sharpe ratio: Baseline → Target

### 3. [Branch/PR Name]
- **Expected P&L Impact**: +$X/day
- **Rationale**: [Why this will move us closer to $100/day]
- **Status**: [pending/in_progress/completed]
- **Dependencies**: [Any blocking work]
- **Metrics to Track**:
  - Avg daily P&L: Baseline → Target
  - % days ≥ $100: Baseline → Target
  - Sharpe ratio: Baseline → Target

## Completed Work (Recent)

### [PR/Branch Name] - Completed [Date]
- **Actual P&L Impact**: +$X/day (or -$X/day if negative)
- **Metrics Achieved**:
  - Avg daily P&L: $X → $Y
  - % days ≥ $100: X% → Y%
  - Sharpe ratio: X → Y
- **Lessons Learned**: [What worked, what didn't]

## How to Use This Roadmap

1. **Before Starting Work**: Check this roadmap to see if your planned work is already listed
2. **When Creating PR**: Update this file with expected P&L impact
3. **After Merging**: Update with actual impact and move to "Completed Work"
4. **Weekly Review**: Re-prioritize based on actual results

## P&L Impact Estimation Guide

- **Position Sizing Improvements**: +$5-15/day (better capital efficiency)
- **Signal Quality Improvements**: +$10-25/day (better entry/exit timing)
- **Risk Management Improvements**: +$5-10/day (fewer large losses)
- **New Strategy Addition**: +$10-30/day (diversification, more opportunities)
- **Data Quality Improvements**: +$5-15/day (better decisions)
- **Execution Improvements**: +$3-8/day (better fills, less slippage)

## Strategy Inventory

Run `python scripts/strategy_inventory.py --check-overlaps` to see:
- All registered strategies
- Latest backtest dates
- Overlapping branches/PRs
- Current pipeline stage

## Target Model Analysis

Run `python scripts/run_core_strategy_reference_backtest.py` to get:
- Current metrics vs $100/day target
- Required daily return %
- Feasibility analysis
- Risk constraint checks

## Notes

- Focus on **P&L impact**, not just code quality
- Each PR should explicitly state expected daily P&L change
- After merge, verify actual impact and update roadmap
- If impact is negative, investigate and document learnings
