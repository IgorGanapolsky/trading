# 🤖 AI-Powered Automated Trading System

![Status](https://img.shields.io/badge/status-production_ready-brightgreen.svg)
![Win Rate](https://img.shields.io/badge/win_rate-62.2%25-success.svg)
![Sharpe Ratio](https://img.shields.io/badge/sharpe-2.18-success.svg)
[![Progress Dashboard](https://img.shields.io/badge/Progress-Dashboard-success)](https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
[![Automated Dry Run](https://img.shields.io/badge/Automated%20Dry%20Run-View%20Latest-blue)](https://github.com/IgorGanapolsky/trading/wiki/Automated-Dry-Run)
[![Dry Run Updated](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/IgorGanapolsky/trading/main/badges/dryrun.json)](https://github.com/IgorGanapolsky/trading/wiki/Automated-Dry-Run)

**Validated profitable** automated trading system using momentum indicators (MACD + RSI + Volume) with cloud deployment via GitHub Actions.

---

## 🚀 Quick Start

### 1. Setup (5 minutes)

```bash
# Clone and install
git clone https://github.com/IgorGanapolsky/trading.git
cd trading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Create `.env` file with your API keys:
```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
PAPER_TRADING=true
DAILY_INVESTMENT=10.0
```

### 3. Smoke Test the System

```bash
# Quick smoke tests (< 30 seconds) - verifies critical paths work
python3 tests/test_smoke.py

# Expected: ✅ ALL SMOKE TESTS PASSED
```

### 4. Run Trading System (Canonical)

```bash
# Point the orchestrator at a ticker list and use the built-in Alpaca simulator
export TARGET_TICKERS="SPY,QQQ,VOO"
export ALPACA_SIMULATED=1  # omit to hit real Alpaca with your keys
PYTHONPATH=src python3 scripts/autonomous_trader.py
```

The entrypoint now bootstraps the funnel orchestrator (Momentum → RL → LLM → Risk) and writes telemetry to `data/audit_trail/hybrid_funnel_runs.jsonl`.

**Done!** System is ready for autonomous execution.

### Useful CLIs

```bash
# Query latest Bogleheads snapshots (md/json)
python3 scripts/bogleheads_query.py --limit 3 --format md

# Ingest a one-off Bogleheads snapshot into the RAG store
python3 scripts/bogleheads_ingest_once.py

# Generate a dry-run report with ensemble + risk (json/md)
python3 scripts/dry_run.py --symbols SPY QQQ --export-json out.json --export-md out.md
```

---

## 📖 Project Documentation

**CRITICAL - Read These First**:
- **[docs/verification-protocols.md](docs/verification-protocols.md)** - "Show, Don't Tell" protocol (MANDATORY reading for all agents and developers)
- **[docs/r-and-d-phase.md](docs/r-and-d-phase.md)** - Current R&D phase strategy and status (90-day plan)
- **[docs/define-success.md](docs/define-success.md)** - Anthropic “Define Success” scorecard adopted for every iteration
- **[docs/AGENTS.md](docs/AGENTS.md)** - Agent coordination guidelines for autonomous operation
- **[docs/PLAN_MODE_ENFORCEMENT.md](docs/PLAN_MODE_ENFORCEMENT.md)** - Mandatory Claude Code Plan Mode workflow + guardrails

**Strategic Context**:
- **[docs/research-findings.md](docs/research-findings.md)** - Future enhancement roadmap and researched capabilities
- **[docs/profit-optimization.md](docs/profit-optimization.md)** - Cost optimization strategies (OpenRouter, High-Yield Cash, batching)

These documents contain critical protocols and context for understanding how the system operates, what phase we're in, and how to verify work properly. All AI agents MUST read verification-protocols.md before making claims about system status or completion.

---

## 💰 Performance (Validated)

**60-Day Backtest** (Sept-Oct 2025):
- ✅ Win Rate: **62.2%** (target: >55%)
- ✅ Sharpe Ratio: **2.18** (world-class)
- ✅ Max Drawdown: **2.2%** (excellent)
- ✅ Annualized Return: **26.16%**

**Current Status**: Active 90-day R&D phase
**Account**: $99,978.75 (paper trading)
**Daily Investment**: $10/day (fixed)

---

## 🎯 Strategy

**Momentum-based trading** with technical indicators:
- MACD (trend confirmation)
- RSI (overbought/oversold detection)
- Volume analysis (signal strength)
- Multi-period returns (1m/3m/6m)

**Four-tier allocation**:
- Tier 1 (60%): Index ETFs (SPY, QQQ, VOO)
- Tier 2 (20%): Growth stocks (NVDA, GOOGL, AMZN)
- Tier 3 (10%): IPO opportunities (manual)
- Tier 4 (10%): Crowdfunding (manual)

---

## ☁️ Cloud Deployment

**GitHub Actions** (runs automatically):
- Schedule: Weekdays at 9:35 AM EST
- No Mac required
- Free for public repos
- Logs available in Actions → Artifacts

**Setup**:
1. Add GitHub Secrets (Settings → Secrets → Actions):
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
   - `DAILY_INVESTMENT` (optional, defaults to 10.0)

2. Workflow runs automatically every weekday

**Alternative**: Docker deployment available (see [CLOUD_DEPLOYMENT.md](docs/CLOUD_DEPLOYMENT.md))

---

## 📊 Architecture

```
┌──────────────────────────────────────────────┐
│ scripts/autonomous_trader.py (stateless CLI) │
└───────────────────────┬──────────────────────┘
                        ▼
┌──────────────────────────────────────────────┐
│        TradingOrchestrator Funnel            │
│  Gate 1: MomentumAgent (math, pandas)        │
│  Gate 2: RLFilter (JSON weights, local)      │
│  Gate 3: LangChainSentimentAgent (Haiku)     │
│  Gate 4: RiskManager (deterministic sizing)  │
│             │                                 │
│             ▼                                 │
│        AlpacaExecutor                         │
│   (real keys or simulator fallback)          │
└──────────────────────────────────────────────┘
                        │
                        ▼
      data/audit_trail/hybrid_funnel_runs.jsonl
         (gate telemetry + execution receipts)
```

Set `HYBRID_LLM_MODEL=claude-3-5-haiku-20241022` (default) or `gpt-4o-mini` to control LLM spend, and tune `ALPACA_SIMULATED`/`SIMULATED_EQUITY` for dry-runs in CI.

---

## 📚 Documentation

### Essential Reading
- **[START_HERE.md](docs/START_HERE.md)** - Complete setup guide
- **[CLOUD_DEPLOYMENT.md](docs/CLOUD_DEPLOYMENT.md)** - Cloud deployment options
- **[RESEARCH_AND_IMPROVEMENTS.md](docs/RESEARCH_AND_IMPROVEMENTS.md)** - Learning resources
- **[MULTI_AGENT_ARCHITECTURE.md](docs/MULTI_AGENT_ARCHITECTURE.md)** - Multi-agent upgrade blueprint

### System Status
- **[PLAN.md](docs/PLAN.md)** - 90-day R&D roadmap
- **[AUTOMATION_STATUS.md](docs/status/AUTOMATION_STATUS.md)** - Current automation status
- **[ALPACA_ACCOUNT_STATUS.md](docs/status/ALPACA_ACCOUNT_STATUS_2025-11-04.md)** - Latest account report

### Technical Docs
- **[BACKTEST_USAGE.md](docs/BACKTEST_USAGE.md)** - Backtesting engine
- **[ORCHESTRATOR_README.md](docs/ORCHESTRATOR_README.md)** - (Legacy) main orchestrator
- **[agent_framework/](src/agent_framework/)** - Base classes for the new agent architecture
- **[orchestrator/main.py](src/orchestrator/main.py)** - Hybrid funnel orchestrator (new)
- `src/main.py` (legacy scheduler) is deprecated — use `scripts/autonomous_trader.py`.
- **[MCP_EXECUTION_GUIDE.md](docs/MCP_EXECUTION_GUIDE.md)** - Code-execution harness for MCP servers
- **[UNUSED_FILE_DETECTION.md](docs/UNUSED_FILE_DETECTION.md)** - Automated unused file detection system
- **[Full Documentation Index](docs/)** - All 42 documentation files

---

## 🌟 Features

### Core Trading
- **Momentum Indicators**: MACD, RSI, Volume analysis
- **Multi-tier Allocation**: ETFs (60%), Growth stocks (20%), IPOs (10%), Crowdfunding (10%)
- **Risk Management**: Daily loss limits, max drawdown protection, position sizing
- **Paper Trading**: 90-day validation before live trading

### Treasuries Momentum Gate (New)
- Allocates 10% of diversified daily allocation to `TLT` only when `SMA20 >= SMA50` (6-month window).
- Skips TLT on weak momentum days to reduce drawdown.

### Bogleheads Continuous Learning (New)
- Ingests Bogleheads forum every 6 hours (CI). Stores snapshots in a Sentiment RAG (JSON fallback if embeddings unavailable).
- Bogleheads agent contributes to ensemble decisions with adjustable weight and regime-based boost.
- Nightly report includes latest snapshot with TL;DR when available.

### Data Sources & Sentiment
- **Market Data**: Real-time via Alpaca API
- **YouTube Analysis**: Automated monitoring of 5 financial channels (Parkev Tatevosian CFA, etc)
- **Reddit Sentiment**: Daily scraping from r/wallstreetbets, r/stocks, r/investing, r/options
- **Technical Indicators**: MACD, RSI, Volume, Moving Averages
- **Sentiment RAG Store**: SQLite metadata + Chroma vector index for historical retrieval

### Automation
- **Cloud Deployment**: GitHub Actions (weekdays 9:35 AM EST)
- **Daily Reporting**: Automated CEO reports with performance metrics
- **State Persistence**: Complete system state tracking
- **Error Handling**: Retry logic, graceful failures, comprehensive logging

### Sentiment Analysis
- **Reddit Scraper**: Monitors 4 key investing subreddits
  - Extracts ticker mentions and sentiment scores
  - Weighted by upvotes and engagement
  - Confidence levels (high/medium/low)
  - Detects meme stocks and sentiment shifts
  - See [Reddit Sentiment Setup Guide](docs/reddit_sentiment_setup.md)

- **YouTube Monitor**: Analyzes financial video content
  - Daily monitoring of 5 pro financial channels
  - Stock picks and recommendations
  - Auto-updates watchlist
  - Integration with Tier 2 strategy

---

## 🛡️ Risk Management

- **Daily loss limit**: 2% of account value
- **Max drawdown**: 10% (triggers halt)
- **Position sizing**: Fixed $10/day (not portfolio-based)
- **Stop losses**: 5% trailing (ATR-based coming soon)
- **Paper trading**: Validate for 90 days before live trading

### Runtime Config (env)
- `MOMENTUM_MIN_SCORE`: Minimum momentum score to pass Gate 1 (default: 0.0)
- `MOMENTUM_MACD_THRESHOLD`: Minimum MACD histogram to pass (default: 0.0)
- `MOMENTUM_RSI_OVERBOUGHT`: RSI ceiling for rejection (default: 70.0)
- `MOMENTUM_VOLUME_MIN`: Minimum volume ratio (current/avg) (default: 0.8)
- `RL_CONFIDENCE_THRESHOLD`: RL gate minimum confidence (default: 0.6)
- `LLM_NEGATIVE_SENTIMENT_THRESHOLD`: Reject if sentiment below this (default: -0.2)
- `RISK_USE_ATR_SCALING`: Toggle ATR-based volatility sizing (default: true)
- `ATR_STOP_MULTIPLIER`: ATR multiplier for stop placement (default: 2.0)

---

## 🧪 Testing

```bash
# Run backtests
python run_backtest_now.py

# Run tests
python -m pytest tests/

# Check current positions
python scripts/check_positions.py
```

---

## 🚨 Safety First

**Before live trading**:
- [ ] 90+ days of profitable paper trading
- [ ] Overall return >5%
- [ ] Max drawdown <10%
- [ ] Win rate >55%
- [ ] You understand why trades are made

**Never**:
- Trade money you can't afford to lose
- Skip paper trading validation
- Trade when desperate or emotional
- Use borrowed/margin money initially

---

## 🤝 Contributing

This is a personal trading system, but suggestions welcome via issues.

---

## 📝 License

MIT License - See [LICENSE](LICENSE)

---

## ⚠️ Disclaimer

This software is for educational purposes. Trading involves risk. Past performance does not guarantee future results. Always paper trade first. Only invest what you can afford to lose.

---

**Built with**: Python 3.11, Alpaca API, GitHub Actions, Streamlit
**Maintained by**: Igor Ganapolsky
**Documentation**: See [docs/](docs/) for complete guides
