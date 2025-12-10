# Scaling Roadmap v2: Path to $100/Day

**Created**: December 3, 2025 (Day 9/90)
**Based on**: Technical research blueprint + codebase analysis

## Executive Summary

| Metric | Current | Research Requirement | Gap |
|--------|---------|---------------------|-----|
| Live Trades | 7 | 385+ (95% confidence) | 378 trades (~4-6 months) |
| Capital | ~$100k | $200-400k for $100/day | 2-4x |
| Backtest Return | 26% | 8-13% realistic live | 50-70% degradation expected |
| Win Rate | 62.2% (backtest) | 0% (live, 7 trades) | Insufficient sample |
| Sharpe | 2.18 (backtest) | CI: ±0.32 on 60 obs | Statistically uncertain |

**Critical Finding**: Current 7 live trades and 60-day backtest are insufficient for statistical validity. Need 385+ trades for 95% confidence on performance metrics.

---

## Phase 1: Statistical Validation (Days 9-45)

**Goal**: Establish statistically significant performance baseline

### 1.1 Backtest Validation Upgrades (Week 1-2)

**Current State**:
- Sharpe ratio calculated but NO confidence intervals
- Walk-forward validator EXISTS but NOT integrated
- No bootstrap resampling

**Actions**:
1. **Implement Sharpe Confidence Intervals** (`src/backtesting/backtest_engine.py`)
   ```python
   SE(Sharpe) = sqrt(1/N + 0.25*kurtosis)
   CI = Sharpe ± 1.96*SE
   ```

2. **Integrate Walk-Forward Analysis** (already in `src/backtesting/walk_forward.py`)
   - Activate in `run_core_backtest.py`
   - 252-day train, 63-day test, 21-day step
   - Track Sharpe std across folds

3. **Add Trade Count Validation**
   ```python
   def is_statistically_valid(trades, min_trades=385):
       return len(trades) >= min_trades
   ```

### 1.2 Extend Backtest History (Week 2-4)

**Current**: 60-day backtest
**Target**: 2+ years covering multiple regimes

**Regime Coverage Required**:
- Bull/Quiet (VIX < 15, ADX > 25 trending up)
- Bull/Volatile (VIX 15-25)
- Bear/Quiet (VIX < 20, trending down)
- Bear/Volatile (VIX > 30, drawdown > 10%)
- Sideways (ADX < 20)

### 1.3 Live Trade Accumulation

**Current**: 7 trades
**Target**: 100+ trades by Day 45 (12 trades/week needed)

---

## Phase 2: Lopez de Prado Enhancements (Days 30-60)

### 2.1 Already Implemented ✅

| Method | Status | Location |
|--------|--------|----------|
| Triple Barrier Labeling | Complete | `src/research/labeling.py` |
| Walk-Forward Validation | Exists (not integrated) | `src/ml/walk_forward_validator.py` |
| Volatility Regime Labels | Complete | `src/research/labeling/volatility.py` |
| Directional Labels | Complete | `src/research/labeling/directional.py` |

### 2.2 High Priority Implementations

#### Fractional Differentiation (Priority: HIGH)

**Why**: Standard returns destroy time-series memory. Fractional diff (d=0.2-0.4) maintains 90%+ correlation while achieving stationarity.

**Implementation**:
```python
# New file: src/research/fractional_diff.py
def fractionally_differentiate(series, d=0.3, threshold=1e-5):
    """
    Lopez de Prado fractional differentiation
    d=0 (no diff), d=1 (standard diff), 0<d<1 (fractional)
    """
    weights = compute_weights(d, threshold)
    return convolve(series, weights)
```

**Files to modify**:
- `src/research/alpha/features.py` - Add frac_diff features
- `src/agents/rl_transformer_features.py` - Use frac_diff for RL

#### Meta-Labeling (Priority: MEDIUM)

**Why**: Secondary ML model to filter false positives from momentum signals.

**Architecture**:
1. Primary model: Momentum signal (long/short/neutral)
2. Meta-model: Logistic regression predicting "should I take this signal?"
3. Output: Position size (0 = skip, 0.5 = half size, 1.0 = full)

**Files to create**:
- `src/ml/meta_labeler.py`

#### Purged Cross-Validation Embargo (Priority: MEDIUM)

**Why**: Prevent information leakage at train/test boundaries.

**Enhancement to**: `src/ml/walk_forward_validator.py`
```python
# Add embargo periods
embargo_days = 5  # Gap between train and test
train_end_purged = train_end - embargo_days
test_start_purged = test_start + embargo_days
```

---

## Phase 3: Architecture Evolution (Days 45-75)

### 3.1 Current Architecture Assessment

**Strengths** (Keep):
- Multi-tier circuit breakers (9/10)
- Sharpe kill switch (10/10)
- SRE monitoring (8/10)
- Trade gateway with mandatory risk checks
- JSONL audit trail

**Weaknesses** (Address):
- Procedural funnel pattern (sequential gates)
- File-based JSON storage (no query capability)
- No message queue (no replay capability)

### 3.2 Evolutionary Upgrades (NOT full rewrite)

**Phase 3a**: Add instrumentation (Week 1)
- Event boundary logging
- End-to-end latency tracking

**Phase 3b**: Message queue (Week 2-3)
- Add Redis for gate-to-gateway decoupling
- Enable trade replay and idempotency

**Phase 3c**: Parallel gates (Week 3-4)
- Convert independent gates to async
- `asyncio.gather()` for momentum + RL in parallel

**NOT RECOMMENDED** (diminishing returns for our scale):
- Full event-driven rewrite
- QuestDB migration (JSONL is fine at our volume)
- Kubernetes deployment

---

## Phase 4: Risk Management Upgrades (Days 60-90)

### 4.1 Current State Assessment

| Component | Current | Score | Gap |
|-----------|---------|-------|-----|
| Kelly Criterion | Static 15% cap | 2/5 | No regime adjustment |
| Correlation | Simplified groups | 2/5 | No real-time matrix |
| Drawdown Control | VaR/CVaR + breakers | 4/5 | Missing 20/252-day windows |
| Tail Hedging | Collar strategy | 3/5 | No VIX spreads |
| Capital Efficiency | Excellent | 5/5 | - |

### 4.2 Priority Upgrades

#### Dynamic Kelly (High Impact)
```python
def dynamic_kelly(base_kelly, vix, regime):
    if vix < 15:  # Low vol regime
        return min(base_kelly * 1.5, 0.25)  # Increase up to 25%
    elif vix > 25:  # High vol regime
        return base_kelly * 0.5  # Halve position sizes
    return base_kelly
```

#### Real-Time Correlation Matrix
```python
def calculate_rolling_correlation(prices, window=60):
    returns = prices.pct_change()
    return returns.rolling(window).corr()
```

#### Extended Drawdown Monitoring
- Add 20-day rolling max drawdown
- Add 252-day rolling max drawdown
- Calculate Calmar ratio (return / max drawdown)

---

## Capital Path to $100/Day

### Realistic Return Expectations

| Scenario | Backtest | Live Degradation | Realistic Live |
|----------|----------|-----------------|----------------|
| Optimistic | 26% | 30% | 18% |
| Moderate | 26% | 50% | 13% |
| Conservative | 26% | 60% | 10% |

### Capital Requirements

For $36,500/year gross ($100/day):

| Scenario | Live Return | Tax/Cost | Net Yield | Capital Needed |
|----------|-------------|----------|-----------|----------------|
| Optimistic | 18% | 30% | 12.6% | $290,000 |
| Moderate | 13% | 35% | 8.5% | $430,000 |
| Conservative | 10% | 35% | 6.5% | $560,000 |

### Fibonacci Scaling Path

**Current**: $10/day paper trading
**Validated Edge Required Before Scaling**:
1. 385+ trades with statistical significance
2. Walk-forward OOS Sharpe > 1.0
3. Max drawdown < 15% across all regimes
4. Win rate > 55% in live trading

**Scaling Sequence** (after validation):
```
Phase 1: $1/day real → Proof of concept
Phase 2: $2/day real → Funded by Phase 1 profits
Phase 3: $3/day real → Funded by Phase 2 profits
...Fibonacci: 5, 8, 13, 21, 34, 55, 89...
```

---

## Key Milestones

| Day | Milestone | Success Criteria |
|-----|-----------|------------------|
| 15 | Sharpe CI implemented | CI calculated on all backtests |
| 30 | Walk-forward integrated | OOS Sharpe tracked |
| 45 | 100 live trades | Statistical baseline emerging |
| 60 | Frac diff + meta-labeling | RL features enhanced |
| 75 | Redis queue added | Replay capability enabled |
| 90 | Go/No-Go decision | 385+ trades, validated edge |

---

## What We're NOT Doing (Avoid Over-Engineering)

1. **NOT** building HFT infrastructure (sub-ms latency)
2. **NOT** migrating to time-series DB (JSONL sufficient at scale)
3. **NOT** implementing full CPCV (basic walk-forward adequate)
4. **NOT** adding alternative data feeds yet ($50-500/mo)
5. **NOT** scaling capital before statistical validation

---

## References

- Lopez de Prado, "Advances in Financial Machine Learning" (2018)
- Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014)
- Research Blueprint: "Scaling an AI trading bot to $100/day" (Dec 2025)

---

**Next Action**: Implement Sharpe confidence intervals in `backtest_engine.py`
