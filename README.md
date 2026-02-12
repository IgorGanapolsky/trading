# 🤖 Ralph Mode - AI Trading System

[![CI](https://github.com/IgorGanapolsky/trading/actions/workflows/ci.yml/badge.svg)](https://github.com/IgorGanapolsky/trading/actions/workflows/ci.yml)
[![Ralph Loop](https://github.com/IgorGanapolsky/trading/actions/workflows/ralph-loop-ai.yml/badge.svg)](https://github.com/IgorGanapolsky/trading/actions/workflows/ralph-loop-ai.yml)
[![Self-Healing Monitor](https://github.com/IgorGanapolsky/trading/actions/workflows/self-healing-monitor.yml/badge.svg)](https://github.com/IgorGanapolsky/trading/actions/workflows/self-healing-monitor.yml)
[![Lessons](https://img.shields.io/badge/lessons_learned-growing-blue.svg)](https://igorganapolsky.github.io/trading/lessons/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dev.to](https://img.shields.io/badge/blog-dev.to-black.svg)](https://dev.to/igorganapolsky)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://igorganapolsky.github.io/trading/)

**Autonomous AI trading system** with scheduled self-healing ("Ralph Loop") workflows, continuous learning, and a defined-risk SPY options strategy.

> **🎯 North Star**: $6,000/month after-tax by Nov 14, 2029  
> **📊 Current status**: [System State JSON](https://github.com/IgorGanapolsky/trading/blob/main/data/system_state.json) | [Progress Dashboard](https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard) | [GitHub Pages](https://igorganapolsky.github.io/trading/) | [RAG Query](https://igorganapolsky.github.io/trading/rag-query/)  
> **🔄 Ralph Loop**: scheduled around the clock; only runs fixes when unhealthy (cost-controlled)

## ✨ What Makes This Special

- **🔄 Self-Healing CI** - Scheduled workflows detect issues, auto-fix what they can, and keep CI green
- **🤖 AI-Powered Fixes** - Uses Claude API in Ralph Loop to propose and apply fixes when needed
- **📚 Lessons Learned (growing)** - Failures and fixes are documented for continuous learning
- **📝 Auto-Published Blog** - Discoveries automatically posted to Dev.to and GitHub Pages
- **🎯 SPY Options Strategy** - Defined-risk options trading focused on SPY during paper validation

---

## Why This Project?

Most trading bots fail because they:

- Chase complex strategies that don't work
- Ignore risk management
- Don't learn from mistakes

**This system is different:**

- **Radically simplified** - Deleted 90% of bloat, kept what works
- **Thompson Sampling** - Mathematically optimal strategy selection (~80 lines)
- **SQLite trade memory** - Query past trades before new ones (~150 lines)
- **Daily verification** - Honest reporting of actual results

---

## Current Performance

Performance metrics change frequently and are auto-synced.

- Source of truth: [data/system_state.json](https://github.com/IgorGanapolsky/trading/blob/main/data/system_state.json)
- Human-readable dashboard: [Progress Dashboard](https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard)
- Public site: [GitHub Pages](https://igorganapolsky.github.io/trading/)
- Query lessons: [RAG Query UI](https://igorganapolsky.github.io/trading/rag-query/)

---

## Strategy: SPY Iron Condors (Defined Risk)

```
Strategy: SPY iron condors (defined risk), 30-45 DTE, ~$5-wide spreads
Focus:    Paper validation first; risk management is non-negotiable
Source:   See CLAUDE.md for the canonical rules and guardrails
```

### Why It Works

1. **Time decay (theta)** works in your favor every day
2. **High probability** - 80%+ of options expire worthless
3. **Defined risk** - You know max loss upfront
4. **Works in sideways markets** - Don't need stocks to go up

---

## Quick Start

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
# Paper trading
python3 scripts/autonomous_trader.py

# Sync latest broker state into data/system_state.json (requires Alpaca keys)
python3 scripts/sync_alpaca_state.py

# Daily verification
python3 scripts/daily_verification.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Trading Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│  1. Thompson Sampler - Select best strategy                 │
│  2. Trade Memory - Query similar past trades                │
│  3. Risk Manager - Position sizing, stops                   │
│  4. Options Strategy - Defined-risk spreads                 │
│  5. Daily Verification - Honest reporting                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │   Alpaca API (Execution)  │
              └───────────────────────────┘
```

### Key Components

| Component              | Purpose            | Location                           |
| ---------------------- | ------------------ | ---------------------------------- |
| **Orchestrator**       | Main trading logic | `src/orchestrator/main.py`         |
| **Thompson Sampler**   | Strategy selection | `src/ml/trade_confidence.py`       |
| **Trade Memory**       | SQLite journal     | `src/learning/trade_memory.py`     |
| **Risk Manager**       | Position sizing    | `src/risk/`                        |
| **Daily Verification** | Honest reporting   | `scripts/daily_verification.py`    |

---

## Learning System

### Thompson Sampling (replaces complex RL)

- Beta distribution for each strategy
- Sample to select best strategy
- Update based on win/loss outcomes
- Proven optimal for <100 decisions

### Trade Memory (complements RAG)

- SQLite database of past trades
- Query BEFORE each new trade
- Pattern recognition: "This setup has 30% win rate - AVOID"
- Simple but effective

---

## Risk Management

**This is NOT financial advice. Paper trade first!**

| Safeguard            | Description                       |
| -------------------- | --------------------------------- |
| **Position Limits**  | Max 5% per position               |
| **Daily Loss Limit** | 2% max daily loss                 |
| **Circuit Breakers** | Auto-halt on 3 consecutive losses |
| **Paper Mode**       | 90-day validation before live     |

---

## Follow Our Journey

| Platform              | Link                                                                          | Description                            |
| --------------------- | ----------------------------------------------------------------------------- | -------------------------------------- |
| **GitHub Pages Blog** | [igorganapolsky.github.io/trading](https://igorganapolsky.github.io/trading/) | Daily trading reports, lessons learned |
| **Dev.to**            | [@igorganapolsky](https://dev.to/igorganapolsky)                              | AI trading insights, tutorials         |
| **Daily Reports**     | [/reports/](https://igorganapolsky.github.io/trading/reports/)                | Transparent P/L tracking               |
| **Lessons Learned**   | [/lessons/](https://igorganapolsky.github.io/trading/lessons/)                | Continuously growing lessons           |

---

## For AI Agents & LLMs

This repo is optimized for AI agent collaboration:

- Quick context: `.claude/CLAUDE.md`
- Rules: `.claude/rules/MANDATORY_RULES.md`
- RAG knowledge base: `rag_knowledge/`

---

## Documentation

- **[Lessons Learned](docs/lessons.md)** - Trading lessons from RAG
- **[Reports](docs/reports.md)** - Performance reports

---

## Development

```bash
# Run tests
pytest tests/ -v

# Type checking
mypy src/ --ignore-missing-imports

# Lint
ruff check src/
```

---

## Disclaimer

**This software is for educational purposes only.**

- Trading involves significant risk of loss
- Past performance does not guarantee future results
- Always paper trade before using real money
- This is NOT financial advice

---

**Built with Python, Alpaca, and radical simplicity**

**Maintained by** [Igor Ganapolsky](https://github.com/IgorGanapolsky)
