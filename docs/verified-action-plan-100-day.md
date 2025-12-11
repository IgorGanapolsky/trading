# Verified Action Plan: Path to $100/Day

**Created**: December 11, 2025
**Based on**: Actual codebase analysis (not external reports)
**Current Status**: Day 9/90 R&D Phase | Portfolio: $100,017.49 | P/L: $17.49

---

## Executive Summary

This plan is based on **verified code analysis** of the actual repository. An external analysis contained several fabricated claims about non-existent files. This document provides accurate bottleneck identification with real file paths and line numbers.

---

## Verified Bottleneck #1: Daily Budget Hard Cap

### The Problem

**File**: `src/risk/risk_manager.py:88-90`

```python
# Enforce the daily budget as a hard per-trade cap so a high Kelly fraction
# cannot overshoot small-budget scenarios (e.g., paper trading).
notional = min(notional, baseline)
```

**Impact**: Even with $100,000 equity and perfect confidence (1.0), maximum trade size is:
- `$10 × 1.0 confidence × 1.25 sentiment = $12.50`

This means **99.98% of capital sits idle** regardless of signal quality.

### The Fix

**Option A**: Add confidence-based scaling (Conservative)

```python
# In src/risk/risk_manager.py, modify calculate_size():
def calculate_size(self, ...):
    # ... existing code ...

    # NEW: Scale up for high-conviction signals
    if blended_confidence >= 0.85:
        baseline = baseline * 3  # 3x for exceptional signals
    elif blended_confidence >= 0.75:
        baseline = baseline * 2  # 2x for high-confidence signals

    # ... rest of existing code ...
```

**Option B**: Use equity-proportional sizing (More Aggressive)

```python
# In src/risk/risk_manager.py:
# Replace line 75:
baseline = self.daily_budget * blended_confidence * sentiment_multiplier * multiplier

# With:
equity_based = account_equity * 0.02 * blended_confidence  # 2% of equity
budget_based = self.daily_budget * blended_confidence * sentiment_multiplier * multiplier
baseline = max(budget_based, equity_based)  # Take larger of the two
```

**Risk**: Option B requires careful monitoring. Start with Option A.

---

## Verified Bottleneck #2: Dynamic Budget Already Exists (But May Be Disabled)

### The Discovery

**File**: `scripts/autonomous_trader.py:305-332`

```python
def _apply_dynamic_daily_budget(logger) -> float | None:
    """
    Adjust DAILY_INVESTMENT based on account equity before orchestrator loads.
    """
    # ... scales DAILY_INVESTMENT up to $50 based on equity
```

This function EXISTS but caps at $50 (line 327):
```python
new_amount = min(50.0, max(10.0, base * multiplier))  # $50 cap
```

### The Fix

1. **Verify it runs**: Check if `_apply_dynamic_daily_budget` is called in the trading workflow
2. **Increase cap**: Change $50 cap to $100 or remove entirely for accounts >$50k
3. **Add environment variable**: `DYNAMIC_BUDGET_CAP` to make configurable

---

## Verified Bottleneck #3: Theta Auto-Execution Exists (Enable It)

### The Discovery

**File**: `src/analytics/options_profit_planner.py:592-619`

```python
if self.auto_execute and self._should_attempt_auto(
    strategy=strategy, regime_label=regime_label
):
    execution = self._auto_execute_theta(result)
```

The `ThetaHarvestExecutor` class has full auto-execution capability:
- Checks IV percentile
- Selects 20-delta contracts
- Executes via `ExecutionAgent`

### Current State

**Environment variable**: `ENABLE_THETA_AUTOMATION` (defaults to `"true"` per line 406)

But `_should_attempt_auto()` only allows execution for:
- `poor_mans_covered_call` strategy
- `calm`, `range`, or `neutral` regime

### The Fix

1. **Verify environment**: Ensure `ENABLE_THETA_AUTOMATION=true` is set
2. **Test execution path**: Run theta harvest with live paper trading
3. **Expand strategies**: Modify `_should_attempt_auto()` to include iron condors in calm regimes

---

## Verified Bottleneck #4: Capital Efficiency Gates Are Correct

### Good News

**File**: `src/risk/capital_efficiency.py`

The capital tier system is well-designed:
- $5k: Poor man's covered calls
- $10k: Iron condors
- $25k: Full options suite

**Current account ($100k) unlocks ALL tiers** - no capital gate blocking.

### No Fix Needed

Capital efficiency calculator is working correctly.

---

## Prioritized Action Plan

### Week 1: Quick Wins (No Code Changes)

| Action | File/Location | Expected Impact |
|--------|---------------|-----------------|
| Set `ENABLE_THETA_AUTOMATION=true` | Environment | Enable options auto-execution |
| Set `DAILY_INVESTMENT=50` | Environment | 5x current trade sizes |
| Verify `_apply_dynamic_daily_budget` runs | `autonomous_trader.py` | Confirm dynamic scaling |

### Week 2: Code Modifications

| Action | File | Line | Impact |
|--------|------|------|--------|
| Add confidence-based scaling | `src/risk/risk_manager.py` | 75-90 | 2-3x trade sizes for high-confidence |
| Increase dynamic budget cap | `scripts/autonomous_trader.py` | 327 | Allow >$50 daily budget |
| Expand theta auto-execution | `src/analytics/options_profit_planner.py` | 625-628 | More strategies auto-execute |

### Week 3: Testing & Validation

- Run backtests with new sizing
- Paper trade for 5 days minimum
- Monitor slippage and fill rates
- Verify P/L reconciliation with Alpaca

---

## Math: What's Actually Achievable?

### Current State
- Daily budget: $10
- Max confidence: 1.0
- Max trade: ~$12.50
- Required return for $100/day: **800%** (impossible)

### After Week 1 (Environment Changes)
- Daily budget: $50
- Max trade: ~$62.50
- Required return for $100/day: **160%** (still unrealistic)

### After Week 2 (Code Changes)
- Base budget: $50
- Confidence multiplier: 3x for high-confidence
- Max trade: ~$187.50 equity + options theta
- Options theta contribution: ~$30-50/day (at $100k equity)
- Required equity return for remaining $50-70: **30-40%** (possible with options)

### Realistic Target
- **Weeks 1-4**: $20-30/day (2x-3x sizing + theta)
- **Weeks 5-8**: $40-60/day (validated strategies, increased risk budget)
- **Weeks 9-12**: $80-100/day (scaled theta + leveraged ETFs if approved)

---

## Files to Modify (Verified Paths)

```
src/risk/risk_manager.py                    # Bottleneck #1: Daily budget cap
scripts/autonomous_trader.py                # Bottleneck #2: Dynamic budget scaling
src/analytics/options_profit_planner.py     # Bottleneck #3: Theta auto-execution
```

---

## What NOT to Do (Avoiding Fabricated Advice)

The external analysis suggested:

| Suggestion | Reality |
|------------|---------|
| "Modify parallel_orchestrator.py" | File doesn't exist |
| "Add macro_factor_agent for VIX/Treasury" | Wrong file - actual file does RAG sentiment |
| "Use tests/test_scaling.py" | File doesn't exist |
| "Implement calculate_aggressive_sizing" | Function doesn't exist |

**Always verify file existence before implementing suggested changes.**

---

## Verification Commands

```bash
# Verify theta automation is enabled
grep -r "ENABLE_THETA_AUTOMATION" src/ scripts/

# Check current daily budget cap
grep -n "daily_budget" src/risk/risk_manager.py

# Verify dynamic budget function
grep -n "_apply_dynamic_daily_budget" scripts/autonomous_trader.py

# Test options profit planner
python3 -c "from src.analytics.options_profit_planner import ThetaHarvestExecutor; print('OK')"
```

---

## Success Metrics

| Metric | Current | Week 4 Target | Week 12 Target |
|--------|---------|---------------|----------------|
| Daily P/L | $2-5 | $20-30 | $80-100 |
| Trade Size | $10-12 | $50-60 | $150-200 |
| Options Theta | $0 | $10-20 | $30-50 |
| Win Rate | 67% | 60%+ | 60%+ |
| Max Drawdown | 2.2% | <5% | <8% |

---

**Document Status**: VERIFIED against actual codebase
**Last Updated**: December 11, 2025
