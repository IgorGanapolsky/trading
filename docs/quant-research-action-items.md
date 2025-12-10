# Quant Research: Immediate Action Items

**Based on**: Renaissance Technologies Medallion Fund & Top Quant Hedge Fund Research
**Date**: December 10, 2025

---

## Critical Insights (Must Implement)

### 1. Win Rate Reality Check
- **Medallion achieved 66% annual returns with only 50.75% win rate**
- **Our current target**: 50-60% win rate is PERFECT
- **Focus**: Risk-reward ratio (1:2 minimum) matters MORE than win rate

### 2. Holding Period Strategy
- **Renaissance holds**: Days to hours (NOT months)
- **Our current approach**: Need to shorten holding periods
- **Exit strategy**: Signal-based (MACD/RSI reversal) NOT time-based

### 3. 2024 Market Reality
- **Momentum CRUSHED mean reversion in 2024**
- **AI/tech trends**: Still persistent into 2025
- **Our strategy**: Primary momentum, secondary mean reversion for timing

---

## Immediate Code Changes (Priority Order)

### Priority 1: Exit Strategy (CRITICAL)
**Current Issue**: May be using time-based exits or weak exit signals
**Fix Required**:
```python
# WRONG: Time-based exit
if days_held > 5:
    exit_position()

# RIGHT: Signal-based exit
if (macd_cross_below_signal() or
    rsi > 70 or
    volume_decline_3_days()):
    exit_position()
```

**Implementation**:
- Remove time-based exits (or use only as safety backstop at 10 days max)
- Add MACD signal line crossover as primary exit
- Add RSI >70 as overbought exit
- Add volume decline (3-day MA below 20-day MA) as exit
- Add trailing stop at 1.5× ATR

### Priority 2: Position Sizing (HIGH)
**Current Issue**: May not be using volatility-adjusted sizing
**Fix Required**:
```python
# WRONG: Fixed position size
position_size = account_value * 0.02

# RIGHT: Volatility-adjusted position size
atr = calculate_atr(symbol, period=14)
risk_per_trade = account_value * 0.02
position_size = risk_per_trade / (atr * 1.5)
```

**Implementation**:
- Calculate ATR for each position
- Adjust position size inversely to volatility
- High volatility = smaller positions
- Low volatility = larger positions

### Priority 3: Drawdown Management (HIGH)
**Current Issue**: No tiered drawdown response
**Fix Required**:
```python
def adjust_position_size_for_drawdown(current_dd, base_size):
    if current_dd >= 0.15:  # 15% drawdown
        return base_size * 0.5
    elif current_dd >= 0.10:  # 10% drawdown
        return base_size * 0.75
    elif current_dd >= 0.05:  # 5% drawdown
        return base_size * 0.90
    else:
        return base_size
```

**Implementation**:
- Track current drawdown from peak equity
- Reduce position size at 5%, 10%, 15% drawdown triggers
- Halt trading at 20% drawdown (manual review required)

### Priority 4: Risk-Reward Calculation (MEDIUM)
**Current Issue**: May not be enforcing minimum 1:2 risk-reward
**Fix Required**:
```python
def validate_trade(entry, stop_loss, take_profit):
    risk = entry - stop_loss
    reward = take_profit - entry
    risk_reward_ratio = reward / risk

    if risk_reward_ratio < 2.0:  # Minimum 1:2
        return False  # Reject trade
    return True
```

**Implementation**:
- Calculate risk-reward BEFORE entering trade
- Reject trades with R:R < 1:2
- Target R:R of 1:3 for optimal growth

### Priority 5: Sharpe Ratio Tracking (MEDIUM)
**Current Issue**: Not tracking risk-adjusted returns
**Fix Required**:
```python
def calculate_sharpe_ratio(returns, risk_free_rate=0.0356):
    # Risk-free rate: 3.56% (Alpaca High-Yield Cash APY)
    excess_returns = returns - (risk_free_rate / 252)  # Daily
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
```

**Implementation**:
- Calculate daily/weekly Sharpe ratio
- Target: >1.0 minimum, >1.5 optimal
- Track in system_state.json
- Report in daily CEO reports

---

## Strategy Adjustments

### Momentum-First Approach (2024-2025 Market)
**Based on**: 2024 research showing momentum dramatically outperformed mean reversion

**Entry Strategy** (Hybrid):
1. **Momentum Filter**: MACD > Signal Line (uptrend confirmed)
2. **Mean Reversion Timing**: RSI 30-50 (buy dip in uptrend)
3. **Volume Confirmation**: Volume > 20-day MA

**Hold Strategy** (Momentum):
1. **Stay with trend**: As long as MACD > Signal
2. **Ignore small pullbacks**: Don't exit on minor RSI dips
3. **Trail stop**: Move stop to 1.5× ATR below recent swing low

**Exit Strategy** (Mean Reversion):
1. **MACD crosses below Signal**: Primary exit
2. **RSI > 70**: Overbought, take profit
3. **Volume decline**: 3-day MA < 20-day MA
4. **Trailing stop hit**: 1.5× ATR below swing low

### Signal Combination Weights
Based on Renaissance's ensemble approach:

**Traditional Signals (60%)**:
- MACD: 25%
- RSI: 20%
- Volume: 15%

**LLM Council (30%)**:
- Multi-model sentiment consensus
- News analysis
- Earnings call analysis

**ML Prediction (10%)**:
- Reinforcement learning agent recommendations
- Pattern recognition
- Anomaly detection

---

## Performance Metrics to Track

### Daily Metrics
- [ ] Daily P/L
- [ ] Win rate (rolling 20 trades)
- [ ] Average win / Average loss
- [ ] Expectancy: (Win% × AvgWin) - (Loss% × AvgLoss)
- [ ] Current drawdown from peak

### Weekly Metrics
- [ ] Sharpe ratio (rolling 30 days)
- [ ] Profit factor: Total Profits / Total Losses
- [ ] Max drawdown this week
- [ ] Risk-reward ratio (average of all trades)
- [ ] Correlation to SPY (market beta)

### Monthly Metrics
- [ ] Sharpe ratio (monthly)
- [ ] Sortino ratio (downside deviation)
- [ ] Win rate by strategy type (momentum vs mean reversion)
- [ ] Best/worst performing signals
- [ ] Signal effectiveness review

---

## Testing Protocol

### Week 1-2: Implement Changes
- Add signal-based exits
- Implement volatility-adjusted position sizing
- Add tiered drawdown response
- Enforce 1:2 minimum risk-reward

### Week 3-4: Paper Trade Validation
- Run for 20+ trades
- Target: Win rate >50%, Sharpe >0.5
- Monitor: Max drawdown <20%
- Validate: Risk-reward achieving 1:2+

### Week 5-6: Optimization
- Adjust signal weights based on performance
- Fine-tune ATR multiplier for stops
- Optimize MACD/RSI parameters if needed

### Week 7-8: Final Validation
- 30 days of consistent performance
- Sharpe ratio >1.0
- Max drawdown <15%
- Ready for live deployment

---

## Red Flags (Stop Trading If...)

1. **Sharpe ratio <0.5** for 2 consecutive weeks
2. **Win rate <40%** for 20+ trades
3. **Drawdown >20%** at any time
4. **5 consecutive losses** (reduce size by 50%)
5. **10 consecutive losses** (halt trading, investigate)
6. **Risk-reward consistently <1:1** (strategy broken)

---

## Success Criteria (Go/No-Go for Live Trading)

### Month 1 (Days 1-30)
- ✅ Sharpe ratio >0.5
- ✅ Win rate >45%
- ✅ Max drawdown <20%
- ✅ System reliability 99.9%+

### Month 2 (Days 31-60)
- ✅ Sharpe ratio >1.0
- ✅ Win rate >55%
- ✅ Max drawdown <15%
- ✅ Risk-reward ratio >1:2

### Month 3 (Days 61-90)
- ✅ Sharpe ratio >1.5
- ✅ Win rate >60%
- ✅ Max drawdown <10%
- ✅ Consistent profits ($3-5/day on $10/day investment)

**If all Month 3 criteria met**: Deploy to live trading with $1/day Fibonacci strategy

---

## Quick Reference: Renaissance Principles

1. **50.75% win rate was enough** - Don't obsess over high win rate
2. **Signal-based exits only** - No human interference once strategy live
3. **Days to hours holding** - Short-term statistical arbitrage
4. **Market neutral** - Balance long/short positions
5. **Volume matters** - Thousands of trades, statistical edge
6. **System is king** - Remove emotion completely

---

**Next Steps**: Review current codebase against these action items, prioritize implementations, and begin Week 1-2 changes.
