# North Star Action Plan: Path to $100/Day Net Income

**Created**: December 2, 2025
**Status**: Ready for Implementation
**Priority**: CRITICAL

---

## 🎯 Current State Assessment

### Performance Metrics
- **Daily Investment**: $10/day (paper trading)
- **Current P/L**: +$13.96 total (Day 9 of 90)
- **Win Rate**: 66.7% ✅ (exceeds 60% target)
- **Profit Per Trade**: ~$0.28 (too low)
- **Daily Net Income**: ~$1.74/day (need $100/day = 57x increase)

### System Status
- ✅ Infrastructure: Operational
- ✅ Automation: GitHub Actions working
- ✅ Strategies: MACD + RSI + Volume implemented
- ⚠️ Options Income: $0/day (infrastructure exists, not generating income)
- ⚠️ Agent Systems: Multi-LLM built but may not be enabled
- ⚠️ Scaling: Mentioned in system_state.json but not verified

---

## 🚀 Critical Actions Required (Priority Order)

### 1. VERIFY & IMPLEMENT SCALING ⚠️ MOST CRITICAL

**Current**: $10/day investment
**Target**: $1,000-1,500/day (100-150x scale)

**Immediate Actions**:
1. Check `.env` file for `DAILY_INVESTMENT` value
2. Verify if Nov 25 scaling decision was implemented
3. If not implemented:
   - Start gradual scaling: $10 → $100 → $500 → $1,000/day
   - Test at each level for 1 week before scaling up
   - Update config safety cap if needed (currently $1,000 max)

**Impact**: **10x multiplier** - This alone gets us from $1.74/day → $17.40/day

**Files to Check**:
- `.env` (if exists) or `.env.example`
- `src/core/config.py` (DAILY_INVESTMENT default)
- `data/system_state.json` (check notes from Nov 25)

**Implementation**:
```bash
# Check current value
grep DAILY_INVESTMENT .env

# If scaling needed, update .env:
DAILY_INVESTMENT=100.0  # Start with 10x scale

# Test for 1 week, then scale to:
DAILY_INVESTMENT=500.0  # 50x scale

# Final scale:
DAILY_INVESTMENT=1000.0  # 100x scale
```

---

### 2. ACTIVATE OPTIONS INCOME GENERATION 💰 HIGH PRIORITY

**Current**: $0/day from options
**Target**: $10-30/day from premium selling

**Status Check Needed**:
1. Verify `OptionsAccumulationStrategy` is running
2. Check current stock positions (need 50+ shares for covered calls)
3. Run `options_profit_planner.py` to assess current state
4. Verify options reserve allocation (should be 5% of daily investment)

**Immediate Actions**:
1. **Check Stock Positions**:
   ```bash
   python3 scripts/check_positions.py
   # Or query Alpaca API directly
   ```

2. **Run Options Profit Planner**:
   ```bash
   PYTHONPATH=src python3 scripts/options_profit_planner.py --target-daily 10
   ```

3. **Verify Options Accumulation**:
   - Check if `OptionsAccumulationStrategy` is called in `main.py`
   - Verify daily allocation: 5% of `DAILY_INVESTMENT`
   - At $10/day: $0.50/day → Too slow (need 100 days for 50 shares)
   - At $1,000/day: $50/day → Much faster (10 days for 50 shares)

4. **Activate Options Selling** (once 50+ shares accumulated):
   - Sell weekly covered calls
   - Target: $0.50-1.00 premium per share per week
   - Example: 50 NVDA shares × $0.50/week = $25/week = $3.57/day
   - Need multiple positions to hit $10/day

**Impact**: **$10-30/day passive income** - High ROI, low risk (covered calls)

**Files to Check**:
- `src/strategies/options_accumulation_strategy.py`
- `src/main.py` (check if options strategy is called)
- `scripts/options_profit_planner.py`
- `data/options_signals/` (check for signals)

---

### 3. ENABLE ALL AGENT SYSTEMS 🤖 ALREADY APPROVED

**CEO Directive** (Nov 24, 2025): "Enable ALL dormant systems NOW! $100/mo budget"

**Systems to Enable**:
1. **Multi-LLM Analysis** (sentiment analysis)
   - Cost: $0.50-2/day (~$15-60/month)
   - Status: Built, may not be enabled
   - Action: Set `use_sentiment=True` in strategy calls

2. **DeepAgents** (planning-based trading)
   - Status: Unknown if active
   - Action: Verify if `EliteOrchestrator` is using DeepAgents

3. **LLM Council** (consensus voting)
   - Status: Unknown if active
   - Action: Check `src/core/llm_council_integration.py`

**Immediate Actions**:
1. **Check Current Enablement**:
   ```python
   # In src/main.py or orchestrator:
   # Look for use_sentiment parameter
   # Currently: use_sentiment=True (line 458 in main.py)
   ```

2. **Verify Multi-LLM is Actually Running**:
   - Check logs for MultiLLMAnalyzer calls
   - Verify OpenRouter API key is set
   - Monitor costs (should be <$2/day)

3. **Enable DeepAgents** (if not active):
   - Check `src/orchestration/elite_orchestrator.py`
   - Verify planning phases are enabled

**Impact**: **10-20% improvement** in decision quality

**Files to Check**:
- `src/main.py` (line 458: `use_sentiment=True`)
- `src/strategies/core_strategy.py` (use_sentiment parameter)
- `src/orchestration/elite_orchestrator.py` (DeepAgents integration)
- `.env` (OPENROUTER_API_KEY)

---

### 4. IMPROVE PROFIT PER TRADE 📈 MEDIUM PRIORITY

**Current**: $0.28 profit per trade
**Target**: $1-2 per trade (4-7x improvement)

**Improvements Needed**:
1. **Better Exit Timing**:
   - Current: Buy-and-hold (Tier 1), 3% stop-loss (Tier 2)
   - Add: Dynamic profit-taking (5%, 10%, 15% targets)
   - Add: Trailing stops for winners

2. **Better Entry Timing**:
   - Current: MACD + RSI + Volume momentum
   - Add: Volume confirmation (require above-average volume)
   - Add: Support/resistance levels
   - Add: Economic calendar guardrails (already implemented)

3. **Position Sizing Optimization**:
   - Current: Fixed dollar amounts
   - Improve: Volatility-adjusted sizing (ATR-based)
   - Already have: Kelly Criterion (verify it's being used)

**Immediate Actions**:
1. **Review Backtest Results**:
   - Identify best-performing patterns
   - Find optimal exit points
   - Analyze win rate by holding period

2. **Implement Dynamic Profit-Taking**:
   - Take profits at 5%, 10%, 15% gains
   - Let winners run but lock in profits
   - Use trailing stops for protection

3. **Optimize Position Sizing**:
   - Use ATR for volatility adjustment
   - Verify Kelly Criterion is active
   - Test different sizing strategies

**Impact**: **4-7x multiplier** on profit per trade

**Files to Modify**:
- `src/strategies/core_strategy.py` (add profit-taking logic)
- `src/strategies/growth_strategy.py` (improve exits)
- `src/risk/risk_manager.py` (position sizing)

---

### 5. ENABLE OPTIMIZED ALLOCATION 💎 MEDIUM PRIORITY

**Current**: Legacy allocation (60% ETFs, 20% Growth, 10% IPO, 10% Crowdfunding)
**Target**: Optimized allocation (40% ETFs, 15% Bonds, 15% REITs, 20% Growth, 5% Options, 5% IPO)

**Benefits**:
- 30% defensive allocation (bonds + REITs)
- Dividend income from REITs
- Options reserve for premium income
- Increased growth allocation for higher returns

**Immediate Actions**:
1. **Enable Optimized Allocation**:
   ```bash
   # Add to .env:
   USE_OPTIMIZED_ALLOCATION=true
   ```

2. **Verify Strategies Exist**:
   - Bond strategy: Check `src/strategies/bond_strategy.py`
   - REIT strategy: Check `src/strategies/reit_strategy.py`

3. **Test Allocation**:
   ```python
   from src.core.config import load_config
   config = load_config()
   config.USE_OPTIMIZED_ALLOCATION = True
   allocations = config.get_tier_allocations()
   print(allocations)
   ```

**Impact**: **Better risk-adjusted returns**, income diversification

**Files to Check**:
- `src/core/config.py` (optimized allocation constants)
- `src/strategies/bond_strategy.py` (if exists)
- `src/strategies/reit_strategy.py` (if exists)
- `.env` (USE_OPTIMIZED_ALLOCATION flag)

---

## 📊 Math Check: Path to $100/Day

### Current Performance
- Daily Investment: $10/day
- Win Rate: 66.7%
- Profit Per Trade: $0.28
- **Daily Net Income**: ~$1.74/day

### With Scaling Only (10x)
- Daily Investment: $100/day
- Same win rate & profit per trade
- **Daily Net Income**: ~$17.40/day

### With Scaling + Options Income
- Daily Investment: $1,000/day
- Options Income: $10/day
- Same win rate & profit per trade
- **Daily Net Income**: ~$174/day + $10 options = $184/day gross

### With All Improvements
- Daily Investment: $1,000/day
- Options Income: $30/day
- Improved profit per trade: $1.50 (5x improvement)
- Win Rate: 60% (maintained)
- **Daily Net Income**: ~$900/day gross + $30 options = $930/day gross
- **After costs** (~$30/day agent costs): **~$900/day net**

**Conclusion**: Scaling + Options + Better exits = Path to $100+/day ✅

---

## 🎯 Implementation Timeline

### Week 1: Critical Actions
- [ ] Day 1: Verify current state (scaling, options, agents)
- [ ] Day 2: Implement scaling to $100/day
- [ ] Day 3: Activate options accumulation
- [ ] Day 4: Enable agent systems
- [ ] Day 5: Test and monitor

### Week 2-4: Strategy Improvements
- [ ] Week 2: Implement dynamic profit-taking
- [ ] Week 3: Enable optimized allocation
- [ ] Week 4: Test and validate improvements

### Month 2-3: Scaling
- [ ] Month 2: Scale to $500/day
- [ ] Month 3: Scale to $1,000/day
- [ ] Target: $50-100/day profit

### Month 4-6: Optimization
- [ ] Fine-tune strategies
- [ ] Scale options income to $20-30/day
- [ ] Target: Consistent $100+/day net income

---

## ✅ Success Criteria

### Immediate (Week 1)
- [ ] Daily investment scaled to $100/day
- [ ] Options accumulation active
- [ ] Agent systems enabled
- [ ] Daily net income: $10-20/day

### Short-term (Month 1-2)
- [ ] Daily investment scaled to $500/day
- [ ] Options income: $5/day
- [ ] Daily net income: $50-75/day

### Long-term (Month 3-6)
- [ ] Daily investment scaled to $1,000/day
- [ ] Options income: $10-30/day
- [ ] Daily net income: $100+/day (consistent)

---

## 🚨 Risk Mitigation

1. **Gradual Scaling**: Don't jump from $10 → $1,000/day. Scale gradually: $10 → $100 → $500 → $1,000
2. **Testing**: Test at each scale level for 1 week before scaling up
3. **Stop-Losses**: Ensure all positions have stop-losses
4. **Circuit Breakers**: Daily loss limits must be enforced
5. **Cost Monitoring**: Track agent costs daily (budget: $100/month)

---

## 📝 Next Steps (Do Now)

1. **Verify Current State**:
   ```bash
   # Check daily investment
   grep DAILY_INVESTMENT .env .env.example

   # Check options status
   python3 scripts/options_profit_planner.py

   # Check agent enablement
   grep use_sentiment src/main.py
   ```

2. **Implement Scaling**:
   - Update `.env` with `DAILY_INVESTMENT=100.0`
   - Test for 1 week
   - Scale to $500/day if successful

3. **Activate Options**:
   - Check stock positions
   - Verify options accumulation is running
   - Activate selling when 50+ shares accumulated

4. **Enable Agents**:
   - Verify Multi-LLM is enabled (`use_sentiment=True`)
   - Check DeepAgents status
   - Monitor costs

5. **Monitor & Adjust**:
   - Track daily metrics
   - Adjust based on performance
   - Scale gradually

---

**Last Updated**: December 2, 2025
**Status**: Ready for Implementation
**Priority**: CRITICAL - Start immediately
