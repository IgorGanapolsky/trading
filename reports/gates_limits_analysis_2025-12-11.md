# Gates and Limits Analysis - December 11, 2025

## Executive Summary

**Status**: Day 31/90 R&D Phase
**Portfolio**: $100,017.49 | P/L: $17.49 (0.017%)
**Win Rate**: 0% (live) | Backtest: 38-52%
**Sharpe Ratio**: -7 to -72 (all negative)

### Key Finding

The gates are **NOT the primary problem**. As of December 10, 2025, Gates 2 (RL) and 3 (LLM) are already **DISABLED** in "simplification mode". The 0% win rate indicates **positions aren't being closed**, not that entries are being blocked.

---

## Current Gate Configuration

### Gate Pipeline (Active)

| Gate | Name | Status | Configuration |
|------|------|--------|---------------|
| 0 | Mental Toughness Coach | ENABLED | Psychology-based trading guard |
| 0.5 | Bull/Bear Debate | ENABLED | Multi-perspective analysis |
| 1 | Momentum | ENABLED | `min_score=0.0` (very permissive) |
| 2 | RL Filter | **DISABLED** | Simplification mode since Dec 10 |
| 3 | LLM Sentiment | **DISABLED** | Simplification mode since Dec 10 |
| 3.5 | Introspective Council | ENABLED | Epistemic uncertainty check |
| 4 | Risk Sizing | ENABLED | 2% daily loss, 10% max position, 10% drawdown |

### Source References

- Gate 2/3 Disabled: `src/orchestrator/main.py:109-137`
- RL Threshold: `RL_CONFIDENCE_THRESHOLD=0.45` (reduced from 0.6)
- Sentiment Threshold: `LLM_NEGATIVE_SENTIMENT_THRESHOLD=-0.2`

---

## RiskManager Configuration

**File**: `src/core/risk_manager.py`

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `max_daily_loss_pct` | 2.0% | Circuit breaker - stops trading after 2% daily loss |
| `max_position_size_pct` | 10.0% | Max single position as % of account |
| `max_drawdown_pct` | 10.0% | Circuit breaker - stops trading at 10% drawdown |
| `max_consecutive_losses` | 3 | Warning trigger (doesn't block trading) |

**Assessment**: These are standard risk limits. Not overly restrictive for a $100k paper account.

---

## Promotion Gate Requirements

**File**: `scripts/enforce_promotion_gate.py`

| Requirement | Threshold | Current Status |
|-------------|-----------|----------------|
| Win Rate | >=60% | 0% (FAILING) |
| Sharpe Ratio | >=1.5 | -7 to -72 (FAILING) |
| Max Drawdown | <=10% | ~0% (PASSING) |
| Min Profitable Days | >=30 | Unknown |
| Min Trades | >=100 | Unknown |

---

## Root Cause Analysis

### Why 0% Win Rate?

**ONLY 1 CLOSED TRADE EVER**: A position closed Dec 9, 2025 after being held for **30 days**.

**Current Open Positions** (from `data/system_state.json`):

| Symbol | Asset Class | P/L % | Days Held | Exit Threshold | Status |
|--------|-------------|-------|-----------|----------------|--------|
| BIL | Treasury | -0.01% | 4 | +/-0.3% | Not triggered |
| IEF | Treasury | -0.003% | 4 | +/-0.3% | Not triggered |
| SHY | Treasury | -0.01% | 4 | +/-0.3% | Not triggered |
| SPY | Equity | -0.10% | 4 | +/-1.0% | Not triggered |
| TLT | Treasury | +0.02% | 4 | +/-0.3% | Not triggered |

### The Real Problem

**Exit thresholds are working correctly** but:

1. **Treasury ETFs (BIL, SHY, IEF, TLT)**: Move <0.1%/day - rarely hit 0.3% threshold
2. **Equities (SPY)**: Need 1% move in 10 days - SPY averages 0.05%/day

**Mathematical Reality**: At current volatility:
- Treasury positions will likely **never** hit 0.3% in 3 days
- SPY may hit 1% in ~20 days (but max hold is 10 days)
- Only time-decay exits are realistic

### Evidence from System State

```json
// Only 1 closed trade in 31 days
"closed_trades": [
  {
    "symbol": "REMOVED",
    "entry_date": "2025-11-09",
    "exit_date": "2025-12-09",  // 30 DAYS!
    "pl_pct": -0.097%
  }
]
```

---

## Recommendations

### Priority 1: Tighten Exit Thresholds (CRITICAL)

Current thresholds are **mathematically unrealistic** for asset volatility:

| Asset Class | Current | Recommended | Rationale |
|-------------|---------|-------------|-----------|
| Treasury | +/-0.3%, 3 days | +/-0.1%, 2 days | Treasuries move 0.02-0.05%/day |
| Equity | +/-1%, 10 days | +/-0.5%, 5 days | SPY moves 0.5-1%/week |

**Immediate Fix** in `src/risk/position_manager.py`:

```python
# Change lines 103-114 from:
treasury_take_profit_pct: float = 0.003  # 0.3%
treasury_stop_loss_pct: float = 0.003    # 0.3%
treasury_max_holding_days: int = 3

# To:
treasury_take_profit_pct: float = 0.001  # 0.1%
treasury_stop_loss_pct: float = 0.001    # 0.1%
treasury_max_holding_days: int = 2        # Force exits faster
```

---

## Summary Table

| Component | Current State | Issue? | Recommendation |
|-----------|---------------|--------|----------------|
| Gate 1 (Momentum) | ENABLED, permissive | No | Keep as-is |
| Gate 2 (RL) | DISABLED | No | Keep disabled (simplification) |
| Gate 3 (LLM) | DISABLED | No | Keep disabled (simplification) |
| Risk Limits | Standard | No | Keep 2%/10%/10% |
| **Exit Thresholds** | Too wide for assets | **YES** | **Tighten treasury to 0.1%, equity to 0.5%** |
| **Max Hold Days** | Too long | **YES** | **Reduce treasury to 2 days** |
| Position Sizing | Fixed | Minor | Add VIX scaling (lower priority)

---

## Next Steps

1. **Immediate (Today)**: Tighten exit thresholds in position_manager.py
   - Treasury: 0.3% -> 0.1%, max 3 days -> 2 days
   - Equity: 1.0% -> 0.5%, max 10 days -> 5 days

2. **This Week**: Monitor exit rate
   - Target: 2-3 exits per week (vs 1 in 31 days currently)
   - Watch for premature exits (profit left on table)

3. **Next Week**: Evaluate if exit changes improve win rate
   - If positions close more frequently -> calculate actual win rate
   - If still no exits -> investigate position_entries persistence

4. **End of Month**: Re-evaluate gate complexity
   - If simple funnel works -> keep Gates 2/3 disabled
   - If win rate > 50% -> consider scaling capital before adding complexity

---

## Key Insight

> **The gates aren't blocking trades - the exit thresholds are preventing closes.**
>
> With Gates 2 and 3 disabled, the funnel is maximally permissive for entries.
> The 0% win rate comes from positions never closing, not from over-filtering.
>
> **Fix the exits first, then worry about gate tuning.**

---

*Generated by Claude CTO | Day 31/90 R&D Phase*
*Analysis timestamp: 2025-12-11T02:30:00Z*
