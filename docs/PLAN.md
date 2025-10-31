# 90-Day R&D Roadmap - Building Profitable Trading Edge

**Version**: 1.0
**Created**: October 31, 2025
**CEO**: Igor Ganapolsky
**CTO**: Claude (AI Agent)
**Status**: APPROVED - R&D Phase Active

---

## Executive Summary

**Mission**: Build a profitable AI trading system that can make $100+/day by Month 6.

**Current State (Day 3)**:
- ✅ Infrastructure: World-class (automation, hygiene, reporting)
- ❌ Trading Edge: None (simple buy-and-hold, no profitability)
- 📊 P/L: -$0.14 (expected in R&D phase)

**90-Day Goal**:
- Build momentum + RL trading system
- Achieve 60%+ win rate, 1.5+ Sharpe ratio
- Validate profitability before scaling Fibonacci

**Total R&D Investment**: ~$270 over 90 days (acceptable tuition fee)

---

## Month 1: Infrastructure + Data Collection (Days 1-30)

**Goal**: Build foundation, collect market data, validate automation

### Week 1 (Days 1-7) ✅ COMPLETED
- ✅ Fibonacci strategy implemented
- ✅ Autonomous pre-commit hygiene
- ✅ Daily CEO reporting automated
- ✅ NVDA + GOOGL disruptive innovation focus
- ✅ Repository 100% organized
- ✅ R&D phase strategy documented

### Week 2 (Days 8-14) 🎯 IN PROGRESS
**Priority**: Add Technical Indicators

**Tasks**:
1. Install pandas-ta library (`pip install pandas-ta`)
2. Add MACD calculation to CoreStrategy
3. Add volume metrics to momentum scoring
4. Implement RSI overbought/oversold detection
5. Test indicators with backtesting on SPY, NVDA, GOOGL

**Deliverables**:
- `src/core/indicators.py` - Technical indicator library
- Updated `CoreStrategy.calculate_momentum()` with MACD + volume
- Test script validating indicators work correctly

**Success Metrics**:
- MACD correctly identifies bullish/bearish crossovers
- Volume ratio accurately detects high-volume days
- RSI identifies overbought (>70) and oversold (<30) conditions

### Week 3 (Days 15-21)
**Priority**: Build Entry/Exit Rules

**Tasks**:
1. Implement entry filters (RSI 40-70, MACD bullish, volume >150%)
2. Implement exit rules (4% profit target, 2% stop-loss, trailing stop)
3. Add position tracking for entry/exit logic
4. Test with paper trading on 3-5 stocks

**Deliverables**:
- Entry/exit rule engine
- Stop-loss and profit-taking automation
- Trailing stop-loss implementation

**Success Metrics**:
- Entry filters reduce false signals by 30%+
- Stop-loss triggers prevent losses >2%
- Profit-taking captures 4%+ gains

### Week 4 (Days 22-30)
**Priority**: Month 1 Review & Data Analysis

**Tasks**:
1. Analyze 30 days of collected market data
2. Calculate win rate, Sharpe ratio, max drawdown
3. Identify best-performing stocks (SPY vs NVDA vs GOOGL)
4. Document patterns and learnings
5. Generate Month 1 CEO report

**Deliverables**:
- 30-day performance report
- Data analysis notebook (Jupyter)
- Month 1 retrospective document

**Success Metrics (Month 1)**:
- System reliability: 99.9%+ (no missed executions)
- Data collected: 30 days × 3 stocks = 90 data points
- Win rate: >45% (acceptable for baseline)
- Infrastructure: Zero critical bugs

---

## Month 2: Build Trading Edge (Days 31-60)

**Goal**: Implement momentum system, build RL agents, achieve profitability

### Week 5 (Days 31-37)
**Priority**: Introspective Agent Architecture

**Tasks**:
1. Build Research Agent (news sentiment, market analysis)
2. Add Alpha Vantage API integration
3. Add Reddit sentiment API (r/wallstreetbets)
4. Implement bias detection introspection
5. Test Research Agent with live data

**Deliverables**:
- `src/agents/research_agent.py`
- Alpha Vantage + Reddit API wrappers
- Introspection logging framework

**Success Metrics**:
- Research Agent detects bias when news sentiment diverges from technicals
- Sentiment scores correlate with next-day price movement
- Agent self-checks pass 95%+ of the time

### Week 6 (Days 38-44)
**Priority**: Signal Agent with MACD + RSI + Volume

**Tasks**:
1. Build Signal Agent (entry/exit signals)
2. Implement indicator consensus checking
3. Add overbought/oversold detection
4. Test Signal Agent with 30 days of historical data
5. Validate signals against actual price movements

**Deliverables**:
- `src/agents/signal_agent.py`
- Indicator consensus algorithm
- Signal backtesting framework

**Success Metrics**:
- Signal Agent achieves 55%+ win rate on backtest
- Indicator consensus correctly flags weak signals
- Overbought detection prevents buying tops

### Week 7 (Days 45-51)
**Priority**: Risk Agent + Circuit Breakers

**Tasks**:
1. Build Risk Agent (position sizing, safety)
2. Implement circuit breakers (daily loss limit, max drawdown)
3. Add Kelly Criterion position sizing
4. Test Risk Agent blocks unsafe trades
5. Integrate Risk Agent with Signal Agent

**Deliverables**:
- `src/agents/risk_agent.py`
- Circuit breaker system
- Position sizing calculator

**Success Metrics**:
- Risk Agent blocks 100% of trades violating risk rules
- Circuit breakers trigger on simulated losses
- Kelly Criterion position sizing balances risk/reward

### Week 8 (Days 52-60)
**Priority**: Execution Agent + Master Orchestrator

**Tasks**:
1. Build Execution Agent (order management)
2. Add pre-flight order validation
3. Build Master Orchestrator (coordinates subagents)
4. End-to-end testing of full agent system
5. Generate Month 2 CEO report

**Deliverables**:
- `src/agents/execution_agent.py`
- `src/agents/master_orchestrator.py`
- Full agent system integration

**Success Metrics (Month 2)**:
- Full agent system executes trades autonomously
- Win rate: >55%
- Sharpe ratio: >1.0
- Daily profit: $0.50-2/day
- Zero trade execution errors

---

## Month 3: Validate & Optimize (Days 61-90)

**Goal**: 30 days of live testing, tune parameters, validate profitability

### Week 9 (Days 61-67)
**Priority**: Live Testing Phase 1

**Tasks**:
1. Deploy full agent system to production
2. Monitor introspection outputs daily
3. Track win rate, Sharpe ratio, drawdown
4. Tune MACD/RSI thresholds based on live data
5. Document edge cases and failures

**Deliverables**:
- Live trading dashboard
- Introspection log analysis
- Parameter tuning notebook

**Success Metrics**:
- Zero critical bugs in production
- Agents self-debug 80%+ of issues
- Win rate maintains >55%

### Week 10 (Days 68-74)
**Priority**: Alpha Vantage News Integration

**Tasks**:
1. Add Alpha Vantage news sentiment to Research Agent
2. Integrate news sentiment into signal generation
3. Test correlation between news and price movements
4. A/B test: signals with vs without news sentiment
5. Measure ROI of news sentiment

**Deliverables**:
- News sentiment integration
- A/B test results
- ROI analysis

**Success Metrics**:
- News sentiment improves win rate by 3-5%
- Agent detects and flags misleading news
- Positive ROI on Alpha Vantage API cost

### Week 11 (Days 75-81)
**Priority**: Dynamic Position Sizing

**Tasks**:
1. Implement Kelly Criterion position sizing
2. Add volatility-adjusted sizing
3. Test with different market conditions
4. Compare fixed vs dynamic sizing
5. Measure risk-adjusted returns

**Deliverables**:
- Dynamic position sizing system
- Volatility calculator
- Comparative analysis

**Success Metrics**:
- Dynamic sizing improves Sharpe ratio by 10%+
- Reduces max drawdown by 20%+
- Better risk-adjusted returns

### Week 12 (Days 82-90)
**Priority**: Final Validation & Go/No-Go Decision

**Tasks**:
1. Analyze 30 days of live trading performance
2. Calculate final metrics (win rate, Sharpe, max drawdown)
3. Generate comprehensive 90-day report
4. CEO review meeting: Go/No-Go for scaling
5. Document lessons learned

**Deliverables**:
- 90-day performance report
- Go/No-Go recommendation
- Scaling plan (if approved)

**Success Criteria (Day 90)**:
```python
if (
    win_rate > 60 and
    sharpe_ratio > 1.5 and
    max_drawdown < 10 and
    profitable_last_30_days and
    no_critical_bugs
):
    # APPROVED: Scale to live trading with Fibonacci
    recommendation = "GO - Scale to Live Trading"
else:
    # EXTEND R&D: Need more time
    recommendation = "EXTEND R&D - Need more data"
```

---

## Key Milestones & Gates

### Gate 1: Day 30 (Month 1 Review)
**Question**: Is infrastructure solid?
- ✅ PASS: System reliability >99%, zero critical bugs
- ❌ FAIL: Extend Month 1, fix infrastructure issues

### Gate 2: Day 60 (Month 2 Review)
**Question**: Do we have a trading edge?
- ✅ PASS: Win rate >55%, Sharpe >1.0, profitable
- ❌ FAIL: Extend Month 2, refine agent system

### Gate 3: Day 90 (Final Review)
**Question**: Ready to scale with real money?
- ✅ PASS: Win rate >60%, Sharpe >1.5, profitable 30 days
- ❌ FAIL: Extend R&D, need more validation

---

## Success Metrics Summary

| Metric | Month 1 Target | Month 2 Target | Month 3 Target | Final (Day 90) |
|--------|---------------|---------------|---------------|----------------|
| **Win Rate** | >45% | >55% | >60% | >60% |
| **Sharpe Ratio** | >0.8 | >1.0 | >1.5 | >1.5 |
| **Max Drawdown** | <15% | <12% | <10% | <10% |
| **Daily Profit** | Break-even | $0.50-2 | $3-5 | $3-5 |
| **System Uptime** | >99% | >99.5% | >99.9% | >99.9% |
| **Agent Introspection** | N/A | 80% self-debug | 90% self-debug | 95% self-debug |

---

## Risk Management During R&D

### Financial Risk
- **Max R&D Cost**: $270 over 90 days
- **Daily Investment**: $3-10/day via Fibonacci
- **Acceptable Loss**: Break-even to -$50 total
- **Stop-Loss**: If losses exceed -$100, pause and review

### Technical Risk
- **Backup Strategy**: Revert to simple momentum if agents fail
- **Circuit Breakers**: Active at all times
- **Manual Override**: CEO can pause system anytime

### Time Risk
- **Milestone Reviews**: Day 30, 60, 90
- **No-Go Threshold**: If not profitable by Day 120, pivot strategy
- **Extension Policy**: Max 30-day extensions per gate

---

## Post-R&D Scaling Plan (Month 4+)

**If Day 90 = GO**:

### Month 4 (Days 91-120)
- Switch from paper trading to live trading
- Start true Fibonacci: $1/day
- Enroll in Alpaca High-Yield Cash (3.56% APY)
- Target: Make $30-60 profit

### Month 5 (Days 121-150)
- Scale to $2/day (if $60 profit achieved)
- Enable OpenRouter Multi-LLM (cost now justified)
- Add more stocks to universe (10-15 total)
- Target: Make $90-120 profit

### Month 6 (Days 151-180)
- Scale to $3-5/day Fibonacci phase
- Add IPO tier (manual via SoFi)
- Daily profits $10-30/day
- Target: Prove North Star strategy works

### Year 1 Goal
- Scale to $13-21/day Fibonacci phase
- Daily profits $100-200/day
- All profit-funded, zero external capital added
- Validate Fibonacci compounding strategy

---

## Weekly CEO Check-Ins

**Every Friday 5 PM**:
1. Review week's trades and P/L
2. Analyze agent introspection logs
3. Discuss blockers or concerns
4. Adjust next week's priorities
5. Update PLAN.md with learnings

**Format**:
- 📊 Performance: Win rate, Sharpe, P/L
- 🤖 Agents: Introspection highlights
- 🚧 Blockers: Technical or strategic issues
- 📈 Next Week: Top 3 priorities

---

## Decision Log

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| Oct 31 | Adopt R&D Phase (90 days) | Need to build trading edge before scaling | Focus on system, not daily P/L |
| Oct 31 | Introspective Agent Architecture | Anthropic research shows improved safety/performance | Build safer, smarter agents |
| Oct 31 | Target 60% win rate, 1.5 Sharpe | Industry benchmarks for profitable momentum systems | Realistic, achievable targets |

---

## Open Questions

1. **Should we add more stocks to universe?**
   - Current: SPY, NVDA, GOOGL (3 stocks)
   - Option: Expand to top 10-15 disruptive stocks
   - Decision: Week 8 based on Month 2 performance

2. **When to enable OpenRouter Multi-LLM?**
   - Current: Disabled (not cost-effective at $3/day)
   - Trigger: When daily profit >$10/day consistently
   - Decision: Month 3 or 4

3. **Should we add crypto exposure (COIN, MARA)?**
   - Risk: Very high volatility (beta 3.0+)
   - Reward: Potential for outsized returns
   - Decision: Month 6 if system proves profitable

---

## Appendix: Technology Stack

**Core Trading**:
- Python 3.11+
- Alpaca API (paper trading → live)
- yfinance (historical data)

**Technical Indicators**:
- pandas-ta (MACD, RSI, volume)
- numpy (calculations)

**AI/ML**:
- Claude Agents SDK (introspective agents)
- OpenRouter (Multi-LLM, disabled during R&D)

**Data Sources**:
- Alpha Vantage (news sentiment)
- Reddit API (social sentiment)
- FRED API (economic indicators)

**Infrastructure**:
- Pre-commit hooks (hygiene)
- Git + GitHub (version control)
- Python scripts (automation)

---

**Version History**:
- v1.0 (Oct 31, 2025): Initial 90-day R&D roadmap
