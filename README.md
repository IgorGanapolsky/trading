# AI-Powered Automated Trading System

A comprehensive automated trading system that combines AI-powered market analysis with systematic risk management. The system uses multiple LLM providers (Claude, GPT-4, Gemini) for ensemble sentiment analysis and implements a four-tiered strategy framework for balanced risk-adjusted returns.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Setup Instructions](#setup-instructions)
- [Configuration Reference](#configuration-reference)
- [Trading Strategies](#trading-strategies)
- [Risk Management](#risk-management)
- [Monitoring and Alerts](#monitoring-and-alerts)
- [Troubleshooting](#troubleshooting)
- [Development Guide](#development-guide)
- [Testing](#testing)
- [Production Deployment](#production-deployment)
- [FAQ](#faq)

---

## Overview

> **Current Phase**: R&D Phase (Days 1-90) - Building Profitable Trading Edge
> **Status**: Day 3 of 90 | P/L: -$0.14 | Focus: Infrastructure + Data Collection
> **Goal**: Build momentum + RL system that can make $100+/day by Month 6

### Project Goals

This trading system aims to achieve consistent, risk-adjusted returns through:

1. **Introspective AI Agents**: Multi-agent system with self-debugging and bias detection
2. **Momentum Trading Edge**: MACD + RSI + Volume indicators for profitable entries/exits
3. **Systematic Risk Management**: Circuit breakers, position sizing, and automated stop-losses
4. **Fibonacci Compounding**: Scale investment using Fibonacci sequence funded by profits
5. **Full Automation**: Scheduled daily execution with comprehensive reporting

### Key Features

- Multi-LLM analysis using Claude 3.5 Sonnet, GPT-4o, and Gemini 2.0 Flash
- Four-tier strategy allocation system (60/20/10/10)
- Automated daily trading with Alpaca API
- Comprehensive risk management with circuit breakers
- Real-time portfolio monitoring and alerts
- Paper trading mode for safe testing
- Historical performance tracking and analytics

### Target Performance

| Tier | Strategy | Allocation | Target Return | Risk Level |
|------|----------|------------|---------------|------------|
| 1 | Core Index Momentum | 60% | 8-12% | LOW |
| 2 | Growth Stock Picking | 20% | 15-25% | MEDIUM |
| 3 | IPO Analysis | 10% | 20-40% | HIGH |
| 4 | Options/Swing Trading | 10% | 25-50% | VERY HIGH |

**Overall Portfolio Target**: 12-18% annual return with controlled drawdown

---

## Architecture

### Introspective Multi-Agent System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   MASTER TRADING AGENT (Orchestrator)                    │
│  • Coordinates subagents with introspection at each step                 │
│  • Aggregates decisions with bias detection                              │
│  • Final go/no-go authority with safety checks                           │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬───────────────────┐
        │                   │                   │                   │
        ▼                   ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  RESEARCH AGENT  │ │   SIGNAL AGENT   │ │   RISK AGENT    │ │ EXECUTION AGENT │
├──────────────────┤ ├──────────────────┤ ├─────────────────┤ ├─────────────────┤
│ DATA SOURCES:    │ │ INDICATORS:      │ │ SAFETY CHECKS:  │ │ ORDER MGMT:     │
│ • News (Alpha    │ │ • MACD           │ │ • Circuit       │ │ • Pre-flight    │
│   Vantage)       │ │ • RSI            │ │   breakers      │ │   validation    │
│ • Social (Reddit)│ │ • Volume ratio   │ │ • Position      │ │ • Alpaca API    │
│ • Macro (FRED)   │ │ • Momentum       │ │   limits        │ │ • Fill confirm  │
│ • Market data    │ │   scores         │ │ • Stop-loss     │ │                 │
├──────────────────┤ ├──────────────────┤ ├─────────────────┤ ├─────────────────┤
│ INTROSPECTION:   │ │ INTROSPECTION:   │ │ INTROSPECTION:  │ │ INTROSPECTION:  │
├──────────────────┤ ├──────────────────┤ ├─────────────────┤ ├─────────────────┤
│ "Am I biased by  │ │ "Do indicators   │ │ "Is this trade  │ │ "Does order     │
│  recent news?"   │ │  agree?"         │ │  safe?"         │ │  match intent?" │
│                  │ │                  │ │                 │ │                 │
│ "Is data         │ │ "Are we at an    │ │ "Do I have      │ │ "Are market     │
│  reliable?"      │ │  extreme?"       │ │  capacity?"     │ │  hours OK?"     │
│                  │ │                  │ │                 │ │                 │
│ "Sources         │ │ "Any indicator   │ │ "Risk rules     │ │ "Quantity       │
│  aligned?"       │ │  contradictions?"│ │  violated?"     │ │  correct?"      │
└──────────────────┘ └──────────────────┘ └─────────────────┘ └─────────────────┘
         │                    │                     │                    │
         └────────────────────┴─────────────────────┴────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   ALPACA TRADING API    │
                          │   (Paper/Live Trading)  │
                          └─────────────────────────┘
```

### Decision Flow with Introspection

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DAILY TRADING WORKFLOW                           │
└─────────────────────────────────────────────────────────────────────────┘

09:35 AM ET - Market Open
     │
     ├─► [1] RESEARCH AGENT: Analyze Market
     │    ├─► Fetch news sentiment (Alpha Vantage)
     │    ├─► Check social sentiment (Reddit r/wallstreetbets)
     │    ├─► Get macro indicators (FRED API)
     │    └─► 🔍 INTROSPECT: "Am I biased? Is data reliable?"
     │         ├─► ✅ PASS → confidence: 0.85
     │         └─► ❌ BIAS DETECTED → reduce confidence: 0.60
     │
     ├─► [2] SIGNAL AGENT: Generate Trade Signal
     │    ├─► Calculate MACD (bullish/bearish crossover)
     │    ├─► Calculate RSI (overbought/oversold)
     │    ├─► Check volume ratio (confirmation)
     │    ├─► Calculate momentum scores
     │    └─► 🔍 INTROSPECT: "Do indicators agree?"
     │         ├─► ✅ CONSENSUS >75% → strong signal
     │         └─► ❌ CONSENSUS <75% → weak signal, skip trade
     │
     ├─► [3] RISK AGENT: Validate Trade
     │    ├─► Check circuit breakers (daily loss, max drawdown)
     │    ├─► Validate position size (Kelly Criterion)
     │    ├─► Check consecutive losses
     │    └─► 🔍 INTROSPECT: "Is trade safe?"
     │         ├─► ✅ ALL CHECKS PASS → approve trade
     │         └─► ❌ RISK VIOLATION → block trade
     │
     ├─► [4] EXECUTION AGENT: Execute Order
     │    ├─► Pre-flight validation (symbol, quantity, side)
     │    ├─► Verify market hours
     │    ├─► Submit order to Alpaca API
     │    └─► 🔍 INTROSPECT: "Does order match intent?"
     │         ├─► ✅ INTENT VERIFIED → execute
     │         └─► ❌ MISMATCH → abort
     │
     └─► [5] MASTER AGENT: Final Review
          ├─► Aggregate all introspection results
          ├─► Log decision trail for audit
          └─► Generate CEO report

10:00 AM ET - Report Generated
     │
     └─► CEO receives daily report with:
          • Trades executed
          • Agent introspection highlights
          • Performance metrics
          • Next day preview
```

### Data Flow Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                   │
├───────────────────────────────────────────────────────────────────────┤
│ Alpha Vantage API  │  Reddit API  │  FRED API  │  Alpaca Market Data │
│ (News Sentiment)   │  (Social)    │  (Macro)   │  (Prices, Volume)   │
└─────────┬──────────┴──────┬──────┴─────┬──────┴──────────┬───────────┘
          │                 │            │                 │
          └─────────────────┴────────────┴─────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   DATA PROCESSING LAYER     │
                    │  • Technical Indicators     │
                    │  • Sentiment Aggregation    │
                    │  • Feature Engineering      │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   AGENT REASONING LAYER     │
                    │  • Multi-agent coordination │
                    │  • Introspection checks     │
                    │  • Decision aggregation     │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   EXECUTION LAYER           │
                    │  • Order validation         │
                    │  • Alpaca API integration   │
                    │  • Position tracking        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   STATE MANAGEMENT          │
                    │  • data/system_state.json   │
                    │  • Trade logs               │
                    │  • Performance tracking     │
                    └─────────────────────────────┘
```

### System Components

```
trading/
├── src/
│   ├── agents/                    # 🤖 Introspective Agent System
│   │   ├── research_agent.py      # Market analysis + bias detection
│   │   ├── signal_agent.py        # MACD/RSI/Volume + consensus
│   │   ├── risk_agent.py          # Safety checks + circuit breakers
│   │   ├── execution_agent.py     # Order mgmt + pre-flight validation
│   │   └── master_orchestrator.py # Agent coordination
│   │
│   ├── core/                      # Core Trading Infrastructure
│   │   ├── indicators.py          # Technical indicators (MACD, RSI, etc.)
│   │   ├── alpaca_trader.py       # Alpaca API integration
│   │   ├── risk_manager.py        # Risk rules + circuit breakers
│   │   └── multi_llm_analysis.py  # Multi-LLM sentiment (future)
│   │
│   ├── strategies/                # Trading Strategies
│   │   ├── core_strategy.py       # Tier 1: Index ETFs (SPY, QQQ, VOO)
│   │   └── growth_strategy.py     # Tier 2: Disruptive (NVDA, GOOGL)
│   │
│   └── utils/                     # Utilities
│       ├── news_sentiment.py      # Alpha Vantage integration
│       └── youtube_analyzer.py    # YouTube transcript analysis
│
├── scripts/                       # Automation Scripts
│   ├── autonomous_trader.py       # Daily execution (Fibonacci)
│   ├── daily_checkin.py          # CEO reporting
│   └── validate_setup.py         # System validation
│
├── .claude/                       # Claude Code Configuration
│   ├── CLAUDE.md                  # Project memory & strategy
│   └── skills/                    # Claude skills
│       ├── precommit_hygiene/     # Auto file organization
│       ├── financial_data_fetcher/
│       └── portfolio_risk_assessment/
│
├── docs/                          # Documentation
│   ├── AGENT_ARCHITECTURE.md      # 🆕 Introspective agents design
│   ├── PLAN.md                    # 🆕 90-day R&D roadmap
│   └── ark_invest_research_report.md
│
├── data/                          # System State (gitignored)
│   ├── system_state.json          # Current state & heuristics
│   └── trades_YYYY-MM-DD.json     # Daily trade logs
│
└── reports/                       # CEO Reports
    └── daily_report_YYYY-MM-DD.txt
```

**Key Documentation**:
- 📘 [PLAN.md](docs/PLAN.md) - 90-Day R&D Roadmap
- 🤖 [AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md) - Introspective Agent Design
- 📋 [CLAUDE.md](.claude/CLAUDE.md) - Project Memory & Strategy

---

## Component Overview

1. **Multi-LLM Analysis Engine** (`src/core/multi_llm_analysis.py`)
   - Parallel queries to Claude, GPT-4, and Gemini
   - Ensemble sentiment scoring
   - IPO analysis and stock evaluation
   - Market outlook generation

2. **Risk Manager** (`src/core/risk_manager.py`)
   - Position sizing calculation
   - Circuit breaker system
   - Trade validation
   - Consecutive loss tracking

3. **Alpaca Trader** (`src/core/alpaca_trader.py`)
   - Order execution (market, limit, stop)
   - Portfolio management
   - Account data retrieval
   - Historical data fetching

4. **Strategy Modules** (`src/strategies/`)
   - Core Strategy: Index ETF momentum
   - Growth Strategy: S&P 500 stock picking
   - IPO Strategy: New issue analysis

---

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Alpaca Trading API account (paper or live)
- OpenRouter API account (for LLM access)
- Git

### 5-Minute Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd trading

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Edit with your API keys

# 5. Test the system (paper trading)
python -m src.strategies.core_strategy
```

---

## Setup Instructions

### 1. Prerequisites

#### System Requirements
- **Operating System**: macOS, Linux, or Windows 10+
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 2GB RAM
- **Disk Space**: 500MB for code and logs
- **Internet**: Stable connection for API calls

#### Required Accounts

**Alpaca Trading** (Required)
- Sign up at https://alpaca.markets
- Choose paper trading account (recommended for testing)
- Note your API Key and Secret Key

**OpenRouter** (Required for AI Analysis)
- Sign up at https://openrouter.ai
- Add credits to your account (~$10 recommended)
- Generate API key from dashboard

### 2. Installation

```bash
# Clone repository
git clone <repository-url>
cd trading

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import alpaca_trade_api; import openai; print('Installation successful!')"
```

### 3. API Key Setup

#### Alpaca API Keys

1. Log in to your Alpaca account
2. Navigate to "Paper Trading" section
3. Generate API Key:
   - Go to "API Keys" under account settings
   - Click "Generate New Key"
   - Copy both API Key and Secret Key
   - Store securely (never commit to git)

#### OpenRouter API Key

1. Log in to OpenRouter dashboard
2. Navigate to "API Keys" section
3. Click "Create New Key"
4. Add a descriptive name (e.g., "Trading Bot")
5. Copy the generated key
6. Add credits: Recommended $10-20 for testing

### 4. Environment Configuration

Create `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```bash
# Required API Keys
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Trading Configuration
PAPER_TRADING=true                # Set to false for live trading (BE CAREFUL!)
DAILY_INVESTMENT=10.0             # Daily investment amount in USD

# Strategy Allocation (must sum to 1.0)
TIER1_ALLOCATION=0.60             # Core index strategy
TIER2_ALLOCATION=0.20             # Growth stock picking
TIER3_ALLOCATION=0.10             # IPO investments
TIER4_ALLOCATION=0.10             # Swing trading

# Risk Management
MAX_DAILY_LOSS_PCT=2.0            # Stop trading if daily loss exceeds 2%
MAX_POSITION_SIZE_PCT=10.0        # Maximum 10% in single position
MAX_DRAWDOWN_PCT=10.0             # Stop trading if drawdown exceeds 10%
STOP_LOSS_PCT=5.0                 # Default stop-loss percentage

# Alert Configuration (optional)
ALERT_EMAIL=your.email@example.com
ALERT_WEBHOOK_URL=https://hooks.example.com/your-webhook
```

### 5. Running Locally

#### Test Individual Components

```bash
# Test Multi-LLM Analyzer
python -m src.core.multi_llm_analysis

# Test Risk Manager
python -m src.core.risk_manager

# Test Alpaca Connection
python -m src.core.alpaca_trader

# Test Core Strategy
python -m src.strategies.core_strategy
```

#### Run Daily Trading

```bash
# Single execution (manual)
python main.py

# Schedule with cron (daily at 9:45 AM ET)
# Add to crontab: crontab -e
45 9 * * 1-5 cd /path/to/trading && /path/to/venv/bin/python main.py >> logs/trading.log 2>&1
```

### 6. Docker Deployment

#### Build Docker Image

```bash
# Build image
docker build -t trading-bot .

# Run container
docker run -d \
  --name trading-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  trading-bot
```

#### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**docker-compose.yml** example:

```yaml
version: '3.8'

services:
  trading-bot:
    build: .
    container_name: trading-bot
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - TZ=America/New_York
```

---

## Configuration Reference

### Environment Variables

#### Core Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ALPACA_API_KEY` | string | *required* | Alpaca API key |
| `ALPACA_SECRET_KEY` | string | *required* | Alpaca secret key |
| `OPENROUTER_API_KEY` | string | *required* | OpenRouter API key for LLM access |
| `PAPER_TRADING` | boolean | `true` | Enable paper trading mode |
| `DAILY_INVESTMENT` | float | `10.0` | Daily investment amount (USD) |

#### Strategy Allocation

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TIER1_ALLOCATION` | float | `0.60` | Core index strategy (60%) |
| `TIER2_ALLOCATION` | float | `0.20` | Growth stock picking (20%) |
| `TIER3_ALLOCATION` | float | `0.10` | IPO investments (10%) |
| `TIER4_ALLOCATION` | float | `0.10` | Swing trading (10%) |

**Note**: Allocations must sum to 1.0

#### Risk Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_DAILY_LOSS_PCT` | float | `2.0` | Maximum daily loss percentage before circuit breaker |
| `MAX_POSITION_SIZE_PCT` | float | `10.0` | Maximum position size as % of portfolio |
| `MAX_DRAWDOWN_PCT` | float | `10.0` | Maximum drawdown before circuit breaker |
| `STOP_LOSS_PCT` | float | `5.0` | Default stop-loss percentage for positions |

#### Alert Configuration (Optional)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ALERT_EMAIL` | string | `null` | Email address for alerts |
| `ALERT_WEBHOOK_URL` | string | `null` | Webhook URL for notifications (Slack, Discord, etc.) |

### Configuration Examples

#### Conservative Configuration
```env
DAILY_INVESTMENT=5.0
TIER1_ALLOCATION=0.80
TIER2_ALLOCATION=0.15
TIER3_ALLOCATION=0.05
TIER4_ALLOCATION=0.00
MAX_DAILY_LOSS_PCT=1.0
MAX_POSITION_SIZE_PCT=5.0
```

#### Aggressive Configuration
```env
DAILY_INVESTMENT=50.0
TIER1_ALLOCATION=0.40
TIER2_ALLOCATION=0.30
TIER3_ALLOCATION=0.15
TIER4_ALLOCATION=0.15
MAX_DAILY_LOSS_PCT=5.0
MAX_POSITION_SIZE_PCT=20.0
```

---

## Trading Strategies

### Tier 1: Core Index Momentum (60% Allocation)

**Target Return**: 8-12% annually | **Risk**: LOW

#### Strategy Overview
- **Universe**: SPY, QQQ, VOO (major index ETFs)
- **Execution**: Daily dollar-cost averaging
- **Daily Allocation**: $6 (60% of $10 daily budget)
- **Selection Method**: Momentum-based with AI sentiment overlay
- **Rebalancing**: Monthly

#### How It Works

1. **Daily Execution**:
   ```
   Morning (9:45 AM ET):
   ├─ Query multi-LLM for market sentiment
   ├─ Calculate momentum scores for each ETF
   │  ├─ 1-month return (50% weight)
   │  ├─ 3-month return (30% weight)
   │  └─ 6-month return (20% weight)
   ├─ Adjust for volatility and Sharpe ratio
   ├─ Apply sentiment boost/penalty
   ├─ Select ETF with highest adjusted score
   └─ Execute $6 purchase
   ```

2. **Momentum Calculation**:
   - Multi-period returns weighted by recency
   - Volatility adjustment (penalize high volatility)
   - Sharpe ratio bonus (reward risk-adjusted returns)
   - RSI indicator (avoid overbought conditions)

3. **Risk Management**:
   - 5% trailing stop-loss on all positions
   - Monthly rebalancing to maintain equal weight
   - Pause buying during very bearish sentiment

#### Example Execution

```python
from src.strategies.core_strategy import CoreStrategy

# Initialize strategy
strategy = CoreStrategy(
    daily_allocation=6.0,
    etf_universe=['SPY', 'QQQ', 'VOO'],
    stop_loss_pct=0.05
)

# Execute daily
order = strategy.execute_daily()

# Check if rebalancing needed
if strategy.should_rebalance():
    rebalance_orders = strategy.rebalance_portfolio()
```

---

### Tier 2: Growth Stock Picking (20% Allocation)

**Target Return**: 15-25% annually | **Risk**: MEDIUM

#### Strategy Overview
- **Universe**: S&P 500 stocks
- **Execution**: Weekly stock selection
- **Weekly Allocation**: $10 (5 days × $2)
- **Position Count**: Maximum 2 stocks
- **Holding Period**: 2-4 weeks
- **Exit Strategy**: 3% stop-loss, 10% take-profit

#### How It Works

1. **Weekly Screening Process**:
   ```
   Monday (After Market Open):
   ├─ AI pre-screening of S&P 500
   │  └─ Multi-LLM filters 500 → ~50 candidates
   ├─ Technical filters
   │  ├─ Momentum > 0 (positive 20-day return)
   │  ├─ RSI between 30-70 (not extreme)
   │  └─ Volume > 1.2x average
   ├─ Multi-LLM consensus scoring
   │  ├─ Query Claude, GPT-4, Gemini
   │  ├─ Aggregate scores (0-100)
   │  └─ Weight: 50% technical + 50% consensus
   └─ Select top 2 stocks for purchase
   ```

2. **Position Management**:
   - **Stop-Loss**: Automatic sell at 3% loss
   - **Take-Profit**: Automatic sell at 10% gain
   - **Max Hold**: Exit after 4 weeks regardless of P/L
   - **Weekly Review**: Re-evaluate after 2 weeks minimum hold

3. **Technical Scoring** (0-100 points):
   - Momentum (0-25 pts): 20-day price performance
   - RSI (0-25 pts): Optimal range 30-70
   - Volume (0-25 pts): Above average volume ratio
   - Moving Averages (0-25 pts): Golden cross bonus

#### Example Execution

```python
from src.strategies.growth_strategy import GrowthStrategy

# Initialize strategy
strategy = GrowthStrategy(weekly_allocation=10.0)

# Execute weekly (run every Monday)
orders = strategy.execute_weekly()

# Execute orders with Alpaca
for order in orders:
    strategy.trader.submit_order(order)
```

---

### Tier 3: IPO Analysis (10% Allocation)

**Target Return**: 20-40% annually | **Risk**: HIGH

#### Strategy Overview
- **Platform**: SoFi (manual execution, no API)
- **Execution**: Manual investment with AI decision support
- **Daily Allocation**: $1 (saved for IPO opportunities)
- **Analysis**: Multi-LLM comprehensive scoring
- **Investment Size**: Based on conviction level

#### How It Works

1. **Daily Balance Tracking**:
   ```python
   from src.strategies.ipo_strategy import IPOStrategy

   strategy = IPOStrategy(daily_deposit=1.0)
   strategy.track_daily_deposit()  # Run daily
   ```

2. **IPO Analysis Process**:
   ```
   When IPO Opportunity Appears:
   ├─ Gather company data
   │  ├─ Financials (revenue, growth, profitability)
   │  ├─ Underwriters
   │  ├─ Valuation and price range
   │  └─ Business model and competitors
   ├─ Multi-dimensional scoring (0-100)
   │  ├─ Underwriter Quality (20%)
   │  │  └─ Top-tier banks = higher score
   │  ├─ Financial Health (40%)
   │  │  ├─ Revenue growth
   │  │  ├─ Profitability/margins
   │  │  └─ Valuation reasonableness
   │  ├─ Market Timing (15%)
   │  │  └─ Overall IPO market conditions
   │  └─ Multi-LLM Analysis (25%)
   │     ├─ Claude investment thesis
   │     └─ GPT-4 risk assessment
   ├─ Generate recommendation
   │  ├─ INVEST (score ≥ 65 + low red flags)
   │  └─ PASS (score < 65 or red flags present)
   └─ Create detailed report
   ```

3. **Investment Allocation**:
   - **High Confidence** (score ≥ 75): 30% of available balance
   - **Medium Confidence** (score 65-74): 20% of balance
   - **Low Confidence** (score 55-64): 10% of balance
   - **Pass** (score < 55): No investment

#### Example Analysis

```python
from src.strategies.ipo_strategy import IPOStrategy

strategy = IPOStrategy(daily_deposit=1.0)

# Example company data
company_data = {
    'name': 'TechCorp Inc',
    'ticker': 'TECH',
    'industry': 'Cloud Software',
    'valuation': 5_000_000_000,
    'revenue': 500_000_000,
    'revenue_growth': 45.0,
    'net_income': -50_000_000,
    'underwriters': ['Goldman Sachs', 'Morgan Stanley'],
    'business_model': 'Enterprise SaaS platform',
    'competitors': ['Salesforce', 'ServiceNow']
}

# Analyze IPO
analysis = strategy.analyze_ipo(company_data)

# Generate detailed report
strategy.generate_ipo_report(
    company_data['name'],
    analysis
)

# Review report and manually invest via SoFi
print(f"Recommendation: {analysis['recommendation']}")
print(f"Target Allocation: ${analysis['target_allocation']:.2f}")
```

#### Key Evaluation Criteria

**Underwriter Quality** (Top-tier banks indicate higher quality):
- Goldman Sachs, Morgan Stanley, JPMorgan → High score
- Wells Fargo, RBC, Jefferies → Medium score
- Lesser-known banks → Lower score

**Financial Red Flags**:
- Revenue declining > 10%
- Massive losses (>50% margin) with large revenue base
- Weak underwriting syndicate
- Excessive risk factors (>10 in S-1 filing)

---

### Tier 4: Swing Trading (10% Allocation)

**Target Return**: 25-50% annually | **Risk**: VERY HIGH

#### Strategy Overview
- **Status**: Manual execution with AI support
- **Approach**: Short-term momentum trades (3-10 days)
- **Daily Allocation**: $1 (pooled for opportunities)
- **Instruments**: Individual stocks, sector ETFs
- **Analysis**: Technical + AI sentiment

#### Coming Soon
This tier is currently in development. Features will include:
- Breakout pattern detection
- Multi-LLM sentiment for swing candidates
- Automated entry/exit signals
- Risk-adjusted position sizing

---

## Risk Management

### Overview

The Risk Manager is the guardian of your capital, implementing multiple layers of protection:

1. **Circuit Breakers** - Automatic trading suspension
2. **Position Sizing** - Intelligent allocation limits
3. **Trade Validation** - Pre-execution risk checks
4. **Loss Tracking** - Consecutive loss monitoring

### Circuit Breakers

#### Daily Loss Limit

Automatically suspends trading if daily losses exceed threshold.

```python
# Configuration
MAX_DAILY_LOSS_PCT = 2.0  # Stop at 2% daily loss

# Example
Account Value: $10,000
Daily P&L: -$250 (-2.5%)
Result: Circuit breaker triggered, trading suspended for the day
```

**Recovery**: Resets at start of next trading day.

#### Maximum Drawdown

Monitors peak-to-trough decline and stops trading if exceeded.

```python
# Configuration
MAX_DRAWDOWN_PCT = 10.0  # Stop at 10% drawdown

# Example
Peak Account Value: $12,000
Current Value: $10,500
Drawdown: 12.5%
Result: Circuit breaker triggered, trading suspended
```

**Recovery**: Manual review required; resumes when account above threshold.

#### Consecutive Losses

Warns (but doesn't stop) after multiple consecutive losing trades.

```python
# Configuration
MAX_CONSECUTIVE_LOSSES = 3

# Example
Losses in a row: 3
Result: Warning alert sent, continue with caution
```

### Position Sizing

#### Maximum Position Size

Limits single position to percentage of portfolio.

```python
# Configuration
MAX_POSITION_SIZE_PCT = 10.0  # Max 10% per position

# Example
Portfolio Value: $10,000
Maximum Position: $1,000 (10%)
Trade Attempt: $1,500 (15%)
Result: Trade rejected - exceeds limit
```

#### Risk-Based Sizing

Calculate position size based on risk tolerance.

```python
from src.core.risk_manager import RiskManager

risk_mgr = RiskManager()

# Calculate safe position size
position_size = risk_mgr.calculate_position_size(
    account_value=10000,
    risk_per_trade_pct=1.0,  # Risk 1% per trade
    price_per_share=150.0
)

print(f"Safe position: {position_size} shares")
# Output: Safe position: 66 shares (≈$10,000 × 1% / $150)
```

### Trade Validation

Every trade is validated before execution:

```python
from src.core.risk_manager import RiskManager

risk_mgr = RiskManager()

validation = risk_mgr.validate_trade(
    symbol='AAPL',
    amount=1500.0,
    sentiment_score=0.75,
    account_value=10000.0,
    trade_type='BUY'
)

if validation['valid']:
    # Execute trade
    print("Trade approved")
else:
    # Reject trade
    print(f"Trade rejected: {validation['reason']}")

# Check warnings
for warning in validation['warnings']:
    print(f"Warning: {warning}")
```

**Validation Checks**:
- Circuit breaker status
- Position size limits
- Sentiment score validity
- Trade amount reasonableness
- Sentiment-action alignment

### Risk Metrics

Track comprehensive risk statistics:

```python
risk_mgr = RiskManager()

# Record trade results
risk_mgr.record_trade_result(-150.0)  # Loss
risk_mgr.record_trade_result(200.0)   # Profit
risk_mgr.record_trade_result(-100.0)  # Loss

# Get metrics
metrics = risk_mgr.get_risk_metrics()

print(f"Win Rate: {metrics['trade_statistics']['win_rate_pct']}%")
print(f"Consecutive Losses: {metrics['trade_statistics']['consecutive_losses']}")
print(f"Circuit Breaker: {metrics['account_metrics']['circuit_breaker_triggered']}")
```

### Best Practices

1. **Start Conservative**: Use paper trading with small amounts
2. **Monitor Daily**: Review circuit breaker status and P&L
3. **Respect Limits**: Never override circuit breakers manually
4. **Keep Records**: Log all trades and risk events
5. **Regular Reviews**: Weekly performance and risk assessment

---

## Monitoring and Alerts

### Logging

All system activity is logged to `logs/` directory:

```
logs/
├── trading.log           # Main trading activity
├── risk_alerts.log       # Risk management events
├── llm_analysis.log      # AI analysis logs
└── errors.log            # Error tracking
```

#### Log Levels

- **INFO**: Normal operations (trades, analysis)
- **WARNING**: Risk alerts, unusual conditions
- **ERROR**: Failed operations, API errors
- **CRITICAL**: Circuit breakers, system failures

#### Example Log Entry

```
2025-10-28 09:45:23 - INFO - [CORE STRATEGY] Executing daily routine
2025-10-28 09:45:25 - INFO - [MULTI-LLM] Market sentiment: BULLISH (0.65)
2025-10-28 09:45:28 - INFO - [CORE STRATEGY] Selected ETF: QQQ (score: 87.3)
2025-10-28 09:45:30 - INFO - [ALPACA] BUY order submitted: QQQ x 0.0147 @ $408.50
2025-10-28 09:45:31 - INFO - [RISK MANAGER] Trade approved - within limits
```

### Alert Types

#### Email Alerts

Configure email notifications for critical events:

```env
# .env configuration
ALERT_EMAIL=your.email@example.com
```

**Alert Triggers**:
- Circuit breaker activated
- Daily loss exceeds warning threshold (1.5%)
- Consecutive losses reach limit
- Trade execution failures
- API connection issues

#### Webhook Alerts

Send notifications to Slack, Discord, or custom endpoints:

```env
# .env configuration
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Webhook Payload Example**:
```json
{
  "type": "risk_alert",
  "severity": "critical",
  "message": "Circuit breaker triggered - daily loss limit exceeded",
  "details": {
    "daily_pl": -250.50,
    "daily_pl_pct": -2.5,
    "account_value": 10000.00,
    "threshold": -2.0
  },
  "timestamp": "2025-10-28T09:45:30Z"
}
```

### Performance Dashboard

Monitor real-time performance (coming soon):

```bash
# Start dashboard
streamlit run dashboard/app.py
```

**Dashboard Features**:
- Real-time P&L tracking
- Strategy performance breakdown
- Risk metrics visualization
- Trade history and analytics
- Account summary

### Health Checks

Verify system health:

```bash
# Run health check script
python scripts/health_check.py
```

**Checks Include**:
- API connectivity (Alpaca, OpenRouter)
- Environment configuration
- Account status
- Balance verification
- Recent trade activity
- Log file integrity

---

## Troubleshooting

### Common Issues

#### 1. API Connection Errors

**Symptom**: `AlpacaTraderError: API connection failed`

**Solutions**:
```bash
# Verify API keys
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Alpaca Key:', os.getenv('ALPACA_API_KEY')[:10] + '...')"

# Test connection
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(paper=True); print(t.get_account_info())"

# Check network connectivity
ping api.alpaca.markets

# Verify environment variables loaded
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Loaded:', 'ALPACA_API_KEY' in os.environ)"
```

**Common Causes**:
- Missing or incorrect API keys
- Network connectivity issues
- Alpaca service outage
- Wrong base URL (paper vs live)

---

#### 2. LLM Analysis Failures

**Symptom**: `No valid sentiment scores found in responses`

**Solutions**:
```bash
# Check OpenRouter API key
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OpenRouter Key:', os.getenv('OPENROUTER_API_KEY')[:10] + '...')"

# Test LLM connectivity
python -c "from src.core.multi_llm_analysis import MultiLLMAnalyzer; a = MultiLLMAnalyzer(); print('LLM client initialized')"

# Check OpenRouter credits
# Visit: https://openrouter.ai/credits

# Reduce LLM load (use fewer models)
# In code: models=[LLMModel.CLAUDE_35_SONNET]  # Use only one model
```

**Common Causes**:
- Insufficient OpenRouter credits
- API rate limiting
- Network timeout issues
- Invalid API key

---

#### 3. Trade Execution Blocked

**Symptom**: `Circuit breaker triggered - trading suspended`

**Solutions**:
```bash
# Check risk metrics
python -c "from src.core.risk_manager import RiskManager; rm = RiskManager(); print(rm.get_risk_metrics())"

# Review circuit breaker status
python scripts/check_risk_status.py

# Reset daily counters (if new trading day)
python -c "from src.core.risk_manager import RiskManager; rm = RiskManager(); rm.reset_daily_counters()"

# Review recent trades and losses
tail -n 100 logs/trading.log | grep "LOSS\|Circuit"
```

**Common Causes**:
- Daily loss limit exceeded (2%)
- Maximum drawdown exceeded (10%)
- Account blocked by Alpaca
- Insufficient buying power

---

#### 4. Installation Issues

**Symptom**: `ModuleNotFoundError: No module named 'alpaca_trade_api'`

**Solutions**:
```bash
# Verify virtual environment activated
which python  # Should show path in venv/

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check for conflicting packages
pip list | grep -i alpaca

# Clear pip cache and reinstall
pip cache purge
pip install -r requirements.txt --no-cache-dir

# Use specific Python version
python3.9 -m pip install -r requirements.txt
```

---

#### 5. Missing or Incorrect Configuration

**Symptom**: `ValueError: daily_allocation must be positive`

**Solutions**:
```bash
# Verify .env file exists
ls -la .env

# Check .env format (no spaces around =)
cat .env

# Validate configuration
python scripts/validate_config.py

# Reset to defaults
cp .env.example .env.backup
cp .env.example .env
# Then edit with your values
```

**Correct Format**:
```env
DAILY_INVESTMENT=10.0          ✓ Correct
DAILY_INVESTMENT = 10.0        ✗ Wrong (spaces)
DAILY_INVESTMENT="10.0"        ✗ Wrong (quotes)
```

---

#### 6. Insufficient Buying Power

**Symptom**: `OrderExecutionError: Insufficient buying power`

**Solutions**:
```bash
# Check account balance
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); print(t.get_account_info())"

# Reduce daily allocation
# Edit .env: DAILY_INVESTMENT=5.0

# Close unprofitable positions
python scripts/close_positions.py

# Wait for settled funds (T+2 settlement)
```

---

#### 7. Data Fetching Errors

**Symptom**: `MarketDataError: Historical data retrieval failed`

**Solutions**:
```bash
# Verify market hours
date  # Check current time

# Test market data access
python -c "import yfinance as yf; print(yf.Ticker('SPY').history(period='1d'))"

# Check symbol validity
python -c "import yfinance as yf; print(yf.Ticker('INVALID').info)"

# Use alternative data period
# In code: period='5d' instead of period='1d'
```

---

#### 8. Docker Issues

**Symptom**: `docker: Error response from daemon`

**Solutions**:
```bash
# Verify Docker running
docker ps

# Check Docker logs
docker logs trading-bot

# Rebuild image
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check volume permissions
ls -la logs/ data/

# View container environment
docker exec trading-bot env | grep -E 'ALPACA|OPENROUTER'
```

---

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set debug level in Python
export LOG_LEVEL=DEBUG

# Run with verbose output
python -m src.strategies.core_strategy --verbose

# Enable debug in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

1. **Check Logs**: Always review `logs/errors.log` first
2. **Test Components**: Run individual modules to isolate issues
3. **Verify API Status**:
   - Alpaca: https://status.alpaca.markets
   - OpenRouter: https://openrouter.ai/status
4. **Review Documentation**: Re-read relevant sections
5. **Community Support**: [Add your support channel info]

### Emergency Procedures

#### Stop All Trading Immediately

```bash
# Method 1: Kill the process
pkill -f "python.*trading"

# Method 2: Cancel all orders via Alpaca
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); t.cancel_all_orders()"

# Method 3: Close all positions
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); t.close_all_positions()"
```

#### Circuit Breaker Override (Use with Caution!)

```python
# Only in emergency - normally let circuit breaker protect you
from src.core.risk_manager import RiskManager

risk_mgr = RiskManager()
risk_mgr.metrics.circuit_breaker_triggered = False
risk_mgr.reset_daily_counters()

# Log why you're overriding
print("WARNING: Circuit breaker manually reset")
```

---

## Development Guide

### Project Structure

```
trading/
├── .env.example          # Environment template
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
├── README.md           # This file
│
├── src/
│   ├── core/
│   │   ├── multi_llm_analysis.py    # Multi-LLM analysis engine
│   │   ├── risk_manager.py          # Risk management system
│   │   └── alpaca_trader.py         # Alpaca API interface
│   │
│   └── strategies/
│       ├── core_strategy.py         # Tier 1: Index momentum
│       ├── growth_strategy.py       # Tier 2: Stock picking
│       └── ipo_strategy.py          # Tier 3: IPO analysis
│
├── tests/
│   ├── test_risk_manager.py
│   ├── test_alpaca_trader.py
│   └── test_strategies.py
│
├── logs/                # Log files (auto-created)
├── data/                # Data storage (auto-created)
├── dashboard/           # Streamlit dashboard (WIP)
└── docs/                # Additional documentation
```

### Coding Standards

#### Python Style Guide

Follow PEP 8 with these specifics:

```python
# Imports
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Constants
MAX_POSITION_SIZE = 0.10
DEFAULT_STOP_LOSS = 0.05

# Classes (PascalCase)
class RiskManager:
    """Risk management class with comprehensive docstrings."""

    def __init__(self, max_loss: float = 2.0):
        """Initialize risk manager.

        Args:
            max_loss: Maximum daily loss percentage
        """
        self.max_loss = max_loss
        self.logger = logging.getLogger(__name__)

# Functions (snake_case)
def calculate_position_size(account_value: float, risk_pct: float) -> float:
    """Calculate position size based on account value and risk.

    Args:
        account_value: Total account value in dollars
        risk_pct: Risk percentage per trade

    Returns:
        Position size in dollars

    Example:
        >>> calculate_position_size(10000, 1.0)
        100.0
    """
    return account_value * (risk_pct / 100)

# Type hints everywhere
def get_sentiment(symbol: str, data: Dict[str, any]) -> float:
    """Get sentiment score for symbol."""
    return 0.75
```

#### Documentation Requirements

**Every module** must have:
- Module-level docstring explaining purpose
- Class docstrings with attributes listed
- Function docstrings with Args/Returns/Examples
- Type hints for all parameters and returns

**Example**:
```python
"""
Risk Management Module

This module provides comprehensive risk management for trading operations.
Implements circuit breakers, position sizing, and trade validation.

Author: Trading Team
Date: 2025-10-28
"""

from typing import Dict, Optional

class RiskManager:
    """
    Risk management system for trading operations.

    Attributes:
        max_daily_loss_pct: Maximum daily loss percentage
        max_position_size_pct: Maximum position size percentage
        metrics: Current risk metrics
    """

    def validate_trade(
        self,
        symbol: str,
        amount: float
    ) -> Dict[str, bool]:
        """
        Validate trade against risk parameters.

        Args:
            symbol: Stock ticker symbol
            amount: Trade amount in dollars

        Returns:
            Dictionary with 'valid' boolean and 'reason' string

        Example:
            >>> rm = RiskManager()
            >>> result = rm.validate_trade('AAPL', 1000.0)
            >>> print(result['valid'])
            True
        """
        pass
```

### Adding New Features

#### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

#### 2. Implement Feature

```python
# Example: Adding new strategy
# File: src/strategies/new_strategy.py

"""
New Strategy Module

Description of your strategy.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class NewStrategy:
    """Your strategy class."""

    def __init__(self, allocation: float):
        """Initialize strategy."""
        self.allocation = allocation
        logger.info(f"NewStrategy initialized with ${allocation}")

    def execute(self) -> List[Dict]:
        """Execute strategy logic."""
        logger.info("Executing new strategy")
        # Your implementation
        return []
```

#### 3. Add Tests

```python
# File: tests/test_new_strategy.py

import pytest
from src.strategies.new_strategy import NewStrategy

def test_strategy_initialization():
    """Test strategy initializes correctly."""
    strategy = NewStrategy(allocation=10.0)
    assert strategy.allocation == 10.0

def test_strategy_execution():
    """Test strategy execution."""
    strategy = NewStrategy(allocation=10.0)
    results = strategy.execute()
    assert isinstance(results, list)
```

#### 4. Run Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_new_strategy.py

# Run with coverage
pytest --cov=src tests/
```

#### 5. Update Documentation

- Add feature to README.md
- Update relevant sections
- Add usage examples
- Document configuration options

### Testing Guidelines

#### Unit Tests

Test individual functions and methods:

```python
def test_calculate_momentum():
    """Test momentum calculation."""
    strategy = CoreStrategy()
    momentum = strategy.calculate_momentum('SPY')
    assert 0 <= momentum <= 100
```

#### Integration Tests

Test component interactions:

```python
def test_trade_execution_flow():
    """Test complete trade flow."""
    trader = AlpacaTrader(paper=True)
    risk_mgr = RiskManager()

    # Validate trade
    validation = risk_mgr.validate_trade('SPY', 100.0, 0.5, 10000.0)
    assert validation['valid']

    # Execute trade
    order = trader.execute_order('SPY', 100.0)
    assert order['status'] in ['filled', 'accepted']
```

#### Mock External APIs

```python
from unittest.mock import Mock, patch

def test_llm_analysis():
    """Test LLM analysis with mocked API."""
    with patch('openai.ChatCompletion.create') as mock_create:
        mock_create.return_value = {
            'choices': [{'message': {'content': 'Bullish'}}]
        }

        analyzer = MultiLLMAnalyzer()
        sentiment = analyzer.get_sentiment({}, [])
        assert sentiment > 0
```

---

## Testing

### Test Setup

```bash
# Install test dependencies (included in requirements.txt)
pip install pytest pytest-asyncio pytest-cov

# Set test environment
export PAPER_TRADING=true
export TEST_MODE=true
```

### Running Tests

#### Quick Test (Essential Tests Only)

```bash
# Run fast unit tests
pytest tests/ -v -m "not slow"

# Expected output:
# tests/test_risk_manager.py::test_position_sizing PASSED
# tests/test_alpaca_trader.py::test_account_info PASSED
# ================================ 12 passed in 2.45s ================================
```

#### Full Test Suite

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

#### Test Individual Components

```bash
# Test risk manager
pytest tests/test_risk_manager.py -v

# Test Alpaca trader
pytest tests/test_alpaca_trader.py -v

# Test strategies
pytest tests/test_strategies.py -v

# Test specific function
pytest tests/test_risk_manager.py::test_circuit_breaker -v
```

### Test Examples

#### Test Risk Manager

```python
# tests/test_risk_manager.py

import pytest
from src.core.risk_manager import RiskManager

def test_position_sizing():
    """Test position size calculation."""
    risk_mgr = RiskManager(max_position_size_pct=10.0)

    position_size = risk_mgr.calculate_position_size(
        account_value=10000.0,
        risk_per_trade_pct=1.0,
        price_per_share=100.0
    )

    assert position_size == 1  # 10000 * 1% / 100 = 1 share
    assert position_size * 100 <= 10000 * 0.10  # Within limits

def test_circuit_breaker():
    """Test circuit breaker triggers correctly."""
    risk_mgr = RiskManager(max_daily_loss_pct=2.0)

    # Should allow trading with small loss
    assert risk_mgr.can_trade(10000.0, -100.0) == True

    # Should block trading with large loss
    assert risk_mgr.can_trade(10000.0, -300.0) == False

def test_trade_validation():
    """Test trade validation logic."""
    risk_mgr = RiskManager()

    validation = risk_mgr.validate_trade(
        symbol='AAPL',
        amount=500.0,
        sentiment_score=0.75,
        account_value=10000.0
    )

    assert validation['valid'] == True
    assert 'reason' in validation
```

#### Test Alpaca Trader (Mocked)

```python
# tests/test_alpaca_trader.py

import pytest
from unittest.mock import Mock, patch
from src.core.alpaca_trader import AlpacaTrader

@patch('alpaca_trade_api.REST')
def test_account_info(mock_rest):
    """Test account info retrieval."""
    # Mock Alpaca API response
    mock_account = Mock()
    mock_account.status = 'ACTIVE'
    mock_account.buying_power = '10000.00'
    mock_account.equity = '10000.00'

    mock_rest.return_value.get_account.return_value = mock_account

    # Test trader
    trader = AlpacaTrader(paper=True)
    account = trader.get_account_info()

    assert account['status'] == 'ACTIVE'
    assert account['buying_power'] == 10000.0

@patch('alpaca_trade_api.REST')
def test_order_execution(mock_rest):
    """Test order execution."""
    # Mock order response
    mock_order = Mock()
    mock_order.id = 'order-123'
    mock_order.symbol = 'SPY'
    mock_order.notional = 100.0
    mock_order.status = 'accepted'

    mock_rest.return_value.submit_order.return_value = mock_order
    mock_rest.return_value.get_account.return_value.trading_blocked = False
    mock_rest.return_value.get_account.return_value.buying_power = '10000'

    # Test order
    trader = AlpacaTrader(paper=True)
    order = trader.execute_order('SPY', 100.0)

    assert order['id'] == 'order-123'
    assert order['symbol'] == 'SPY'
```

### Test Coverage Goals

- **Core Modules**: >90% coverage
- **Strategies**: >80% coverage
- **Overall**: >85% coverage

Check coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

---

## Production Deployment

### Pre-Deployment Checklist

#### 1. Security Review

- [ ] All API keys stored securely (not in code)
- [ ] `.env` file in `.gitignore`
- [ ] No secrets in logs
- [ ] HTTPS/TLS for all API calls
- [ ] Rate limiting configured
- [ ] Error messages don't expose sensitive data

#### 2. Configuration Validation

```bash
# Run pre-deployment checks
python scripts/pre_deployment_check.py

# Expected checks:
# ✓ Environment variables configured
# ✓ API connectivity verified
# ✓ Risk limits set appropriately
# ✓ Allocations sum to 100%
# ✓ Log directory writable
# ✓ Data directory writable
```

#### 3. Testing Verification

```bash
# Run full test suite
pytest tests/ -v

# Run integration tests
pytest tests/integration/ -v

# Verify paper trading works
python scripts/test_paper_trading.py
```

#### 4. Monitoring Setup

- [ ] Alerting configured (email/webhook)
- [ ] Logging enabled and tested
- [ ] Dashboard accessible
- [ ] Health check endpoint working
- [ ] Backup strategy in place

### Deployment Options

#### Option 1: VPS Deployment (Recommended)

**Step 1: Provision Server**
```bash
# DigitalOcean, AWS EC2, Linode, etc.
# Recommended specs:
# - 2 GB RAM
# - 1 vCPU
# - 25 GB SSD
# - Ubuntu 22.04 LTS
```

**Step 2: Server Setup**
```bash
# SSH into server
ssh user@your-server-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10
sudo apt install python3.10 python3.10-venv python3-pip -y

# Install Git
sudo apt install git -y

# Clone repository
git clone <your-repo-url> trading
cd trading

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Step 3: Configure Environment**
```bash
# Create .env file
nano .env
# Add your configuration (API keys, etc.)

# Secure .env file
chmod 600 .env

# Test configuration
python -c "from dotenv import load_dotenv; load_dotenv(); print('Config loaded')"
```

**Step 4: Setup Cron Job**
```bash
# Edit crontab
crontab -e

# Add daily execution (9:45 AM ET)
45 9 * * 1-5 cd /home/user/trading && /home/user/trading/venv/bin/python main.py >> logs/cron.log 2>&1

# Add weekly execution for growth strategy (Monday 9:30 AM ET)
30 9 * * 1 cd /home/user/trading && /home/user/trading/venv/bin/python -m src.strategies.growth_strategy >> logs/growth_cron.log 2>&1

# Save and exit
```

**Step 5: Setup systemd Service (Alternative)**
```bash
# Create service file
sudo nano /etc/systemd/system/trading-bot.service

# Add content:
[Unit]
Description=AI Trading Bot
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/trading
Environment="PATH=/home/user/trading/venv/bin"
ExecStart=/home/user/trading/venv/bin/python main.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot
```

---

#### Option 2: Docker Deployment

**Step 1: Create Dockerfile**
```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p logs data

# Run application
CMD ["python", "main.py"]
```

**Step 2: Create docker-compose.yml**
```yaml
version: '3.8'

services:
  trading-bot:
    build: .
    container_name: trading-bot
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - TZ=America/New_York
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Step 3: Deploy**
```bash
# Build image
docker-compose build

# Start container
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

---

#### Option 3: Cloud Function (AWS Lambda)

**Step 1: Create Lambda Handler**
```python
# lambda_handler.py
import os
import logging
from src.strategies.core_strategy import CoreStrategy

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """AWS Lambda handler for trading execution."""
    try:
        # Initialize strategy
        strategy = CoreStrategy(
            daily_allocation=float(os.getenv('DAILY_INVESTMENT', 10.0))
        )

        # Execute daily routine
        order = strategy.execute_daily()

        return {
            'statusCode': 200,
            'body': f'Order executed: {order.symbol if order else "None"}'
        }
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
```

**Step 2: Package for Lambda**
```bash
# Create deployment package
mkdir lambda_package
pip install -r requirements.txt -t lambda_package/
cp -r src lambda_package/
cp lambda_handler.py lambda_package/

# Create zip
cd lambda_package
zip -r ../trading-bot-lambda.zip .
cd ..
```

**Step 3: Deploy to AWS**
```bash
# Using AWS CLI
aws lambda create-function \
  --function-name trading-bot \
  --runtime python3.10 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://trading-bot-lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{ALPACA_API_KEY=$ALPACA_KEY,OPENROUTER_API_KEY=$OPENROUTER_KEY}"

# Create EventBridge rule for daily execution
aws events put-rule \
  --name daily-trading \
  --schedule-expression "cron(45 13 ? * MON-FRI *)" \
  --description "Execute trading bot daily at 9:45 AM ET"

# Add Lambda permission
aws lambda add-permission \
  --function-name trading-bot \
  --statement-id daily-trading \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/daily-trading
```

---

### Post-Deployment

#### Monitoring

```bash
# Check logs
tail -f logs/trading.log

# Monitor system resources
htop  # or top

# Check disk space
df -h

# Monitor network
netstat -tuln
```

#### Backup Strategy

```bash
# Daily backups
# Add to crontab:
0 0 * * * tar -czf /backups/trading-$(date +\%Y\%m\%d).tar.gz /home/user/trading/data /home/user/trading/logs

# Keep last 7 days
0 1 * * * find /backups -name "trading-*.tar.gz" -mtime +7 -delete
```

#### Health Monitoring

```bash
# Create health check script
# scripts/health_check.sh
#!/bin/bash

# Check if process is running
if pgrep -f "python.*trading" > /dev/null; then
    echo "✓ Trading bot is running"
else
    echo "✗ Trading bot is not running"
    # Send alert
    curl -X POST $WEBHOOK_URL -d '{"text":"Trading bot down!"}'
fi

# Check API connectivity
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); t.get_account_info()" && echo "✓ API connected" || echo "✗ API connection failed"

# Check disk space
df -h / | awk 'NR==2 {if ($5+0 > 80) print "✗ Disk space low: " $5; else print "✓ Disk space OK: " $5}'

# Schedule health check (every 15 minutes)
# */15 * * * * /home/user/trading/scripts/health_check.sh >> /home/user/trading/logs/health.log 2>&1
```

---

### Scaling Considerations

As your system grows:

1. **Horizontal Scaling**: Run multiple instances for different strategies
2. **Database**: Add PostgreSQL/MongoDB for better data management
3. **Message Queue**: Use Redis/RabbitMQ for asynchronous processing
4. **Load Balancer**: Distribute API requests across instances
5. **Caching**: Add Redis for LLM response caching

---

## FAQ

### General Questions

**Q: Is this system profitable?**

A: The system is designed to achieve 12-18% annual returns through diversified strategies and risk management. However:
- Past performance doesn't guarantee future results
- Markets are unpredictable
- Always start with paper trading
- Never invest more than you can afford to lose

**Q: How much money do I need to start?**

A: Recommended minimums:
- **Paper Trading** (testing): $0 (use Alpaca paper account)
- **Live Trading**: $500-1000 minimum
  - Allows proper position sizing
  - Can handle multiple positions
  - Provides margin for losses

**Q: How much time does this require?**

A: After initial setup (2-4 hours):
- **Automated**: 5 minutes/day to review logs
- **Manual Components** (IPO, Tier 4): 30-60 minutes/week
- **Monthly Review**: 1-2 hours

**Q: Do I need programming experience?**

A: Basic Python knowledge helps but isn't required:
- **No Experience**: Follow setup guide exactly, use paper trading
- **Basic Python**: Can customize strategies and parameters
- **Advanced**: Can add new strategies and features

---

### Technical Questions

**Q: Which Python version should I use?**

A: Python 3.8 or higher. Tested on:
- ✓ Python 3.8
- ✓ Python 3.9
- ✓ Python 3.10 (recommended)
- ✓ Python 3.11

**Q: Can I run this on Windows?**

A: Yes, but Linux/macOS recommended:
- **Windows**: Works but requires WSL2 for best experience
- **macOS**: Fully supported
- **Linux**: Fully supported (Ubuntu 20.04+ recommended)

**Q: How do I update to the latest version?**

```bash
# Backup your data
cp -r data data.backup
cp -r logs logs.backup

# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Test in paper mode
python -m pytest tests/

# Resume trading
```

**Q: Can I run multiple strategies simultaneously?**

A: Yes, each strategy can run independently:
```bash
# Run all strategies
python main.py --all

# Run specific strategy
python main.py --strategy core
python main.py --strategy growth
```

---

### Trading Questions

**Q: When does the bot execute trades?**

A: Default schedule:
- **Core Strategy** (Tier 1): Daily at 9:45 AM ET
- **Growth Strategy** (Tier 2): Monday at 9:30 AM ET
- **IPO Analysis** (Tier 3): Manual based on opportunities
- **Swing Trading** (Tier 4): Manual with AI support

**Q: What happens if I miss a trading day?**

A: The system automatically skips:
- Holidays (market closed)
- Weekends
- When circuit breaker is active

To manually execute missed day:
```bash
python main.py --force-execute
```

**Q: Can I trade outside market hours?**

A: No, the system only trades during:
- **Regular Hours**: 9:30 AM - 4:00 PM ET
- **Pre-Market**: Not supported (can be added)
- **After-Hours**: Not supported (can be added)

**Q: How do I paper trade before going live?**

```bash
# 1. Set paper trading in .env
PAPER_TRADING=true

# 2. Use Alpaca paper account credentials
ALPACA_API_KEY=<paper-trading-key>
ALPACA_SECRET_KEY=<paper-trading-secret>

# 3. Run for at least 30 days
# 4. Review performance metrics
# 5. Only then consider live trading
```

---

### Risk & Safety Questions

**Q: What's the maximum I can lose in a day?**

A: The system has multiple protections:
- **Circuit Breaker**: Stops at 2% daily loss (configurable)
- **Position Limit**: Max 10% per position (configurable)
- **Stop-Loss**: Default 5% per position
- **Max Drawdown**: Stops at 10% total drawdown

Example with $10,000 account:
- Daily loss limit: $200 (2%)
- Single position max: $1,000 (10%)
- Total drawdown limit: $1,000 (10% from peak)

**Q: Can the bot lose all my money?**

A: Extremely unlikely due to risk controls, but:
- **Circuit breakers** stop large losses
- **Position sizing** limits exposure
- **Stop-losses** on every position
- **Diversification** across tiers

However, in extreme events (market crash, flash crash):
- Stop-losses may not execute at desired price
- Circuit breakers may not prevent all losses
- Always use paper trading first!

**Q: How do I stop the bot immediately?**

```bash
# Method 1: Kill process
pkill -f "python.*trading"

# Method 2: Cancel all orders
python scripts/emergency_stop.py

# Method 3: Close all positions
python scripts/close_all_positions.py
```

**Q: What happens if the bot crashes mid-trade?**

A: The system is designed to be resilient:
1. Orders already submitted will complete on Alpaca
2. Stop-losses remain active (set on Alpaca side)
3. Restart the bot to resume monitoring
4. Review logs to understand what happened

```bash
# Check recent activity
tail -100 logs/trading.log

# Verify positions
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); print(t.get_positions())"
```

---

### Performance Questions

**Q: How can I track performance?**

```bash
# View performance metrics
python scripts/show_performance.py

# Check specific strategy
python -c "from src.strategies.core_strategy import CoreStrategy; s = CoreStrategy(); print(s.get_performance_metrics())"

# Export to CSV
python scripts/export_trades.py --output trades.csv
```

**Q: What's a good win rate?**

- **Overall**: 50-60% win rate is good
- **Tier 1 (Core)**: 60-70% (low volatility)
- **Tier 2 (Growth)**: 45-55% (higher risk/reward)
- **Tier 3 (IPO)**: 40-50% (high risk/reward)

Remember: Win rate alone doesn't matter. A strategy can be profitable with 40% win rate if wins are larger than losses.

**Q: How do I know if the bot is working correctly?**

Check these indicators daily:
```bash
# 1. Logs show recent activity
tail -20 logs/trading.log

# 2. No error messages
grep ERROR logs/trading.log | tail -10

# 3. Trades being executed
grep "Order submitted" logs/trading.log | tail -5

# 4. Risk metrics healthy
python scripts/check_risk_status.py
```

---

### Customization Questions

**Q: Can I change the daily investment amount?**

Yes, edit `.env`:
```env
# Change from $10 to your desired amount
DAILY_INVESTMENT=25.0

# Tier allocations stay the same (60/20/10/10)
# So with $25: Tier 1 gets $15, Tier 2 gets $5, etc.
```

**Q: Can I add my own strategy?**

Yes! See [Development Guide](#development-guide):

```python
# Create: src/strategies/my_strategy.py
class MyStrategy:
    def __init__(self, allocation: float):
        self.allocation = allocation

    def execute(self):
        # Your strategy logic
        pass

# Add to main.py
from src.strategies.my_strategy import MyStrategy
strategy = MyStrategy(allocation=5.0)
```

**Q: Can I use different LLM models?**

Yes, edit `src/core/multi_llm_analysis.py`:

```python
# Change model selection
models = [
    LLMModel.CLAUDE_35_SONNET,  # Keep this
    LLMModel.GPT4O,              # Keep this
    # LLMModel.GEMINI_2_FLASH    # Remove or add others
]
```

**Q: Can I trade other assets (crypto, forex)?**

Currently supports stocks and ETFs only. To add crypto:
1. Need exchange API (Coinbase, Binance)
2. Modify `alpaca_trader.py` for crypto exchange
3. Adjust strategies for 24/7 trading
4. Update risk management for higher volatility

---

### Troubleshooting FAQ

**Q: Why am I getting "Insufficient buying power"?**

Common causes:
1. **Unsettled funds**: Wait T+2 settlement
2. **Too high daily allocation**: Reduce in `.env`
3. **Pattern Day Trader** restriction: Need $25k for unlimited trades
4. **Orders pending**: Check `trader.get_all_orders()`

Solution:
```bash
# Check account status
python -c "from src.core.alpaca_trader import AlpacaTrader; t = AlpacaTrader(); print(t.get_account_info())"

# Reduce daily investment
# Edit .env: DAILY_INVESTMENT=5.0
```

**Q: Bot isn't making any trades - why?**

Check these issues:
1. **Circuit breaker active**: Check logs for "circuit breaker"
2. **Outside market hours**: Trades only 9:30-4PM ET
3. **Sentiment too bearish**: Very negative sentiment pauses trading
4. **No valid candidates**: All stocks filtered out

Debug:
```bash
# Check circuit breaker status
python scripts/check_risk_status.py

# Run in verbose mode
python main.py --verbose

# Test individual components
python -m src.strategies.core_strategy
```

**Q: LLM calls are too expensive - how to reduce costs?**

Options:
1. **Use fewer models**: Only Claude or only GPT-4
2. **Reduce analysis frequency**: Weekly instead of daily
3. **Use cheaper models**: Gemini 2.0 Flash is free tier
4. **Cache results**: Add caching for repeated analysis

```python
# In multi_llm_analysis.py
# Use only one model
models = [LLMModel.GEMINI_2_FLASH]  # Free tier
```

---

### Support & Resources

**Q: Where can I get help?**

1. **Documentation**: This README (you're reading it!)
2. **Logs**: Always check `logs/trading.log` first
3. **Issues**: [GitHub Issues](your-repo/issues)
4. **Community**: [Discord/Slack channel]

**Q: How do I report a bug?**

```bash
# 1. Gather information
python scripts/generate_bug_report.py

# 2. Create GitHub issue with:
- Bug report output
- Relevant log excerpts
- Steps to reproduce
- Expected vs actual behavior
```

**Q: Can I contribute to the project?**

Yes! Contributions welcome:
1. Fork the repository
2. Create feature branch
3. Make your changes
4. Add tests
5. Submit pull request

See [Development Guide](#development-guide) for details.

---

## License

[Add your license information here]

## Disclaimer

This software is for educational purposes only. Trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this system. Always:

- Start with paper trading
- Never invest more than you can afford to lose
- Conduct your own research and due diligence
- Consider consulting a financial advisor
- Understand that past performance doesn't guarantee future results

**Use at your own risk.**

---

## Acknowledgments

- **Alpaca Markets**: Trading API and infrastructure
- **OpenRouter**: Multi-LLM access and routing
- **Anthropic**: Claude AI models
- **OpenAI**: GPT models
- **Google**: Gemini models
- **yfinance**: Market data library

---

**Last Updated**: 2025-10-28
**Version**: 1.0.0
**Maintainer**: [Your Name/Team]
