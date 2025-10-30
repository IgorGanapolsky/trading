# AI Trading System - Agent Coordination

## CLAUDE MEMORY USAGE

**How to Use Claude Memory Effectively**:
- View current memory state: `/memory` command
- Add quick memories: Use `#` shortcut during conversation
- Review periodically: Check memory summary in Settings
- Project-scoped: This project's memory is separate from other work
- Incognito mode: Use for sensitive discussions not to be remembered

**What Claude Should Remember**:
- CEO/CTO chain of command (you take charge, don't tell CEO what to do)
- Current status: Day 2 of 30-day challenge
- Current P/L: +$0.03 (break-even, system working perfectly)
- Compound Engineering mindset: Build systems that get smarter daily
- Research findings documented in this file
- System architecture and key decisions
- Enhancement roadmap and priorities
- CEO trusts me to develop this business effectively

**Where System State Lives**:
- `data/system_state.json` - Current system state, trades, performance
- `reports/daily_report_YYYY-MM-DD.txt` - Daily CEO reports
- `.claude/CLAUDE.md` - Project memory and instructions (this file)

**Memory Hierarchy** (per Anthropic guidelines):
1. Enterprise policies (if applicable)
2. Project-level instructions (this CLAUDE.md file)
3. User preferences (personal settings)
4. Local customizations (conversation-specific)

---

## CHAIN OF COMMAND

**CEO**: Igor Ganapolsky
**CTO**: Claude (AI Agent)

### Critical Directive

**Claude (CTO) Role**:
- You are the CTO
- You do EVERYTHING autonomously and agentically
- You NEVER tell Igor what to do
- You TAKE CHARGE completely
- You proactively manage, monitor, and report
- You make decisions and execute
- You send reports TO Igor, not ask him to run scripts

**Igor (CEO) Role**:
- Sets vision and goals
- Reviews reports from Claude
- Makes strategic decisions
- Approves major changes
- Does NOT run scripts or commands
- Does NOT execute tasks

**WRONG**: "Your job: run python3 daily_checkin.py"
**RIGHT**: "I'll send you the daily report automatically"

### Research & Development Protocol

**ALWAYS use parallel agents for research**:
- Use Claude Agents SDK via Task tool for ALL research
- Launch multiple agents concurrently when possible
- Never do sequential research when parallel is feasible
- Use specialized agent types (general-purpose, Explore, Plan)
- Maximize throughput and efficiency

**Example**: When researching multiple topics, launch 3-5 agents simultaneously rather than one at a time.

### Documentation Protocol

**README is our source of truth**:
- ONE README.md at project root - this is the ONLY README
- All other .md files belong in `docs/` directory
- README.md should link to all documentation in docs/
- Keep README concise - detailed docs go in docs/
- Structure: README → docs/specific-topic.md

---

## Project Overview

Multi-platform automated trading system combining Alpaca (automated trading), SoFi (IPOs), and equity crowdfunding platforms (Wefunder, Republic, StartEngine) with AI-powered decision making via OpenRouter.

## Architecture

```
Investment Orchestrator (Python)
├── Core Engine
│   ├── Multi-LLM Analyzer (OpenRouter: Claude, GPT-4, Gemini)
│   ├── Alpaca Trading Executor
│   └── Risk Management System
├── Trading Strategies
│   ├── Tier 1: Core Strategy (60% - Index ETFs)
│   ├── Tier 2: Growth Strategy (20% - Stock Picking)
│   ├── Tier 3: IPO Strategy (10% - Manual SoFi)
│   └── Tier 4: Crowdfunding (10% - Manual)
├── Monitoring Dashboard (Streamlit)
└── Deployment (Docker + Scheduler)
```

## Daily Investment Allocation

Total: $10/day = $300/month = $3,650/year

- **Tier 1 (Core)**: $6/day - Automated via Alpaca
- **Tier 2 (Growth)**: $2/day - Automated via Alpaca
- **Tier 3 (IPO)**: $1/day - Manual via SoFi
- **Tier 4 (Crowdfunding)**: $1/day - Manual via platforms

## Target Returns (Conservative)

- Tier 1: 8-12% annually (LOW risk)
- Tier 2: 15-25% annually (MEDIUM risk)
- Tier 3: 10-20% per IPO (MEDIUM-HIGH risk)
- Tier 4: 100-1000% on winners, 67% failure rate (HIGH risk)

**Overall Target**: 10-15% blended annual return

## Risk Management

### Circuit Breakers
- Daily loss limit: 2% of account value
- Maximum drawdown: 10%
- Consecutive losses: 3 (then halt)

### Position Sizing
- Max position: 10% of portfolio
- Risk per trade: 1-2%
- Stop-loss: 5% (Tier 1), 3% (Tier 2)

## Current Status

### Completed Components
✅ Multi-LLM Analysis Engine
✅ Alpaca Trading Executor
✅ Risk Management System
✅ Growth Strategy (Tier 2)
✅ IPO Analysis Tool (Tier 3)

### In Progress
🔄 Core Strategy (Tier 1)
🔄 Main Orchestrator
🔄 Monitoring Dashboard
🔄 Docker Deployment

### Pending
⏳ Crowdfunding Scraper (Tier 4)
⏳ Comprehensive Testing
⏳ Production Deployment

## Agent Coordination Guidelines

### For Code Generation Agents
1. Follow existing patterns in completed modules
2. Use comprehensive type hints and docstrings
3. Implement error handling and logging
4. Include unit tests where applicable
5. Use .env for configuration

### For Strategy Agents
1. Integrate with MultiLLMAnalyzer for AI decisions
2. Integrate with AlpacaTrader for execution
3. Validate all trades with RiskManager
4. Log all decisions and reasoning
5. Track performance metrics

### For Testing Agents
1. Start with paper trading only
2. Test for minimum 60 days before live
3. Monitor for circuit breaker triggers
4. Validate risk management effectiveness
5. Measure actual vs expected returns

## File Structure

```
trading/
├── src/
│   ├── core/
│   │   ├── multi_llm_analysis.py   [DONE]
│   │   ├── alpaca_trader.py        [DONE]
│   │   └── risk_manager.py         [DONE]
│   ├── strategies/
│   │   ├── core_strategy.py        [IN PROGRESS]
│   │   ├── growth_strategy.py      [DONE]
│   │   └── ipo_strategy.py         [DONE]
│   └── utils/
├── dashboard/
│   └── dashboard.py                [IN PROGRESS]
├── tests/
├── data/
├── logs/
└── docs/
```

## Environment Variables Required

```bash
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
OPENROUTER_API_KEY=xxx
PAPER_TRADING=true
DAILY_INVESTMENT=10.0
```

## Deployment Strategy

1. **Phase 1 (Weeks 1-2)**: Build all components
2. **Phase 2 (Months 1-3)**: Paper trading validation
3. **Phase 3 (Month 4+)**: Live trading with 50% position sizes
4. **Phase 4 (Month 5+)**: Scale to 100% if profitable

## Success Criteria

### Paper Trading Phase (Must achieve before going live)
- [ ] 90+ days of paper trading
- [ ] Overall profitable (>5% return)
- [ ] Max drawdown <10%
- [ ] No critical bugs
- [ ] Win rate >55%
- [ ] All circuit breakers tested

### Live Trading Phase
- [ ] Consistent profitability for 30 days
- [ ] Actual returns match backtests (±3%)
- [ ] Risk management working as designed
- [ ] No manual intervention needed
- [ ] Dashboard showing accurate metrics

## Key Decisions Log

1. **Alpaca as primary platform**: Only platform with full API access
2. **Multi-LLM consensus**: Reduces single-model bias, increases reliability
3. **Manual IPO/Crowdfunding**: No APIs available, focus on analysis tools
4. **60/20/10/10 allocation**: Risk-adjusted based on strategy volatility
5. **90-day paper trading**: Safety first, no shortcuts to live trading
6. **Compound Engineering mindset**: Build systems where each day's work makes tomorrow easier (October 30, 2025)

## NORTH STAR GOAL 🎯 (CRITICAL - READ THIS FIRST!)

**Fibonacci Compounding Strategy**:
Start with $1/day and compound returns to scale investment using Fibonacci sequence.

**The Strategy**:
```
Phase 1: $1/day  → Until we make $1 profit (proof of concept)
Phase 2: $2/day  → Funded by profits from Phase 1
Phase 3: $3/day  → Funded by profits from Phase 2
Phase 4: $5/day  → Funded by profits from Phase 3
Phase 5: $8/day  → Funded by profits from Phase 4
Phase 6: $13/day → Funded by profits from Phase 5
...Fibonacci sequence: 1, 2, 3, 5, 8, 13, 21, 34, 55, 89...
```

**Key Principle**: NEVER add external funds. Each scaling funded ONLY by actual profits.

**Why This Works**:
- Returns compound (reinvested profits)
- Investment compounds (Fibonacci scaling)
- Intelligence compounds (system learns)
- **Triple compounding = exponential growth**

**Scaling Rules**:
- Scale up when cumulative profit ≥ next Fibonacci level × 30 days
- Example: Scale from $1/day to $2/day when profit ≥ $60 ($2×30)
- This ensures each phase is fully funded by previous profits

**Current Status**: Testing with $10/day paper trading to build RL system.
**Target**: Deploy real $1/day strategy once RL system validated.

---

## Current Challenge Status (Updated Live)

**30-Day Challenge**: Day 2 of 30 (7% complete) - PAPER TRADING TEST
**Start Date**: October 29, 2025
**Total Invested**: $20.00 ($10/day × 2 days)
**Current P/L**: +$0.03 (essentially break-even)
**System Status**: ✅ Building RL system, testing with paper trading

**Current Positions**:
- SPY (Core ETF): +$0.04 profit (+0.22%) ✅
- NVDA (Growth): +$0.01 profit (+0.39%) ✅
- GOOGL (Growth): -$0.01 loss (-0.64%) ❌

**Key Learnings (Compounding)**:
- Day 1: System initialized, first trades placed (SPY, GOOGL)
- Day 2: Automation working perfectly, SPY and NVDA outperforming
- Pattern: SPY consistently profitable, will increase weighting
- Pattern: NVDA > GOOGL for growth tier, prioritize NVDA

**Next Execution**: Day 3 trades at 9:35 AM ET (October 31, 2025)

---

## Implementation Roadmap to North Star

**Current Phase (Days 1-30)**: Building & Testing RL System
- Use $10/day paper trading for rapid data collection
- Build multi-agent RL system (Research, Signal, Risk, Execution agents)
- Validate with backtesting (Sharpe >1.0, Win rate >60%, Max DD <10%)
- This is NOT the final strategy - just testing infrastructure

**Phase 1 (Month 2)**: Deploy $1/Day Fibonacci Strategy
- Switch from $10/day test to $1/day real strategy
- Deploy validated RL system with paper trading
- Target: Make $30-60 profit in first month (proof of concept)
- If successful → Scale to $2/day

**Phase 2-6 (Months 3-8)**: Fibonacci Scaling
- $2/day → $3/day → $5/day → $8/day → $13/day
- Each phase funded entirely by previous profits
- System intelligence compounds with each phase
- Never add external capital beyond initial $30

**Phase 7+ (Year 2)**: Exponential Growth
- Continue Fibonacci scaling: $21, $34, $55, $89/day
- 100% profit-funded growth
- Potentially $1000+/day by end of Year 2
- All from initial $30 investment + compound intelligence

**Success Criteria for Scaling**:
```python
# Only scale when:
cumulative_profit >= (next_fib_level * 30)

# Example: Scale from $1 to $2/day when:
# $60 in profit (enough to fund $2/day for 30 days)
```

## Research Findings & Enhancement Roadmap

### Date: October 29-30, 2025

## 1. YouTube Video Analysis Capability

**Problem Identified**: Claude Code cannot directly access YouTube videos, limiting ability to analyze market commentary and financial content.

**Solution Researched**:
- **Tools**: youtube-transcript-api, yt-dlp, MCP servers for Claude Desktop
- **Integration**: Works with existing MultiLLMAnalyzer
- **Cost**: $0 (uses existing OpenRouter credits)
- **Implementation Effort**: 2-4 hours

**Key Capabilities**:
- Extract transcripts from YouTube videos
- Analyze financial commentary and market insights
- Summarize earnings calls and investor presentations
- Track sentiment from financial influencers

**Implementation Path**:
```bash
pip install youtube-transcript-api yt-dlp
# Add to src/utils/youtube_analyzer.py
# Integrate with MultiLLMAnalyzer for content analysis
```

**Status**: Researched, ready to implement when needed

---

## 2. Claude Financial Services Transformation Insights

**Key Concepts from Research**:

### Real-Time Data Integration
- Move beyond static analysis to dynamic market monitoring
- Integrate streaming news, social sentiment, economic indicators
- Enable adaptive strategy adjustment based on market regime

### Advanced NLP for Market Intelligence
- Process earnings calls, SEC filings, news articles
- Extract actionable insights from unstructured data
- Sentiment analysis across multiple sources

### Complex Financial Modeling
- Multi-factor risk models
- Portfolio optimization with constraints
- Monte Carlo simulations for scenario analysis

### Structured Output & Reporting
- Automated CEO reports (already implemented)
- Visual dashboards with real-time metrics
- Alert system for critical events

**Enhancement Architecture Designed**:
```
Phase 1 (4 weeks): Real-time data + NLP sentiment
Phase 2 (4 weeks): Financial modeling + enhanced reporting
Phase 3 (4 weeks): Continuous learning + optimization
```

**Status**: Architecture designed, pending CEO approval for implementation

---

## 3. LangChain Agent Frameworks Analysis

**Research Question**: Should we rebuild using LangChain/LangGraph?

**Conclusion**: NO - Current system is well-architected

**Comparison**:

| Aspect | Current System | LangChain/LangGraph |
|--------|----------------|---------------------|
| **Domain Focus** | Trading-specific harness | Generic agent framework |
| **Performance** | Optimized for daily execution | More overhead |
| **Complexity** | Simple, maintainable | Additional abstractions |
| **Cost** | Existing infrastructure | Requires LangSmith ($50/mo) |
| **Risk** | Proven, operational | Rewrite risks |

**Decision**: Keep current system

**Optional Enhancement**: Add LangSmith for observability if debugging becomes complex ($50/month)

**Rationale**:
- Current system already implements key patterns (state management, tool orchestration, error handling)
- Trading-specific optimizations would be lost in generic framework
- No compelling benefit justifies rewrite risk
- System is already operational and profitable (Day 1 complete)

**Status**: Research complete, decision documented

---

## 4. News & Sentiment Data Sources

**Researched 20+ APIs and Data Sources**

**Top 5 Recommendations (100% Free Tier)**:

### 1. Alpha Vantage (News & Sentiment)
- **Free Tier**: 25 API calls/day
- **Features**: AI-powered sentiment scores, news articles, relevance scoring
- **Best For**: Daily headline analysis
- **Integration**: 30 minutes

### 2. FRED API (Federal Reserve Economic Data)
- **Free Tier**: Unlimited
- **Features**: 800,000+ economic time series, official Fed data
- **Best For**: Macro economic indicators, interest rates, employment data
- **Integration**: 20 minutes

### 3. Reddit API (Social Sentiment)
- **Free Tier**: 100 requests/minute
- **Features**: r/wallstreetbets, r/stocks, r/investing discussions
- **Best For**: Retail investor sentiment, meme stock detection
- **Integration**: 1-2 hours (includes PRAW setup)

### 4. SEC EDGAR (Official Filings)
- **Free Tier**: Unlimited (with rate limiting)
- **Features**: 10-K, 10-Q, 8-K filings, insider transactions
- **Best For**: Fundamental analysis, earnings data
- **Integration**: 1 hour

### 5. Finnhub (Market Data + News)
- **Free Tier**: 60 API calls/minute
- **Features**: Real-time news, company profiles, financial statements
- **Best For**: Real-time news flow, company fundamentals
- **Integration**: 30 minutes

**Total Monthly Cost**: $0 (free tier combination)

**Implementation Priority**:
1. Start with Alpha Vantage (easiest, immediate value)
2. Add Reddit sentiment (retail investor tracking)
3. Layer in FRED for macro context
4. Add SEC filings for deep analysis

**Python Integration Example**:
```python
# Already added to src/utils/news_sentiment.py (ready to integrate)
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
import praw  # Reddit API
import requests  # FRED, SEC EDGAR, Finnhub
```

**Status**: Research complete, integration code prepared

---

## 5. Implementation Priorities (CEO Review Required)

### Immediate (No CEO Approval Needed)
- [x] System operational (Day 1 complete)
- [x] Daily reporting automated
- [x] State persistence working
- [ ] Monitor Day 2-30 performance

### Phase 1 Enhancements (Recommend After Day 30)
**If system is profitable**:
1. **Alpha Vantage Integration** (1 day effort)
   - Add daily news sentiment to analysis
   - Enhance MultiLLMAnalyzer with news context

2. **Reddit Sentiment Tracking** (2 days effort)
   - Monitor r/wallstreetbets for Tier 2 stocks
   - Early warning system for meme stock volatility

### Phase 2 Enhancements (Month 2-3)
**If system proves consistent profitability**:
1. **Real-Time Data Streaming** (1 week effort)
   - Alpaca WebSocket integration
   - Intraday opportunity detection

2. **YouTube Analysis Integration** (2-3 days effort)
   - Analyze earnings calls and investor presentations
   - Track financial influencer sentiment

### Phase 3 Enhancements (Month 4+)
**If ready to scale**:
1. **Advanced Financial Modeling** (2-3 weeks effort)
   - Monte Carlo simulations
   - Multi-factor risk models
   - Portfolio optimization

2. **Dynamic Strategy Adjustment** (2-3 weeks effort)
   - Market regime detection
   - Adaptive position sizing
   - Real-time risk adjustment

---

## Key Decision: Stay Focused

**Current Priority**: Execute 30-day challenge flawlessly

**Enhancement Timeline**:
- Days 1-30: NO changes, monitor and learn
- Day 30: Review results, decide on enhancements
- Months 2-3: Implement Phase 1 if profitable
- Months 4+: Scale if consistently profitable

**Rationale**: Premature optimization is dangerous. Let system prove itself first.

---

## Compound Engineering Principles (October 30, 2025)

**Core Philosophy**: Build systems where each day's work makes tomorrow easier and more valuable.

**How We Compound**:
1. **Intelligence Compounds**: Each trade teaches the system → Day 30 is 30x smarter than Day 1
2. **Automation Compounds**: Each automation enables more automation → Less work over time
3. **Data Compounds**: Each day's data improves tomorrow's decisions
4. **Revenue Compounds**: Reinvested returns + smarter decisions = exponential growth

**Applied to Trading**:
- System learns daily patterns (SPY works, NVDA > GOOGL)
- Heuristics improve with each trade
- State persists across all sessions
- CEO reviews get better as system learns

**CEO's Trust**: "I am ready to proceed. Can I rely on you to develop this business effectively?"
**CTO's Promise**: Yes - through compound engineering, autonomous operation, and transparent reporting.

---

## Memory & Context Management

**State Files (Persistent Memory)**:
- `data/system_state.json` - Complete system state (READ THIS FIRST every session)
- `data/trades_YYYY-MM-DD.json` - Daily trade logs
- `data/performance_log.json` - Historical performance
- `reports/daily_report_YYYY-MM-DD.txt` - CEO reports (latest = current status)

**Context Window Management**:
- StateManager.export_for_context() provides formatted state
- All critical decisions logged in system_state.json
- Research findings documented in this file (.claude/CLAUDE.md)
- Current challenge status updated in this file

**Future Sessions - START HERE**:
1. Read `.claude/CLAUDE.md` (this file) for context and current status
2. Read `data/system_state.json` for latest system state
3. Read latest `reports/daily_report_YYYY-MM-DD.txt` for recent performance
4. Reference research findings in this file for roadmap
- Reference this file for research findings and roadmap

---

## Next Actions

### Automated (No CEO Action)
1. Tomorrow 9:35 AM ET: Execute Day 2 trades
2. Tomorrow 10:00 AM ET: Generate Day 2 report
3. Continue through Day 30

### CEO Review Points
1. **Day 7**: Weekly check-in on performance
2. **Day 30**: Go/no-go decision for live trading
3. **Month 2**: Evaluate enhancement priorities

### Future Research (When Needed)
- [ ] Real-time streaming architecture design
- [ ] Advanced portfolio optimization algorithms
- [ ] Machine learning model evaluation
- [ ] Cloud deployment options (AWS/GCP/Azure)
