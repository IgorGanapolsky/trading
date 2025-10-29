# AI Trading System - Agent Coordination

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

## Next Actions

1. Complete core strategy implementation
2. Build main orchestrator with scheduling
3. Create monitoring dashboard
4. Setup Docker deployment
5. Write comprehensive documentation
6. Begin paper trading validation
