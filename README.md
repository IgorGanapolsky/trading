# 🤖 AI Options Trading Bot

[![Options Win Rate](https://img.shields.io/badge/options_win_rate-75%25-success.svg)](docs/options-profit-roadmap.md)
[![Total Profit](https://img.shields.io/badge/profit-%2B%24327-success.svg)](dashboard.md)
[![Status](https://img.shields.io/badge/status-paper_trading-yellow.svg)](docs/r-and-d-phase.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Open-source AI-powered trading system** that uses multi-agent LLM consensus and options premium selling to generate consistent profits. Built with Python, Alpaca API, and modern ML techniques.

> 📈 **Live Results**: 75% win rate on options, +$327 profit in 9 days of paper trading

---

## 🏆 Why This Project?

Most trading bots fail because they:
- ❌ Chase complex strategies that don't work
- ❌ Ignore risk management
- ❌ Don't learn from mistakes

**This system is different:**
- ✅ **Data-driven strategy selection** - We tried 8 strategies, kept what works (options: 75% win rate)
- ✅ **Removed what doesn't work** - Crypto had 0% win rate, so we removed it
- ✅ **RAG-powered learning** - 50+ lessons learned indexed and queried before every decision
- ✅ **Multi-agent verification** - No single point of failure

---

## 📊 Live Performance (Day 9/90)

| Strategy | P/L | Win Rate | Status |
|----------|-----|----------|--------|
| **🏆 Options (Cash-Secured Puts)** | **+$327.82** | **75%** | ✅ PRIMARY |
| ~~Crypto~~ | -$0.43 | 0% | ❌ Removed |
| Bonds | $0.00 | 100% | ✅ Hedge |
| Core ETFs | -$4.15 | N/A | ✅ Active |

**Key Insight**: Options generate 100% of profits. Focus on what works.

---

## 🎯 Options Strategy (The Winner)

Our primary strategy is **cash-secured put selling** on quality stocks:

```
Strategy: Sell 15-20 delta puts, 30-45 DTE
Target:   2% monthly premium (24% annual)
Stocks:   SPY, QQQ, AMD, NVDA
Risk:     Willing to own shares if assigned
```

### Why It Works

1. **Time decay (theta)** works in your favor every day
2. **High probability** - 80%+ of options expire worthless
3. **Defined risk** - You know max loss upfront
4. **Works in sideways markets** - Don't need stocks to go up

### Recent Trades

| Symbol | Entry | Exit | P/L | Result |
|--------|-------|------|-----|--------|
| SPY $660 Put | $638 | $441 | **+$197** | ✅ WIN |
| AMD $200 Put | $590 | $460 | **+$130** | ✅ WIN |
| SPY $660 Put | $6.38 | $5.56 | **+$0.82** | ✅ WIN |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/IgorGanapolsky/trading.git
cd trading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Alpaca API keys
```

### 3. Run

```bash
# Paper trading (safe)
PYTHONPATH=src python3 scripts/autonomous_trader.py

# Check positions
python3 scripts/check_positions.py
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Trading Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│  Gate 1: Momentum Filter (MACD, RSI, Volume)                │
│  Gate 2: RL Agent (Transformer + Heuristics)                │
│  Gate 3: LLM Sentiment (Claude/GPT consensus)               │
│  Gate 4: Risk Manager (Position sizing, stops)              │
│  Gate 5: Options Strategy (Cash-secured puts)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │   Alpaca API (Execution)  │
              └───────────────────────────┘
```

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Orchestrator** | Main trading logic | `src/orchestrator/main.py` |
| **Options Strategy** | Put selling logic | `src/strategies/options_strategy.py` |
| **Risk Manager** | Position sizing | `src/safety/risk_manager.py` |
| **RAG System** | Lessons learned | `rag_knowledge/lessons_learned/` |
| **ML Pipeline** | Predictions | `src/ml/` |

---

## 📚 Documentation

### Getting Started
- **[Quick Start Guide](docs/START_HERE.md)** - Full setup instructions
- **[Cloud Deployment](docs/CLOUD_DEPLOYMENT.md)** - GitHub Actions automation
- **[Options Roadmap](docs/options-profit-roadmap.md)** - Options strategy details

### Architecture
- **[RAG/ML Architecture](docs/RAG_ML_ARCHITECTURE.md)** - How the AI learns
- **[Verification System](docs/VERIFICATION_SYSTEM.md)** - Safety mechanisms
- **[Multi-Agent Design](docs/MULTI_AGENT_ARCHITECTURE.md)** - Agent coordination

### Operations
- **[Dashboard](dashboard.md)** - Live performance metrics
- **[Lessons Learned](rag_knowledge/lessons_learned/)** - 50+ documented learnings
- **[R&D Phase](docs/r-and-d-phase.md)** - Current 90-day plan

---

## 🛡️ Risk Management

**This is NOT financial advice. Paper trade first!**

### Built-in Safeguards

| Safeguard | Description |
|-----------|-------------|
| **Position Limits** | Max 5% per position |
| **Daily Loss Limit** | 2% max daily loss |
| **Circuit Breakers** | Auto-halt on 3 consecutive losses |
| **Paper Mode** | 90-day validation before live |

### The Rules

1. ✅ Always paper trade first (90 days)
2. ✅ Never risk more than you can lose
3. ✅ Understand every trade before placing
4. ❌ No margin trading initially
5. ❌ No emotional revenge trading

---

## 🧠 AI/ML Features

### RAG (Retrieval Augmented Generation)
- 50+ lessons learned indexed
- Queried before every strategic decision
- Prevents repeated mistakes

### Multi-Agent Consensus
- Multiple LLMs vote on trades
- No single model failure
- Configurable confidence thresholds

### Reinforcement Learning
- Transformer-based predictions
- Online learning from outcomes
- Adaptive strategy weights

---

## 📈 Portfolio Allocation

```
Options Premium:     37%  ████████████████████░░░░░░░░  PRIMARY
Core ETFs (SPY):     25%  ██████████████░░░░░░░░░░░░░░
Treasuries:          15%  ████████░░░░░░░░░░░░░░░░░░░░  Hedge
Growth Stocks:       10%  █████░░░░░░░░░░░░░░░░░░░░░░░
REITs:                5%  ██░░░░░░░░░░░░░░░░░░░░░░░░░░  Testing
Precious Metals:      3%  █░░░░░░░░░░░░░░░░░░░░░░░░░░░  Testing
Cash Reserve:         5%  ██░░░░░░░░░░░░░░░░░░░░░░░░░░
```

---

## 🤝 Contributing

This is an active project! Contributions welcome:

1. **Report bugs** - Open an issue
2. **Suggest features** - Open a discussion
3. **Submit PRs** - Fork and contribute

### Development

```bash
# Run tests
pytest tests/ -v

# Type checking
mypy src/ --ignore-missing-imports

# Lint
ruff check src/
```

---

## 📊 Comparison to Other Bots

| Feature | This Project | Most Bots |
|---------|--------------|-----------|
| **Strategy** | Options (proven) | Complex strategies |
| **Win Rate** | 75% | Unknown |
| **Open Source** | ✅ Yes | Often closed |
| **Learning System** | RAG + ML | None |
| **Risk Management** | Multi-layer | Basic |
| **Documentation** | Extensive | Minimal |

---

## ⭐ Star History

If this project helps you, please star it! ⭐

---

## 📝 License

MIT License - See [LICENSE](LICENSE)

---

## ⚠️ Disclaimer

**This software is for educational purposes only.**

- Trading involves significant risk of loss
- Past performance does not guarantee future results
- Always paper trade before using real money
- This is NOT financial advice

---

## 🔗 Links

- **[Dashboard](dashboard.md)** - Live performance
- **[Lessons Learned](rag_knowledge/lessons_learned/)** - What we've learned
- **[GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)** - Automation

---

**Built with** ❤️ **using Python, Alpaca, Claude, and coffee**

**Maintained by** [Igor Ganapolsky](https://github.com/IgorGanapolsky)
