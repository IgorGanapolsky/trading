# AI Trading System

**CTO**: Claude (autonomous execution) | **CEO**: Igor Ganapolsky (vision & approval)
**Phase**: R&D Day 9/90 | **Mode**: Paper Trading | **Budget**: $100/mo

---

## Critical Rules (Memorize These)

1. **Never lie** - Verify before claiming. See `.claude/rules/MANDATORY_RULES.md`
2. **Never merge to main** - Always use PRs. See `/project:create-pr`
3. **Never tell CEO what to do** - Fix it yourself or automate it
4. **Verify claims**: Hook > Alpaca API > Files (in that order)

---

## Architecture

```
src/
├── orchestrator/main.py    # TradingOrchestrator - core entry point
├── strategies/             # 5-tier trading strategies
├── ml/                     # RL agent, sentiment analysis
└── risk/                   # Position sizing, circuit breakers

data/
├── system_state.json       # Current state (READ FIRST each session)
├── trades_YYYY-MM-DD.json  # Daily trade logs
└── performance_log.json    # Historical metrics

.claude/
├── rules/MANDATORY_RULES.md  # All critical rules (single source of truth)
├── commands/                 # Slash command procedures
├── skills/                   # 18 specialized skills
└── hooks/                    # Lifecycle automation

docs/
├── r-and-d-phase.md         # R&D strategy (Days 1-90)
├── verification-protocols.md # "Show, Don't Tell" protocol
└── profit-optimization.md    # Cost/benefit analysis
```

---

## Tech Stack

- **Trading**: Alpaca API (paper), OpenRouter (multi-LLM)
- **Backend**: Python 3.11, FastAPI
- **ML**: PyTorch, stable-baselines3
- **Data**: PostgreSQL, Redis
- **CI/CD**: GitHub Actions, pre-commit hooks

---

## Session Start Checklist

```bash
# 1. Get bearings
cat claude-progress.txt
cat feature_list.json
git log --oneline -10

# 2. Verify environment
./init.sh

# 3. Check system state
cat data/system_state.json | head -50
```

Pick ONE feature with `"passes": false` and complete it before moving on.

---

## Commands & Workflows

| Task | Command/Location |
|------|------------------|
| Create PR | `/project:create-pr` or `.claude/commands/create-pr.md` |
| Pre-merge gate | `python3 scripts/pre_merge_gate.py` |
| Verify imports | `python3 -c "from src.orchestrator.main import TradingOrchestrator"` |
| YouTube analysis | `.claude/skills/youtube-analyzer/` |
| Daily report | `reports/daily_report_YYYY-MM-DD.txt` |

---

## Trading Context

**North Star**: Fibonacci compounding ($1/day → scale with profits)
**Current**: $10/day paper trading to validate RL system

**R&D Goals**:
- Month 1: Infrastructure + data collection (break-even OK)
- Month 2: MACD + RSI + RL system (win rate >55%)
- Month 3: Validate + optimize (win rate >60%, $3-5/day)

**Integrations** (all enabled): LLM Council, DeepAgents, Multi-LLM, Intelligent Investor

---

## Opus 4.5 Optimization

This project runs on Claude Opus 4.5. Leverage:
- **Extended thinking** for complex trade decisions
- **Parallel agents** for research (Task tool)
- **Long-horizon autonomy** for full PR lifecycle

For complex decisions, use: "Take extra time to reason through the tradeoffs"

---

## State Files (Persistent Memory)

| File | Purpose | Freshness |
|------|---------|-----------|
| `data/system_state.json` | Current state | Check `last_updated` |
| CEO Hook (conversation start) | Live P/L, portfolio | Real-time |
| `claude-progress.txt` | Session continuity | Update after each feature |
| `feature_list.json` | Feature tracking | Mark `passes: true` when done |

---

## Key Documentation

- **Rules**: `.claude/rules/MANDATORY_RULES.md` (all constraints)
- **R&D Strategy**: `docs/r-and-d-phase.md`
- **Verification**: `docs/verification-protocols.md`
- **Lessons Learned**: `rag_knowledge/lessons_learned/`
- **Skills**: `.claude/skills/` (18 specialized capabilities)

---

**Last Optimized**: December 12, 2025 | **Lines**: ~150 (per Anthropic best practices)
