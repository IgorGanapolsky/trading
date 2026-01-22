# 🤖 Ralph Mode - AI Trading System

[![Tests](https://img.shields.io/badge/tests-875_passing-brightgreen.svg)](#)
[![Lessons](https://img.shields.io/badge/lessons_learned-122+-blue.svg)](#)
[![Self-Healing](https://img.shields.io/badge/CI-self--healing-purple.svg)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dev.to](https://img.shields.io/badge/blog-dev.to-black.svg)](https://dev.to/igorganapolsky)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub_Pages-blue.svg)](https://igorganapolsky.github.io/trading/)

**Fully autonomous AI trading system** using the [Ralph Wiggum iterative coding technique](https://github.com/Th0rgal/opencode-ralph-wiggum). Features **self-healing CI**, **automated bug fixes**, and **iron condor options strategy** on SPY.

> **🎯 North Star**: $100/day after tax | **📊 Current**: $5,066 paper account | **🔄 Ralph Mode**: Active 24/7

## ✨ What Makes This Special

- **🔄 Self-Healing CI** - Ralph Mode runs 24/7, automatically finding and fixing bugs
- **🤖 AI-Powered Fixes** - Uses Claude API to analyze failures and generate fixes
- **📚 122+ Lessons Learned** - Every failure documented for continuous learning
- **📝 Auto-Published Blog** - Discoveries automatically posted to Dev.to and GitHub Pages
- **🎯 Iron Condor Strategy** - Defined-risk options trading on SPY only

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

## Current Performance (Day 72/90 - Jan 8, 2026)

| Account | Equity | P/L | Status |
|---------|--------|-----|--------|
| Live | $30.00 | $0.00 | Accumulating $25/day |
| Paper (R&D) | $5,000.00 | $0.00 | FRESH START (reset Jan 7) |

| Metric | Value | Target |
|--------|-------|--------|
| Win Rate | N/A | 55%+ |
| Positions | 0 | - |
| Backtest Pass | 19/13 | Scenarios |

**Honest Assessment**: Live trading started Jan 3, 2026 with fresh $20 deposit. Accumulating $25/day for defined-risk options spreads ($500 minimum for CSPs). Paper account was RESET to $5,000 on Jan 7, 2026 by CEO to match realistic 6-month capital milestone. Previous $100K+ paper results were unrealistic for actual capital trajectory.

---

## Strategy: Cash-Secured Puts

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

# Check positions
python3 scripts/check_positions.py

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
│  4. Options Strategy - Cash-secured puts                    │
│  5. Daily Verification - Honest reporting                   │
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
| **Thompson Sampler** | Strategy selection | `src/learning/thompson_sampler.py` |
| **Trade Memory** | SQLite journal | `src/learning/trade_memory.py` |
| **Risk Manager** | Position sizing | `src/risk/` |
| **Daily Verification** | Honest reporting | `scripts/daily_verification.py` |

---

## Learning System

### Thompson Sampling (replaces complex RL)
- Beta distribution for each strategy
- Sample to select best strategy
- Update based on win/loss outcomes
- Proven optimal for <100 decisions

### Trade Memory (replaces RAG)
- SQLite database of past trades
- Query BEFORE each new trade
- Pattern recognition: "This setup has 30% win rate - AVOID"
- Simple but effective

---

## Risk Management

**This is NOT financial advice. Paper trade first!**

| Safeguard | Description |
|-----------|-------------|
| **Position Limits** | Max 5% per position |
| **Daily Loss Limit** | 2% max daily loss |
| **Circuit Breakers** | Auto-halt on 3 consecutive losses |
| **Paper Mode** | 90-day validation before live |

---

## Follow Our Journey

| Platform | Link | Description |
|----------|------|-------------|
| **GitHub Pages Blog** | [igorganapolsky.github.io/trading](https://igorganapolsky.github.io/trading/) | Daily trading reports, lessons learned |
| **Dev.to** | [@igorganapolsky](https://dev.to/igorganapolsky) | AI trading insights, tutorials |
| **Daily Reports** | [/reports/](https://igorganapolsky.github.io/trading/reports/) | Transparent P/L tracking |
| **Lessons Learned** | [/lessons/](https://igorganapolsky.github.io/trading/lessons/) | 101+ documented lessons |

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
