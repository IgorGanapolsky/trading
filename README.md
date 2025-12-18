# AI Options Trading Bot

[![Win Rate](https://img.shields.io/badge/win_rate-50%25-yellow.svg)](docs/r-and-d-phase.md)
[![Status](https://img.shields.io/badge/status-paper_trading-yellow.svg)](docs/r-and-d-phase.md)
[![Day](https://img.shields.io/badge/day-50%2F90-blue.svg)](docs/r-and-d-phase.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Open-source AI-powered trading system** using options premium selling and Thompson Sampling strategy selection. Built with Python and Alpaca API.

> **Current Status**: Day 50/90 R&D Phase | $99,450 equity | 50% win rate

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

## Current Performance (Day 50/90)

| Metric | Value | Status |
|--------|-------|--------|
| Equity | $99,449.77 | Paper |
| P/L | -$550.23 | -0.55% |
| Win Rate | 50% | Target: 55%+ |
| Backtest Pass | 0/13 | Needs work |

**Honest Assessment**: System is break-even after 50 days. Options strategy shows promise but execution needs improvement.

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
