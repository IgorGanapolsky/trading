# Claude Reference Documentation

Extended documentation for the trading system. Not loaded every session.
Reference this file with `@.claude/REFERENCE.md` when needed.

## Architecture

```
src/
├── orchestrator/main.py    # TradingOrchestrator - core entry point
├── strategies/             # 5-tier trading strategies
├── agents/                 # Trading agents (momentum, debate, RL)
└── risk/                   # Position sizing, circuit breakers

data/
├── system_state.json       # Current state (READ FIRST each session)
├── trades_YYYY-MM-DD.json  # Daily trade logs
└── performance_log.json    # Historical metrics
```

## Tech Stack

- **Trading**: Alpaca API (paper), OpenRouter (multi-LLM)
- **Backend**: Python 3.11, FastAPI
- **ML**: PyTorch, stable-baselines3
- **Data**: PostgreSQL, Redis
- **CI/CD**: GitHub Actions, pre-commit hooks

## Commands & Workflows

| Task | Command/Location |
|------|------------------|
| Create PR | `/project:create-pr` |
| Pre-merge gate | `python3 scripts/pre_merge_gate.py` |
| YouTube analysis | `.claude/skills/youtube-analyzer/` |
| Budget tracking | `skill: budget_tracker` |
| News analysis | `skill: text_analyzer` |
| Pre-trade research | `skill: deep_research` |

## R&D Goals

- Month 1: Infrastructure + data collection (break-even OK)
- Month 2: MACD + RSI + RL system (win rate >55%)
- Month 3: Validate + optimize (win rate >60%)

## Key Documentation

- **Rules**: `.claude/rules/MANDATORY_RULES.md`
- **R&D Strategy**: `docs/r-and-d-phase.md`
- **Verification**: `docs/verification-protocols.md`
- **Lessons Learned**: `rag_knowledge/lessons_learned/`
- **Skills**: `.claude/skills/` (17 specialized capabilities)

## Persistent Memory System

| Component | Purpose |
|-----------|---------|
| `/diary` | Record session learnings |
| `/reflect` | Analyze diary → update CLAUDE.md rules |
| `~/.claude/memory/diary/` | Diary storage |
| `data/feedback/` | Thumbs up/down tracking |
| `capture_feedback.sh` | Auto-capture feedback |
