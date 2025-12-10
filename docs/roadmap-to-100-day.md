# Roadmap to $100/Day: Production-Ready Trading System

**Created**: December 5, 2025
**Status**: Active
**Current Day**: 9/90 (R&D Phase)

---

## Executive Summary

This roadmap addresses the gaps identified in the code review assessment. The goal is to transform the current system from "promising but fragile" to "production-ready for scaling."

**Key Finding**: The codebase already has more infrastructure than the assessment credited:
- Slippage modeling exists (`src/risk/slippage_model.py`)
- Model versioning exists (`src/ml/reoptimization_scheduler.py`)
- Walk-forward validation exists (`src/backtesting/walk_forward_matrix.py`)

**Genuine Gaps**: Live cost tracking, partial fills, strategy diversification, capital scaling rules.

---

## Task 1: Live Execution Cost Tracking

**Priority**: HIGH
**Effort**: 4-6 hours
**Status**: Not Started

### Problem
Backtest slippage model (`src/risk/slippage_model.py`) is not validated against real Alpaca fills. We have no way to know if our 5 bps assumption matches reality.

### Implementation

**File**: `src/execution/alpaca_executor.py`

```python
# Add to AlpacaExecutor class:
def track_fill_slippage(self, order_id: str, expected_price: float) -> dict:
    """Compare expected vs actual fill price"""
    order = self.api.get_order(order_id)
    if order.filled_avg_price:
        actual_price = float(order.filled_avg_price)
        slippage_bps = abs(actual_price - expected_price) / expected_price * 10000
        return {
            "order_id": order_id,
            "expected_price": expected_price,
            "actual_price": actual_price,
            "slippage_bps": slippage_bps,
            "timestamp": datetime.now().isoformat()
        }
```

**File**: `data/execution_costs.json` (new)
```json
{
  "fills": [...],
  "daily_summary": {
    "avg_slippage_bps": 3.2,
    "model_accuracy": 0.85
  }
}
```

### Acceptance Criteria
- [ ] Every live order logs expected vs actual fill price
- [ ] Daily summary compares model prediction vs reality
- [ ] Alert if average slippage exceeds model by >50%

---

## Task 2: Commission Integration in Normal Backtests

**Priority**: HIGH
**Effort**: 2-3 hours
**Status**: Not Started

### Problem
Commission fees only exist in `pessimistic_backtest.py`. Normal backtests show 0 commission, which is misleading.

### Implementation

**File**: `src/risk/slippage_model.py`

Add to `SlippageModel.__init__()`:
```python
self.commission_schedule = {
    "stocks": 0.0,  # Alpaca: $0 for stocks
    "options": 0.65,  # $0.65/contract
    "sec_fee": 0.0000278,  # SEC fee per $ sold
    "finra_taf": 0.000166,  # FINRA TAF per share (max $8.30)
}
```

**File**: `src/backtesting/backtest_engine.py`

Update `_execute_trade()` to include commission costs by default.

### Acceptance Criteria
- [ ] Normal backtest includes SEC fee + FINRA TAF
- [ ] Options backtests include $0.65/contract
- [ ] Results show commission as separate line item

---

## Task 3: Multi-Strategy Ensemble

**Priority**: HIGH
**Effort**: 8-12 hours
**Status**: Not Started

### Problem
Single strategy (momentum + RL + LLM funnel) is exposed to regime risk. Momentum fails in mean-reverting markets.

### Implementation

**File**: `src/strategies/mean_reversion_strategy.py` (new)

```python
class MeanReversionStrategy:
    """RSI oversold/overbought + Bollinger Band reversion"""

    def generate_signal(self, symbol: str, data: pd.DataFrame) -> Signal:
        rsi = self.calculate_rsi(data, period=14)
        bb_position = self.bollinger_position(data)

        if rsi < 30 and bb_position < 0.2:
            return Signal(action="BUY", confidence=0.7, strategy="mean_reversion")
        elif rsi > 70 and bb_position > 0.8:
            return Signal(action="SELL", confidence=0.7, strategy="mean_reversion")
```

**File**: `src/strategies/strategy_ensemble.py` (new)

```python
class StrategyEnsemble:
    """Combines momentum + mean reversion with regime detection"""

    def __init__(self):
        self.momentum = MomentumStrategy()
        self.mean_reversion = MeanReversionStrategy()
        self.regime_detector = RegimeDetector()

    def generate_signal(self, symbol: str) -> Signal:
        regime = self.regime_detector.detect()  # TRENDING or RANGING

        if regime == "TRENDING":
            weight = {"momentum": 0.7, "mean_reversion": 0.3}
        else:
            weight = {"momentum": 0.3, "mean_reversion": 0.7}

        # Weighted ensemble vote
        return self.weighted_vote(weight)
```

### Acceptance Criteria
- [ ] Mean reversion strategy passes walk-forward validation (Sharpe > 0.8)
- [ ] Ensemble backtest shows lower max drawdown than momentum-only
- [ ] Regime detector correctly identifies trending vs ranging periods

---

## Task 4: Capital Scaling Rules (Fibonacci + Drawdown Limits)

**Priority**: MEDIUM
**Effort**: 3-4 hours
**Status**: Not Started

### Problem
No formalized rules for scaling from $10/day to $100/day. Risk of ruin if scaling too fast.

### Implementation

**File**: `src/risk/capital_scaler.py` (new)

```python
@dataclass
class ScalingRules:
    fibonacci_sequence = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    # Scale up when cumulative profit >= next_fib_level * 30 days
    # Example: Scale $1 -> $2 when profit >= $60 ($2 * 30)

    max_drawdown_pct: float = 0.15  # 15% max drawdown before pause
    daily_loss_limit_pct: float = 0.02  # 2% daily loss limit
    scale_down_threshold: float = 0.10  # 10% drawdown triggers scale-down

class CapitalScaler:
    def should_scale_up(self, current_level: int, cumulative_profit: float) -> bool:
        next_level = self.fibonacci_sequence[current_level + 1]
        required_profit = next_level * 30
        return cumulative_profit >= required_profit

    def check_circuit_breakers(self, daily_pnl: float, drawdown: float) -> str:
        if drawdown > self.max_drawdown_pct:
            return "HALT"  # Stop trading, manual review
        elif drawdown > self.scale_down_threshold:
            return "SCALE_DOWN"  # Reduce position sizes
        elif daily_pnl < -self.daily_loss_limit_pct:
            return "PAUSE_TODAY"  # No more trades today
        return "CONTINUE"
```

### Acceptance Criteria
- [ ] Scaling rules enforced in `alpaca_executor.py`
- [ ] Circuit breakers halt trading at 15% drawdown
- [ ] Daily loss limit (2%) pauses trading for the day
- [ ] Scaling only uses profits, never external funds

---

## Task 5: Forward Test Cost Validation

**Priority**: MEDIUM
**Effort**: 4-5 hours
**Status**: ✅ COMPLETE

### Problem
Walk-forward validation exists but doesn't compare backtest costs to live costs.

### Implementation

**File**: `src/backtesting/cost_validator.py` (new)

```python
class CostValidator:
    """Weekly comparison of backtest vs live execution costs"""

    def validate_weekly(self) -> ValidationReport:
        # Load last 7 days of live fills
        live_costs = self.load_live_costs()

        # Run backtest over same period
        backtest_costs = self.run_backtest_same_period()

        divergence = abs(live_costs.avg_slippage - backtest_costs.avg_slippage)

        return ValidationReport(
            live_avg_slippage_bps=live_costs.avg_slippage,
            backtest_avg_slippage_bps=backtest_costs.avg_slippage,
            divergence_bps=divergence,
            model_accurate=divergence < 2.0,  # Within 2 bps
            recommendation=self.get_recommendation(divergence)
        )
```

**Integration**: Add to `.github/workflows/weekly-validation.yml`

### Acceptance Criteria
- [x] Weekly report compares live vs backtest costs
- [x] Alert if divergence > 2 bps
- [x] Automatic slippage model recalibration if divergence persists

---

## Task 6: Automated Stress Testing Before Live Deployment

**Priority**: MEDIUM
**Effort**: 3-4 hours
**Status**: ✅ COMPLETE

### Problem
Pessimistic backtest exists (`src/backtesting/pessimistic_backtest.py`) but isn't automated before live deployment.

### Implementation

**File**: `.github/workflows/pre-deploy-stress-test.yml` (new)

```yaml
name: Pre-Deploy Stress Test

on:
  push:
    branches: [main]
    paths:
      - 'src/strategies/**'
      - 'src/ml/**'

jobs:
  stress-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Pessimistic Backtest
        run: python -m src.backtesting.pessimistic_backtest --symbols SPY,QQQ

      - name: Validate Results
        run: |
          # Fail if pessimistic Sharpe < 0.5
          python scripts/validate_stress_test.py --min-sharpe 0.5
```

**File**: `scripts/validate_stress_test.py` (new)

```python
def validate(results_path: str, min_sharpe: float = 0.5):
    results = json.load(open(results_path))

    if results["pessimistic_sharpe"] < min_sharpe:
        print(f"FAIL: Pessimistic Sharpe {results['pessimistic_sharpe']} < {min_sharpe}")
        sys.exit(1)

    if results["max_drawdown"] > 0.25:
        print(f"FAIL: Max drawdown {results['max_drawdown']} > 25%")
        sys.exit(1)

    print("PASS: Strategy survives stress test")
```

### Acceptance Criteria
- [x] Every strategy change triggers stress test
- [x] Deployment blocked if pessimistic Sharpe < 0.5
- [x] Deployment blocked if max drawdown > 25%

---

## Timeline & Dependencies

```
Week 1-2: Task 1 (Live Cost Tracking) + Task 2 (Commission Integration)
          └── Foundation for cost validation

Week 3-4: Task 5 (Forward Test Validation)
          └── Depends on Task 1 data

Week 3-5: Task 3 (Multi-Strategy Ensemble)
          └── Independent, can parallel with above

Week 5-6: Task 4 (Capital Scaling) + Task 6 (Stress Testing)
          └── Final hardening before scaling
```

---

## Success Metrics

| Metric | Current | Target | Timeline |
|--------|---------|--------|----------|
| Live vs Backtest Cost Divergence | Unknown | < 2 bps | Week 3 |
| Strategy Correlation (Momentum vs MR) | N/A | < 0.3 | Week 5 |
| Max Drawdown (Stress Test) | Unknown | < 20% | Week 6 |
| Sharpe Ratio (Ensemble) | 2.18 (single) | > 1.5 (ensemble) | Week 5 |
| Capital Scaling Ready | No | Yes | Week 6 |

---

## Risk Mitigation

1. **If live costs diverge significantly**: Pause live trading, recalibrate model
2. **If mean reversion underperforms**: Keep as minority weight (30%), don't abandon
3. **If drawdown exceeds 15%**: Automatic halt, require manual review
4. **If stress test fails**: Block deployment, investigate

---

## References

- `src/risk/slippage_model.py` - Existing cost model
- `src/backtesting/pessimistic_backtest.py` - Existing stress test
- `src/ml/reoptimization_scheduler.py` - Existing versioning
- `docs/r-and-d-phase.md` - Current R&D strategy
