# Lesson Learned #129: Backtest Evaluation Bugs Discovered via Deep Research

**Date**: January 10, 2026
**Category**: System Integrity
**Severity**: HIGH

## Context

CEO requested deep research into Anthropic's "Demystifying evals for AI agents" article to determine if their evaluation framework would improve our trading system.

## Discovery

While analyzing the article against our existing infrastructure, the research revealed that **we already have more rigorous evaluation infrastructure** than typical AI agent evals because we have real financial accountability. However, the research uncovered **critical bugs** in our existing evaluation system:

## Bugs Found and Fixed

### Bug 1: Slippage Model Disabled
**Location**: `scripts/run_backtest_matrix.py`
**Issue**: The code claimed `slippage_model_enabled: True` but all execution costs were hardcoded to 0.0
**Impact**: Backtests overestimated returns by 20-50% (per slippage_model.py documentation)
**Fix**: Integrated actual SlippageModel into backtest execution, applying slippage and fees to trades

### Bug 2: Win Rate Without Context (ll_118 violation)
**Location**: `scripts/run_backtest_matrix.py` and output JSONs
**Issue**: Win rate displayed without avg_return, allowing misleading metrics (e.g., "80% win rate" with -6.97% avg return)
**Impact**: False confidence in strategy performance
**Fix**: Added `avg_return_pct` field and `win_rate_with_context` that always shows both together

### Bug 3: Missing Bidirectional Learning
**Location**: `src/analytics/live_vs_backtest_tracker.py`
**Issue**: Tracked live slippage but didn't sync back to backtest assumptions
**Impact**: Same slippage assumptions used repeatedly despite real-world evidence
**Fix**: Added `sync_to_backtest_assumptions()` method and `load_live_slippage_assumptions()` for backtests

## Key Insight

**The Anthropic article is useful for evaluating LLM agents (like Claude Code), NOT for trading systems.**

Our trading system already has:
- Quantitative metrics (Sharpe, win rate, drawdown)
- Survival gate validation (95% capital preservation)
- 19 historical scenarios including crash replays
- Live vs backtest tracking
- Anomaly detection

**The real value** was using the research process to discover implementation bugs, not adopting a new framework.

## Prevention

1. Code should **actually implement** what documentation claims (slippage_model_enabled)
2. Always show **avg_return with win_rate** per ll_118
3. Implement **bidirectional feedback loops** from production to testing
4. Regularly audit evaluation infrastructure for silent failures

## Files Changed

- `scripts/run_backtest_matrix.py` - Integrated slippage model, added avg_return_pct
- `src/analytics/live_vs_backtest_tracker.py` - Added bidirectional learning functions

## Tags
#evaluation #backtest #slippage #win-rate #bidirectional-learning #system-audit
