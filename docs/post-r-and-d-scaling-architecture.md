# Post-R&D Scaling Architecture: Path to $100/Day

**Created**: December 11, 2025
**Context**: Analysis of scaling constraints during R&D phase
**Status**: Roadmap for implementation AFTER Day 90 validation

---

## Executive Summary

This document captures the architectural evolution required to scale from R&D validation to $100/day net income. The key insight: **scaling is a post-validation activity, not a current priority.**

### The Timing Matrix

| Phase | Days | Focus | Scaling Activity |
|-------|------|-------|------------------|
| **R&D Month 1** | 1-30 | System reliability, data collection | NONE - validate edge |
| **R&D Month 2** | 31-60 | Build trading edge (>55% win rate) | NONE - refine signals |
| **R&D Month 3** | 61-90 | Validate edge (>60% WR, >1.5 Sharpe) | NONE - prove consistency |
| **Post-R&D Q1** | 91-180 | Dynamic allocation + options | BEGIN scaling |
| **Post-R&D Q2** | 181-365 | Full multi-strategy deployment | AGGRESSIVE scaling |

**Current Status**: Day 9/90 - Focus on edge validation, NOT scaling.

---

## Part 1: Why Scaling Now is Premature

### The Math Reality

With $10/day fixed allocation:

```
Daily Investment:     $10
Annual Investment:    $3,650
At 26% Return:        $949/year profit
Daily Profit:         $2.60/day

Gap to $100/day:      ~40x
```

**Conclusion**: $100/day requires either massive capital OR exceptional returns (which = gambling).

### The Correct Response

The analysis suggesting immediate scaling is mathematically correct but **strategically premature** for these reasons:

1. **Edge Not Proven**: 7 live trades is statistically meaningless (need 385+ for 95% confidence)
2. **R&D Phase Purpose**: Months 1-3 are explicitly for building edge, not scaling
3. **Fibonacci Strategy**: Documented approach scales AFTER proving profitability at each level
4. **Risk Compounding**: Scaling before validation = scaling losses

### What We're Validating (Days 1-90)

| Metric | Current | Day 90 Target | Purpose |
|--------|---------|---------------|---------|
| Live Trades | 7 | 100+ | Statistical significance |
| Win Rate | 66.7% (live) | >60% sustained | Edge validation |
| Sharpe Ratio | 2.18 (backtest) | >1.5 (live) | Risk-adjusted performance |
| Max Drawdown | N/A | <10% | Risk management validation |
| Consecutive Profitable Days | 9 | 30+ | Consistency proof |

---

## Part 2: Post-R&D Scaling Architecture (Day 91+)

### Phase 1: Dynamic Capital Allocation (Days 91-120)

**The Core Problem**: Fixed $10/day doesn't scale naturally.

**The Solution**: Percentage-based allocation model.

```python
# Current (Fixed) - REPLACE AFTER R&D
DAILY_INVESTMENT = 10  # Fixed dollars

# Post-R&D (Dynamic) - IMPLEMENT AT DAY 91
class DynamicAllocator:
    def __init__(self, portfolio_value):
        self.portfolio = portfolio_value
        self.base_allocation_pct = 0.01  # 1% of portfolio daily
        self.max_allocation_pct = 0.02   # 2% cap
        self.min_allocation_pct = 0.005  # 0.5% floor

    def calculate_daily_allocation(self, vix_level, regime):
        """
        Volatility-adjusted daily allocation
        """
        base = self.portfolio * self.base_allocation_pct

        # Regime adjustments
        if vix_level < 15:  # Low vol - increase
            multiplier = 1.5
        elif vix_level > 25:  # High vol - decrease
            multiplier = 0.5
        else:
            multiplier = 1.0

        allocation = base * multiplier

        # Apply caps
        max_alloc = self.portfolio * self.max_allocation_pct
        min_alloc = self.portfolio * self.min_allocation_pct

        return max(min_alloc, min(allocation, max_alloc))
```

**Impact at $100k portfolio**:
- Base: $100k × 1% = $1,000/day
- Low vol: $100k × 1.5% = $1,500/day
- High vol: $100k × 0.5% = $500/day

**Files to Modify**:
- `src/risk/risk_manager.py` - Add `DynamicAllocator` class
- `src/orchestrator/main.py` - Replace fixed allocation with dynamic
- `config/trading_config.yaml` - Add percentage parameters

### Phase 2: Multi-Strategy Parallel Execution (Days 121-150)

**Current Architecture**: Sequential strategy execution
**Post-R&D Architecture**: Parallel multi-strategy with conflict resolution

```
┌─────────────────────────────────────────────────────────┐
│                    CAPITAL ALLOCATOR                     │
│  Total Daily Budget = f(portfolio, volatility, regime)   │
└───────────────┬─────────────────────────────────────────┘
                │
    ┌───────────┼───────────┬───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼
┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
│Tier 1 │  │Tier 2 │  │Options│  │ Crypto │  │ Cash  │
│ ETF   │  │Growth │  │Premium│  │Weekend │  │Reserve│
│ 40%   │  │ 25%   │  │ 15%   │  │ 10%    │  │ 10%   │
└───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘
    │          │          │          │          │
    └──────────┴──────────┴──────────┴──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │ CONFLICT RESOLUTION │
               │ - Max 3 positions   │
               │ - No sector overlap │
               │ - Total risk < 5%   │
               └─────────────────────┘
```

**Allocation Evolution**:

| Strategy | R&D Phase | Post-R&D Phase 1 | Post-R&D Phase 2 |
|----------|-----------|------------------|------------------|
| Tier 1 ETFs | 60% | 40% | 35% |
| Tier 2 Growth | 40% | 25% | 20% |
| Options Premium | 0% | 15% | 20% |
| Crypto Weekend | 0% | 10% | 15% |
| Cash Reserve | 0% | 10% | 10% |

### Phase 3: Options Income Integration (Days 151-180)

**Prerequisites**:
- Accumulate 100+ shares of high-premium stocks (NVDA, AAPL, GOOGL)
- Validate options scanner produces opportunities
- Complete Phil Town options training module

**Implementation**:

```python
class OptionsIncomeEngine:
    """
    Post-R&D options premium generator
    Target: $10-30/day from premium selling
    """

    def __init__(self):
        self.strategies = {
            'covered_calls': CoveredCallStrategy(),
            'cash_secured_puts': CashSecuredPutStrategy(),
            'collar': CollarStrategy()
        }
        self.daily_premium_target = 15  # $15/day

    def execute_weekly(self, positions, capital):
        """
        Weekly options cycle:
        1. Monday: Scan for opportunities
        2. Tuesday: Execute positions
        3. Thursday: Manage (roll if needed)
        4. Friday: Close or let expire
        """
        opportunities = self.scan_opportunities(positions)
        if opportunities:
            return self.execute_optimal(opportunities, capital)
        return None
```

**Expected Income**:

| Holdings | Strategy | Weekly Premium | Daily Equivalent |
|----------|----------|----------------|------------------|
| 100 NVDA @ $140 | Covered Call (25 delta) | $150-200 | $21-28/day |
| 100 AAPL @ $195 | Covered Call (25 delta) | $80-120 | $11-17/day |
| $10k cash | Cash-Secured Puts | $50-100 | $7-14/day |

**Total Target**: $30-50/day from options (achievable at $100k+ scale)

---

## Part 3: Capital Requirements Analysis

### Return Degradation Expectation

**Critical Insight**: Backtest returns ALWAYS degrade in live trading.

| Scenario | Backtest Return | Expected Degradation | Live Return |
|----------|-----------------|---------------------|-------------|
| Optimistic | 26% | 30% | 18% |
| Moderate | 26% | 50% | 13% |
| Conservative | 26% | 60% | 10% |

### Capital Required for $100/Day

**Target**: $36,500/year gross ($100/day × 365)

| Return Scenario | Live Return | Tax/Costs (35%) | Net Yield | Capital Required |
|-----------------|-------------|-----------------|-----------|------------------|
| Optimistic | 18% | 35% | 11.7% | $312,000 |
| Moderate | 13% | 35% | 8.5% | $429,000 |
| Conservative | 10% | 35% | 6.5% | $562,000 |

### Fibonacci Scaling Path (Proven Strategy)

The documented Fibonacci approach scales responsibly:

```
Phase 1: $1/day real    → Prove $1 profit        → Scale trigger: $30 profit
Phase 2: $2/day real    → Funded by Phase 1     → Scale trigger: $60 profit
Phase 3: $3/day real    → Funded by Phase 2     → Scale trigger: $90 profit
Phase 4: $5/day real    → Fibonacci continues   → Scale trigger: $150 profit
Phase 5: $8/day real    → ...                   → Scale trigger: $240 profit
...
Phase 10: $89/day real  → Approaching target    → Scale trigger: $2,670 profit
Phase 11: $144/day real → TARGET EXCEEDED       → Maintain
```

**Why This Works**:
1. Each phase funded by previous profits (no external capital injection)
2. Validates edge at every level before scaling
3. Limits downside (losses capped at previous profits)
4. Creates compounding intelligence (system learns at each scale)

---

## Part 4: Essential Safety Tests for Scaling

### Pre-Scaling Gate (Run at Day 90)

```python
def pre_scaling_gate_check():
    """
    MUST PASS before any scaling begins
    """
    checks = {
        'statistical_validity': live_trades >= 100,
        'win_rate_sustained': win_rate >= 0.60,
        'sharpe_live': live_sharpe >= 1.0,
        'max_drawdown': max_drawdown <= 0.10,
        'consecutive_profitable': profitable_days >= 30,
        'no_critical_bugs': critical_bug_count == 0
    }

    passed = all(checks.values())

    if not passed:
        print("SCALING BLOCKED - Extend R&D phase")
        for check, status in checks.items():
            if not status:
                print(f"  FAILED: {check}")

    return passed
```

### Scaling Phase Tests

**1. Capital Scaling Dry-Run** (NEW - Implement at Day 85)

```python
def capital_scaling_simulation(historical_data, days=90):
    """
    Simulate dynamic allocation model on historical data
    Verify position sizes scale correctly without exceeding limits
    """
    results = {
        'max_position_pct': 0,
        'max_drawdown': 0,
        'scaling_violations': 0
    }

    for day in historical_data:
        allocation = dynamic_allocator.calculate(day.portfolio, day.vix)
        position_pct = allocation / day.portfolio

        if position_pct > 0.02:  # 2% max
            results['scaling_violations'] += 1

        results['max_position_pct'] = max(results['max_position_pct'], position_pct)

    return results
```

**2. Multi-Strategy Conflict Test** (NEW - Implement at Day 120)

```python
def multi_strategy_conflict_check(proposed_trades):
    """
    Ensure parallel strategies don't over-concentrate risk
    """
    conflicts = []

    # Check sector concentration
    sectors = [t.sector for t in proposed_trades]
    if any(sectors.count(s) > 2 for s in sectors):
        conflicts.append("Sector over-concentration")

    # Check correlation
    tickers = [t.symbol for t in proposed_trades]
    corr_matrix = get_correlation_matrix(tickers)
    if corr_matrix.max() > 0.8:
        conflicts.append("High correlation between positions")

    # Check total risk
    total_risk = sum(t.risk_pct for t in proposed_trades)
    if total_risk > 0.05:  # 5% max portfolio risk
        conflicts.append("Total risk exceeds 5%")

    return conflicts
```

**3. Liquidity & Slippage Simulation** (NEW - Implement at Day 150)

```python
def slippage_simulation(order, avg_volume):
    """
    Estimate execution slippage based on order size vs volume
    """
    order_pct_of_volume = order.shares / avg_volume

    if order_pct_of_volume < 0.01:  # <1% of volume
        expected_slippage = 0.001  # 0.1%
    elif order_pct_of_volume < 0.05:  # 1-5% of volume
        expected_slippage = 0.005  # 0.5%
    else:
        expected_slippage = 0.02  # 2% - WARN
        print(f"WARNING: Order size {order_pct_of_volume:.1%} of volume")

    return expected_slippage
```

**4. Regime Shift Detection Audit** (Weekly - Existing, enhance)

```python
def regime_detection_audit(historical_labels, live_labels):
    """
    Verify regime detection matches labeled historical periods
    """
    accuracy = sum(h == l for h, l in zip(historical_labels, live_labels)) / len(historical_labels)

    if accuracy < 0.80:
        print(f"WARNING: Regime detection accuracy {accuracy:.1%} below 80% threshold")
        return False
    return True
```

---

## Part 5: Implementation Timeline

### R&D Phase (Current: Days 1-90)

| Day | Milestone | Action |
|-----|-----------|--------|
| 1-30 | Infrastructure validation | Continue current approach |
| 31-60 | Edge building | Implement MACD+RSI+Volume system |
| 61-90 | Edge validation | 30 days of consistent performance |
| **90** | **Go/No-Go Decision** | Run pre-scaling gate check |

### Post-R&D Phase 1 (Days 91-180)

| Day | Milestone | Action |
|-----|-----------|--------|
| 91-100 | Dynamic allocation | Implement percentage-based model |
| 101-120 | Testing | Dry-run with paper trades |
| 121-150 | Multi-strategy | Add parallel execution |
| 151-180 | Options integration | Begin covered call program |

### Post-R&D Phase 2 (Days 181-365)

| Day | Milestone | Action |
|-----|-----------|--------|
| 181-240 | Scale to $500/day | Gradually increase allocation |
| 241-300 | Scale to $1,000/day | Full dynamic allocation |
| 301-365 | Optimization | Fine-tune for $100/day net |

---

## Part 6: Risk Mitigations for Scaling

### Scaling Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Position sizing errors | Medium | High | Gradual scaling, daily verification |
| Win rate degradation | Medium | High | Automatic scale-back triggers |
| Options assignment | Low | Medium | Only covered calls, monitor delta |
| Market crash during scale | Low | Very High | Circuit breakers, 10% cash buffer |
| Correlation spike | Medium | Medium | Real-time correlation monitoring |

### Automatic Scale-Back Triggers

```python
SCALE_BACK_TRIGGERS = {
    'daily_loss_pct': 0.02,      # 2% daily loss → reduce 50%
    'weekly_loss_pct': 0.05,     # 5% weekly loss → pause scaling
    'win_rate_drop': 0.50,       # Win rate < 50% → return to base
    'sharpe_drop': 0.5,          # Sharpe < 0.5 → return to base
    'max_drawdown': 0.10,        # 10% drawdown → halt trading
}
```

---

## Summary: The Scaling Path

### What NOT to Do (Now)

1. ❌ Scale daily investment before Day 90 validation
2. ❌ Implement dynamic allocation during R&D
3. ❌ Add options complexity while building edge
4. ❌ Chase $100/day at expense of risk management

### What TO Do (Now - Days 1-90)

1. ✅ Continue $10/day paper trading
2. ✅ Focus on improving win rate and Sharpe ratio
3. ✅ Accumulate 100+ trades for statistical validity
4. ✅ Document edge characteristics for scaling

### What TO Do (Later - Days 91+)

1. ✅ Implement dynamic percentage-based allocation
2. ✅ Add multi-strategy parallel execution
3. ✅ Integrate options income stream
4. ✅ Scale via Fibonacci sequence funded by profits

---

## References

- `docs/r-and-d-phase.md` - Current R&D phase strategy
- `docs/scaling-roadmap-v2.md` - Technical scaling details
- `docs/PATH_TO_100_DAILY.md` - Detailed action plan
- `docs/north-star-roadmap.md` - Gap analysis
- Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014)

---

**Document Owner**: Claude CTO
**Last Updated**: December 11, 2025
**Next Review**: Day 30 (R&D Month 1 Review)
