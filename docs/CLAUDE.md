# Trading System - Project Context

**For detailed agent coordination and protocols, see `.claude/CLAUDE.md`**

---

## About This Project

AI-powered automated trading system using momentum indicators (MACD + RSI + Volume) with multi-agent architecture. Currently in 90-day R&D phase (paper trading) building profitable trading edge.

**Key Technologies**:
- Python 3.10+ with type hints required
- Alpaca API for trading execution
- Multi-agent system (Research, Signal, Risk, Execution agents)
- Streamlit dashboard for monitoring
- GitHub Actions for cloud deployment
- MCP (Model Context Protocol) for tool integrations

---

## Key Directories

```
trading/
├── src/
│   ├── agents/              # Multi-agent trading system
│   │   ├── research_agent.py      # Market analysis + sentiment
│   │   ├── signal_agent.py        # Technical indicators (MACD/RSI/Volume)
│   │   ├── risk_agent.py          # Position sizing + safety checks
│   │   ├── execution_agent.py      # Order execution + validation
│   │   └── meta_agent.py          # Hierarchical coordinator
│   ├── core/                # Core trading infrastructure
│   │   ├── alpaca_trader.py       # Alpaca API wrapper
│   │   ├── indicators.py          # Technical indicators
│   │   └── risk_manager.py        # Risk management rules
│   ├── strategies/          # Trading strategies (Tier 1-4)
│   ├── orchestration/       # Orchestrator implementations
│   ├── ml/                  # Machine learning models (LSTM-PPO)
│   └── utils/               # Utilities (data fetching, logging)
├── scripts/                 # Automation scripts
│   ├── autonomous_trader.py      # Daily execution (legacy)
│   └── advanced_autonomous_trader.py  # Multi-agent execution
├── data/                    # System state and trade logs
│   ├── system_state.json          # Current system state (READ FIRST)
│   ├── trades_YYYY-MM-DD.json     # Daily trade logs
│   └── trading_plans/             # Trading plan execution logs
├── docs/                    # Comprehensive documentation (150+ files)
├── tests/                   # Unit tests (pytest)
├── dashboard/               # Streamlit dashboard
└── .claude/                 # Claude-specific configs and hooks
```

---

## Coding Standards

- **Type Hints**: Required on all functions
- **Testing**: pytest (fixtures in `tests/conftest.py`)
- **Code Style**: PEP 8 with 100 character lines
- **Error Handling**: Comprehensive logging via loguru
- **State Management**: All state in `data/system_state.json` (verify freshness)
- **Documentation**: README.md is source of truth, detailed docs in `docs/`

---

## Common Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt

# Run trading system (paper mode)
PYTHONPATH=src python3 -m orchestrator.main --mode paper

# Legacy single-script execution
python scripts/autonomous_trader.py

# Run tests
python -m pytest tests/ -v

# Run backtests
python run_backtest_now.py

# Launch dashboard
streamlit run dashboard/trading_dashboard.py

# Check current positions
python scripts/check_positions.py
```

---

## Critical Protocols

### Verification Protocol (MANDATORY)
**ALWAYS verify trading results before reporting**:
1. Read CEO hook (displayed at conversation start) - highest authority
2. Query Alpaca API directly (`api.get_account()`, `api.list_positions()`)
3. Check timestamps in `data/system_state.json` (reject if >24h old)
4. Trust hierarchy: Hook > API > Files

**See `docs/verification-protocols.md` for full "SHOW, DON'T TELL" protocol**

### Autonomous Execution Protocol
- **NEVER ask CEO to run commands** - execute everything autonomously
- **ALWAYS commit and push changes** - never leave uncommitted work
- **NO manual steps** - system is fully automated
- **Report accomplishments, not instructions**

### Trading Strategy
- **Tier 1 (60%)**: Core ETFs (SPY, QQQ, VOO, BND) - momentum-based selection
- **Tier 2 (20%)**: Growth stocks (NVDA, GOOGL, AMZN) - 3-way rotation
- **Tier 3 (10%)**: IPO reserve (manual execution via SoFi)
- **Tier 4 (10%)**: Crowdfunding reserve (manual execution)
- **Daily Investment**: $10/day fixed (Fibonacci compounding strategy)

---

## Current Phase

**R&D Phase (Days 1-90)** - Building profitable trading edge
- **Month 1**: Infrastructure + data collection (current)
- **Month 2**: Build trading edge (MACD + RSI + Volume)
- **Month 3**: Validate & optimize (RL agent integration)

**Goal**: Build RL + Momentum system that can make $100+/day by Month 6

**See `docs/r-and-d-phase.md` for full R&D strategy**

---

## Key Documentation

**CRITICAL - Read These First**:
- `docs/verification-protocols.md` - "Show, Don't Tell" protocol (MANDATORY)
- `docs/r-and-d-phase.md` - Current R&D phase strategy
- `docs/STRATEGIES.md` - Trading strategy details
- `.claude/CLAUDE.md` - Detailed agent coordination and protocols

**Architecture**:
- `docs/MULTI_AGENT_ARCHITECTURE.md` - Multi-agent system design
- `docs/2025_MULTI_AGENT_SYSTEM.md` - Current agent implementation
- `README.md` - Project overview and quickstart

---

## Environment Variables

Required in `.env`:
```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
PAPER_TRADING=true
DAILY_INVESTMENT=10.0
```

Optional:
- `OPENROUTER_API_KEY` - For multi-LLM analysis
- `ANTHROPIC_API_KEY` - For Claude agents
- `GOOGLE_API_KEY` - For Gemini agent

---

## Automated Operations

- **Weekdays 9:35 AM ET**: Execute equity trades (Tier 1 + 2)
- **Weekdays 10:00 AM ET**: Generate daily CEO report

All automation via GitHub Actions workflows.

---

## Important Notes

- **State Files**: `data/system_state.json` is source of truth for system state
- **Trade Logs**: `data/trades_YYYY-MM-DD.json` contains daily execution logs
- **CEO Reports**: `reports/daily_report_YYYY-MM-DD.txt` - latest = current status
- **Paper Trading**: Currently validating system (90-day R&D phase)
- **Never lie about trading results** - always verify against CEO hook and Alpaca API

---

**Last Updated**: November 26, 2025
**For detailed protocols and agent coordination, see `.claude/CLAUDE.md`**
