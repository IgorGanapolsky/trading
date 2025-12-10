# Options Strategy Roadmap to $100/Day Income

**Created**: December 3, 2025
**Goal**: Transform current system from growth-oriented to consistent daily income ($100/day)
**Target Capital**: $50k-$100k for sustainable income generation

---

## Current State Assessment

### What Already Exists (More Than Expected)

| Component | Status | Location |
|-----------|--------|----------|
| **IV Rank Filter** | ✅ Complete | `src/utils/iv_analyzer.py:333-379` |
| **IV Percentile** | ✅ Complete | `src/utils/iv_analyzer.py:381-423` |
| **Expected Move (McMillan)** | ✅ Complete | `src/utils/iv_analyzer.py:646-728` |
| **Kelly Criterion** | ✅ Complete (0.25x) | `src/risk/kelly.py`, `.claude/skills/position_sizer/` |
| **Delta Management** | ✅ Complete | `src/risk/options_risk_monitor.py:182-269` |
| **Stop-Loss Rules** | ✅ Complete | `src/risk/options_risk_monitor.py:56-60` |
| **Covered Calls** | ✅ Automated | `src/strategies/options_strategy.py` |
| **Rule #1 Put Selling** | ✅ Automated | `src/strategies/rule_one_options.py` |
| **Signal Enhancement** | ✅ Complete | `src/signals/options_signal_enhancer.py` |
| **Credit Strategy IV Gate** | ✅ Enforced | IV Rank < 20% blocks all credit spreads |

### Gaps to Address

| Gap | Priority | Impact on $100/Day |
|-----|----------|-------------------|
| Iron Condor Execution | HIGH | Direct income strategy |
| Income Mode Position Sizing | HIGH | Consistency over growth |
| Gamma Exit Triggers | MEDIUM | Risk protection |
| Spread Margin Calculator | MEDIUM | Capital efficiency |
| Earnings Volatility Crush | LOW | Event risk protection |

---

## Implementation Roadmap

### Phase 1: Income-Focused Position Sizing (Week 1-2)

**Goal**: Add "Income Mode" to position sizer for consistent daily income vs growth.

**File**: `src/risk/kelly.py` and `.claude/skills/position_sizer/scripts/position_sizer.py`

**Current State**:
- Uses 0.25x Kelly (quarter Kelly) - capped at 25% of full Kelly
- Max position: 10% of portfolio
- Aggressive for income goals

**Required Changes**:

```python
# Add to position_sizer.py

class PositionSizingMode(Enum):
    GROWTH = "growth"          # Current: 0.25x Kelly, optimize total return
    INCOME = "income"          # New: Fixed 1-2% risk, optimize win rate
    HALF_KELLY = "half_kelly"  # New: 0.50x Kelly, balanced approach

def calculate_income_mode_size(
    self,
    account_value: float,
    target_daily_income: float = 100.0,
    avg_premium_yield: float = 0.015,  # 1.5% per trade
    trades_per_week: int = 5,
) -> dict:
    """
    Calculate position size for consistent income generation.

    Target: $100/day = $500/week = $2,000/month

    If avg premium yield is 1.5% per trade:
    - Need $500/week from 5 trades
    - Each trade needs to yield $100
    - $100 / 1.5% = $6,667 notional per trade

    For 10% max position: need $66,670 account minimum
    """
    weekly_income = target_daily_income * 5
    income_per_trade = weekly_income / trades_per_week
    required_notional = income_per_trade / avg_premium_yield

    # Cap at 10% of account
    max_notional = account_value * 0.10
    actual_notional = min(required_notional, max_notional)

    return {
        "target_daily_income": target_daily_income,
        "required_notional_per_trade": round(required_notional, 2),
        "actual_notional": round(actual_notional, 2),
        "achievable_daily_income": round(
            (actual_notional * avg_premium_yield * trades_per_week) / 5, 2
        ),
        "minimum_account_for_target": round(required_notional * 10, 2),
        "position_pct": round((actual_notional / account_value) * 100, 2),
    }
```

**Deliverables**:
- [ ] Add `PositionSizingMode` enum to position sizer
- [ ] Add `calculate_income_mode_size()` method
- [ ] Add `--mode income` CLI option
- [ ] Add Half-Kelly (0.50x) option for balanced approach
- [ ] Update skill documentation

---

### Phase 2: Iron Condor Execution Engine (Week 2-3)

**Goal**: Implement automated iron condor execution (highest win-rate income strategy).

**New File**: `src/strategies/iron_condor_strategy.py`

**Why Iron Condors for Income**:
- Win rate: 70-80% (vs 45-55% for directional)
- Defined risk: Max loss = width of spread - premium received
- Theta positive: Time decay works FOR you
- Works in range-bound markets (most of the time)

**Requirements**:

```python
# Iron Condor Strategy Module

class IronCondorStrategy:
    """
    Automated iron condor execution for theta income.

    Entry Criteria:
    - IV Rank > 50 (selling expensive premium)
    - Expected move < strike width (probability of profit)
    - Days to expiration: 30-45 (optimal theta decay)
    - Delta: 16 delta wings (84% probability OTM)

    Exit Criteria:
    - Profit target: 50% of max profit (lock in gains)
    - Stop loss: 2.0x credit received (McMillan rule)
    - Time exit: 21 DTE (avoid gamma risk)
    - Delta breach: Close if delta > 30 on either wing
    """

    # Entry parameters
    MIN_IV_RANK = 50
    TARGET_DTE = 30  # to 45
    TARGET_DELTA = 0.16  # 16 delta wings

    # Exit parameters
    PROFIT_TARGET_PCT = 0.50  # Take profit at 50% max
    STOP_LOSS_MULTIPLIER = 2.0  # Exit at 2x credit
    GAMMA_EXIT_DTE = 21  # Close by 21 DTE to avoid gamma
    DELTA_BREACH_THRESHOLD = 0.30  # Close if wing delta > 30
```

**Deliverables**:
- [ ] Create `src/strategies/iron_condor_strategy.py`
- [ ] Implement entry signal validation
- [ ] Implement multi-leg order execution via Alpaca
- [ ] Add profit target exit (50% max profit)
- [ ] Add gamma risk exit (21 DTE rule)
- [ ] Add delta breach exit trigger
- [ ] Integration tests

---

### Phase 3: Gamma Risk Management (Week 3-4)

**Goal**: Add gamma-based exit triggers (currently only delta-based).

**File**: `src/risk/options_risk_monitor.py`

**Current State**:
- Tracks gamma but doesn't act on it
- Only delta triggers rebalancing
- No expiration week protection

**Required Changes**:

```python
# Add to OptionsRiskMonitor class

# Gamma thresholds
MAX_POSITION_GAMMA = 0.05  # Exit if gamma > 0.05
GAMMA_WARNING_DTE = 14     # Warn if DTE < 14 and gamma rising
EXPIRATION_WEEK_RULE = 7   # Force exit if DTE < 7 for short positions

def check_gamma_risk(self, position: OptionsPosition) -> Optional[dict]:
    """
    Check gamma risk and recommend exit if necessary.

    McMillan Rule: "Gamma is the silent killer of options traders."
    High gamma = position delta changes rapidly = hard to manage.
    """
    dte = (position.expiration_date - date.today()).days

    # Rule 1: Force exit in expiration week for short positions
    if position.side == "short" and dte <= self.EXPIRATION_WEEK_RULE:
        return {
            "action": "CLOSE",
            "reason": f"GAMMA_RISK: DTE={dte} - expiration week rule triggered",
            "urgency": "HIGH",
        }

    # Rule 2: Exit if gamma too high
    if abs(position.gamma) > self.MAX_POSITION_GAMMA:
        return {
            "action": "CLOSE",
            "reason": f"GAMMA_RISK: Gamma={position.gamma:.3f} exceeds {self.MAX_POSITION_GAMMA}",
            "urgency": "MEDIUM",
        }

    # Rule 3: Warn if approaching danger zone
    if dte <= self.GAMMA_WARNING_DTE and abs(position.gamma) > 0.03:
        return {
            "action": "WARN",
            "reason": f"GAMMA_WARNING: DTE={dte}, Gamma={position.gamma:.3f} - consider closing",
            "urgency": "LOW",
        }

    return None
```

**Deliverables**:
- [ ] Add `check_gamma_risk()` method
- [ ] Add expiration week rule (DTE < 7 force exit)
- [ ] Add high gamma threshold exit (gamma > 0.05)
- [ ] Integrate into `run_risk_check()` method
- [ ] Add gamma monitoring dashboard output

---

### Phase 4: Spread Margin Calculator (Week 4-5)

**Goal**: Track buying power and margin requirements for spread positions.

**New File**: `src/risk/spread_margin.py`

**Why This Matters**:
- Spreads require margin/buying power
- Without tracking, can over-allocate capital
- Impacts number of concurrent positions

```python
class SpreadMarginCalculator:
    """
    Calculate margin requirements for options spreads.

    Credit Spread Margin = Width of spread - credit received
    Iron Condor Margin = Max of (put spread width, call spread width) - credit
    """

    def calculate_credit_spread_margin(
        self,
        short_strike: float,
        long_strike: float,
        credit_received: float,
        contracts: int = 1,
    ) -> dict:
        """
        Calculate margin for credit spread.

        Example:
        - Sell 450 put, buy 445 put for $1.50 credit
        - Width = $5, Credit = $1.50
        - Margin = ($5 - $1.50) × 100 × contracts = $350 per contract
        """
        width = abs(short_strike - long_strike)
        margin_per_contract = (width - credit_received) * 100
        total_margin = margin_per_contract * contracts
        max_profit = credit_received * 100 * contracts
        max_loss = total_margin

        return {
            "margin_required": total_margin,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "risk_reward": f"1:{round(max_profit / max_loss, 2)}",
            "breakeven_points": [short_strike - credit_received, short_strike + credit_received],
        }
```

**Deliverables**:
- [ ] Create `src/risk/spread_margin.py`
- [ ] Credit spread margin calculation
- [ ] Iron condor margin calculation
- [ ] Buying power tracking across positions
- [ ] Integration with position sizing

---

### Phase 5: Earnings Volatility Protection (Week 5-6)

**Goal**: Avoid holding premium through earnings (IV crush risk).

**File**: `src/utils/earnings_calendar.py` (new) + integration

**Why This Matters**:
- IV spikes before earnings, crashes after
- If short premium through earnings: IV crush can HELP
- But if wrong about direction: catastrophic loss
- Conservative approach: Close 2-3 days before earnings

```python
class EarningsProtection:
    """
    Manage positions around earnings announcements.

    Rule: Close all short premium positions 3 days before earnings
    unless explicitly configured for earnings plays.
    """

    CLOSE_BEFORE_EARNINGS_DAYS = 3

    async def check_earnings_risk(
        self,
        symbol: str,
        position_expiration: date
    ) -> dict:
        """
        Check if position has earnings risk.

        Returns:
            Dict with earnings date, days until, and action recommendation
        """
        earnings_date = await self._get_next_earnings(symbol)

        if earnings_date is None:
            return {"has_earnings_risk": False}

        days_until_earnings = (earnings_date - date.today()).days
        position_expires_before = position_expiration < earnings_date

        if position_expires_before:
            return {"has_earnings_risk": False, "reason": "Position expires before earnings"}

        if days_until_earnings <= self.CLOSE_BEFORE_EARNINGS_DAYS:
            return {
                "has_earnings_risk": True,
                "action": "CLOSE",
                "reason": f"Earnings in {days_until_earnings} days - close short premium",
                "earnings_date": earnings_date.isoformat(),
            }

        return {
            "has_earnings_risk": True,
            "action": "MONITOR",
            "reason": f"Earnings in {days_until_earnings} days - plan exit",
            "earnings_date": earnings_date.isoformat(),
        }
```

**Deliverables**:
- [ ] Create `src/utils/earnings_calendar.py`
- [ ] Integrate with Alpaca news/events API
- [ ] Add earnings check to risk monitor
- [ ] Auto-close positions 3 days before earnings

---

## Capital Requirements Analysis

### For $100/Day Target

| Account Size | Daily Income | Strategy Mix | Notes |
|--------------|--------------|--------------|-------|
| $25,000 | $25-40 | Covered calls only | PDT limit |
| $50,000 | $50-75 | CC + Iron Condors | Approaching target |
| $75,000 | $75-100 | Full suite | Target achievable |
| $100,000 | $100-150 | Full suite + scaling | Comfortable margin |

### Math Behind $100/Day

**Conservative Theta Selling**:
- Average premium yield: 1.5% per position
- Positions per week: 5 (one per day)
- Win rate: 70%
- Average win: $100, Average loss: $150

```
Weekly Income = (5 × $100 × 0.70) - (5 × $150 × 0.30)
Weekly Income = $350 - $225 = $125/week
Daily Average = $25/day (conservative)
```

**For $100/day**: Need 4x the position size = $400k notional per week
At 10% max position: Need $40k × 5 = $200k account OR
At 20% max position: Need $20k × 5 = $100k account

**Realistic Target**: $50-75k account → $50-75/day income

---

## Implementation Priority

1. **Immediate (This Week)**:
   - Add Income Mode to position sizer
   - This unblocks all other improvements

2. **High Priority (Week 2-3)**:
   - Iron Condor execution engine
   - This is the primary income generator

3. **Medium Priority (Week 4-5)**:
   - Gamma risk management
   - Spread margin calculator

4. **Lower Priority (Week 5-6)**:
   - Earnings protection
   - Enhanced dashboard

---

## Success Metrics

| Metric | Current | Target (90 days) |
|--------|---------|------------------|
| Win Rate | 62.2% (backtest) | 70%+ |
| Daily P/L Variance | High | Low (consistent) |
| Sharpe Ratio | 2.18 | 2.5+ |
| Max Drawdown | Unknown | <5% |
| Days Profitable | Unknown | >70% |
| Avg Daily Income | $5.50 | $50-100 |

---

## Files to Create/Modify

### New Files
- `src/strategies/iron_condor_strategy.py`
- `src/risk/spread_margin.py`
- `src/utils/earnings_calendar.py`

### Files to Modify
- `src/risk/kelly.py` - Add Half-Kelly option
- `.claude/skills/position_sizer/scripts/position_sizer.py` - Add Income Mode
- `src/risk/options_risk_monitor.py` - Add gamma triggers

---

## Next Steps

1. Review this roadmap
2. Approve Phase 1 implementation
3. Begin Income Mode position sizing work

**Note**: The existing codebase is MORE sophisticated than initially assessed. IV Rank filtering, McMillan rules, and delta management are already in place. Focus should be on execution gaps (iron condors) and income optimization (position sizing mode).
