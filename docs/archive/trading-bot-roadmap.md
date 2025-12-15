# Trading Bot Roadmap: Path to $100/Day

**Date:** 2025-12-10
**Author:** Claude CTO
**Status:** ACTIVE - Implementation in Progress

---

## Executive Summary: The Brutal Truth

### The Math Problem

| Metric | Current Reality | Required for $100/Day |
|--------|-----------------|----------------------|
| **Daily Investment** | $10/day | N/A (investment ≠ income) |
| **Paper Account** | ~$100,000 | $100,000 (sufficient for options) |
| **Required Daily Return** | 0.1% net | 0.1% net on $100k = $100 |
| **Current Strategy** | Buy & Hold (Wealth Preservation) | Income Generation (Theta Decay) |

**Diagnosis:** We're building a **savings bot** but measuring it against **income bot** metrics.

---

## The Architecture Mismatch

### Current System (Wealth Preservation)
```
Signal Flow:
  MomentumAgent → RLFilter → LLM Sentiment → Risk Manager → BUY SPY/QQQ

Problem:
  - SPY average daily move: 0.04%
  - $100k × 0.04% = $40/day (BEFORE fees, slippage, losing days)
  - To reliably make $100/day on SPY alone = Need $250k+ capital
```

### Required System (Income Generation)
```
Signal Flow:
  ThetaAgent → IV Analysis → Credit Spread Selection → Risk Manager → SELL PREMIUM

Why This Works:
  - Sell 2 put credit spreads per day on SPY
  - Each spread: ~$50 credit, ~$200 max risk (25% return on risk)
  - Daily income: $100 from time decay (theta)
  - Market can move ±5% and you still profit
```

---

## Asset Class Alignment Matrix

| Asset Class | Current Status | $100/Day Verdict | Action |
|-------------|----------------|------------------|--------|
| **Equities (SPY/QQQ)** | ✅ Active (Core) | 🔴 FAIL | Demote to "base holdings" |
| **Options (Credit Spreads)** | ⚠️ Code exists, not primary | 🟢 THE PATH | Promote to primary income |
| **Crypto (BTC/ETH)** | ✅ Active (weekends) | 🟡 POSSIBLE | Add mean-reversion weekend strategy |
| **Bonds (TLT)** | ✅ Active (hedge) | 🔴 N/A | Keep as volatility hedge only |

---

## Implementation Roadmap

### Phase 1: Kill the Noise (Week 1)
**Priority: HIGH**

1. **Disable social sentiment for ETFs**
   - SPY/QQQ move on macro data (CPI, Fed), not Reddit/YouTube
   - File: `src/utils/unified_sentiment.py`
   - Action: Create ETF bypass list, skip sentiment gate for SPY/QQQ/IWM

2. **Fix execution timing**
   - Current: 9:35 AM ET (first 30 minutes = amateur hour)
   - Target: 3:55 PM ET (Market on Close = true daily trend)
   - File: `.github/workflows/daily-trading.yml`

### Phase 2: Validate the Foundation (Week 2)
**Priority: HIGH**

1. **Historic backtest validation**
   - Create `scripts/backtest_historic.py`
   - Test against: 2020 (Covid crash), 2022 (Bear market)
   - Pass criteria: <15% max drawdown, Sharpe >0.5

2. **Fix backtest rigor**
   - Current: 60-day window captures single regime
   - Required: 5-year window including multiple regimes

### Phase 3: The Theta Pivot (Week 3-4)
**Priority: CRITICAL**

1. **Promote ThetaAgent to primary income strategy**
   - Existing code: `src/strategies/credit_spreads.py` (750+ lines, McMillan-based)
   - Current status: Side feature, not integrated into daily flow
   - Action: Integrate into `TradingOrchestrator` as Gate 5

2. **Implementation:**
   ```python
   # New Gate 5: Theta Harvest
   if self.equity >= 5000 and market_regime == "calm":
       spreads = credit_spreads_strategy.scan_universe()
       if spreads and spreads[0].confidence > 0.7:
           execute_credit_spread(spreads[0])
   ```

3. **Risk parameters (McMillan):**
   - IV Rank > 30% for premium selling
   - Target delta: 0.25 (75% probability of profit)
   - DTE: 30-45 days (optimal theta decay)
   - Stop loss: 2x credit received

### Phase 4: Crypto Weekend Engine (Week 5)
**Priority: MEDIUM**

1. **Create CryptoWeekendAgent**
   - Strategy: Mean reversion on Saturday/Sunday
   - Rationale: Low liquidity causes fake dumps → buy dip, sell rebound

2. **Implementation:**
   ```python
   class CryptoWeekendAgent:
       # Weekend mean reversion strategy
       # BTC/ETH oversold (RSI < 30) on weekends = BUY
       # Take profit at +2% or RSI > 50
   ```

---

## Technical Debt to Address

### 1. Single-Asset Bias
**Problem:** `AlpacaExecutor` is hard-coded for equity market hours (9:30-4:00)
**Fix:** Create polymorphic executors:
- `EquityExecutor` (9:30 AM - 4:00 PM ET)
- `OptionsExecutor` (9:30 AM - 4:00 PM ET)
- `CryptoExecutor` (24/7)

### 2. Risk Manager Incompatibility
**Problem:** Current risk manager uses daily loss limits appropriate for stocks
- Stocks: 2% daily loss = bad day
- Crypto: 2% = Tuesday morning
- Options: 50% loss before expiry = normal (can still profit)

**Fix:** Asset-class-specific risk profiles:
```python
RISK_PROFILES = {
    "equity": {"daily_loss_limit": 0.02, "position_limit": 0.10},
    "crypto": {"daily_loss_limit": 0.05, "position_limit": 0.05},
    "options": {"max_loss_per_spread": 0.02, "concurrent_spreads": 3}
}
```

### 3. Sentiment Gate Over-engineering
**Problem:** Using LLMs to analyze Reddit sentiment for SPY is burning compute for noise
**Fix:**
- ETFs (SPY, QQQ, IWM): Macro-economic data only (CPI, Fed, yields)
- Individual stocks (NVDA, GOOGL): Keep sentiment gates active
- Options: IV rank and Greeks only, no sentiment

---

## Capital Requirements (Reality Check)

### For $100/Day Safely via Options
- **Account size:** $25,000 minimum (to meet PDT rules and have margin)
- **Strategy:** Credit spreads with defined risk
- **Expected win rate:** 70-80% (with proper delta selection)
- **Math:** 2 spreads/day × $50 avg credit × 80% win rate = $80/day net

### For $100/Day Safely via Stocks
- **Account size:** $250,000+ (without leverage)
- **Strategy:** Swing trading with strict risk management
- **Expected daily return:** 0.04% net
- **Math:** $250k × 0.04% = $100/day

### Current Account ($100k paper)
- **Realistic target via theta:** $50-75/day
- **Path to $100/day:** Scale to $150k+ OR improve win rate to 85%+

---

## Success Metrics

### Week 1 Goals
- [ ] ETF sentiment bypass implemented
- [ ] Execution timing moved to 3:55 PM

### Week 2 Goals
- [ ] Historic backtest script created
- [ ] 2020/2022 stress tests passing

### Week 4 Goals
- [ ] Credit spreads integrated into daily flow
- [ ] First theta income generated

### Week 8 Goals
- [ ] 30-day track record of theta income
- [ ] Average daily premium: $50+

---

## Files to Modify

| File | Change | Priority |
|------|--------|----------|
| `src/utils/unified_sentiment.py` | Add ETF bypass list | HIGH |
| `.github/workflows/daily-trading.yml` | Change cron to 3:55 PM | HIGH |
| `src/orchestrator/main.py` | Add Gate 5 (Theta Harvest) | CRITICAL |
| `src/strategies/credit_spreads.py` | Integrate into orchestrator | CRITICAL |
| `scripts/backtest_historic.py` | Create new file | HIGH |
| `src/core/config.py` | Add asset-class risk profiles | MEDIUM |

---

## Conclusion

**Stop building a Tesla to drive to the grocery store.**

The current architecture is sophisticated (AI/RL/LLM gates) but the destination is wrong (buy SPY).

**Simplify the engine, upgrade the destination.**

1. ETFs don't need LLM sentiment analysis → Use macro data
2. $100/day requires income generation → Sell premium, don't buy shares
3. Credit spreads code exists → Promote it from side feature to primary strategy
4. Backtest on crashes → Prove the system survives before scaling

---

*Last Updated: 2025-12-10*
*Next Review: Weekly*
