# AI Options Trading Bot

[![Win Rate](https://img.shields.io/badge/win_rate-80%25-brightgreen.svg)](docs/r-and-d-phase.md)
[![Status](https://img.shields.io/badge/status-live_trading-green.svg)](docs/r-and-d-phase.md)
[![Day](https://img.shields.io/badge/day-69%2F90-blue.svg)](docs/r-and-d-phase.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Open-source AI-powered trading system** using options premium selling and Thompson Sampling strategy selection. Built with Python and Alpaca API.

> **Current Status**: Day 69/90 R&D Phase | Live: $30 (accumulating) | Paper: $101,084 (+1.08%) | 80% win rate

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

## Current Performance (Day 69/90)

| Account | Equity | P/L | Status |
|---------|--------|-----|--------|
| Live | $30.00 | $0.00 | Accumulating $10/day |
| Paper (R&D) | $101,083.86 | +$1,083.86 | +1.08% |

| Metric | Value | Target |
|--------|-------|--------|
| Win Rate | 80% | 55%+ |
| Positions | 5 | Active |
| Backtest Pass | 19/13 | Scenarios |

**Honest Assessment**: Live trading started Jan 3, 2026 with fresh $20 deposit. Accumulating $10/day for defined-risk options spreads ($100-200 minimum). Paper account validates strategy with 80% win rate and +$1,083 profit.

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
| **Lessons Learned** | [/lessons/](https://igorganapolsky.github.io/trading/lessons/) | 66+ documented lessons |

---

## For AI Agents & LLMs

This repo is optimized for AI agent collaboration. See **[AGENTS.md](AGENTS.md)** for:
- Quick context loading
- Key file locations
- Critical rules and constraints
- RAG knowledge base (`rag_knowledge/`)

**Claude Code users**: See `.claude/CLAUDE.md` for full context.

---

## Documentation

- **[R&D Phase](docs/r-and-d-phase.md)** - Current 90-day plan
- **[Verification Protocols](docs/verification-protocols.md)** - Safety mechanisms
- **[Profit Optimization](docs/profit-optimization.md)** - Strategy details
- **[Environment Variables](docs/ENVIRONMENT_VARIABLES.md)** - Configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues

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
