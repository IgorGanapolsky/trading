# AI Agent Quick Context Guide

> **For AI agents, LLMs, and multi-agent systems working on this codebase**

## TL;DR - 30 Second Context

```
PROJECT: AI Options Trading System
STATUS:  Paper trading, Day 50/90 R&D phase
GOAL:    $1/day profit via options premium
TECH:    Python 3.11, Alpaca API, Claude AI
EQUITY:  $100,697 (+$697 profit)
```

## Critical Rules (MUST READ)

1. **Never trade real money** - Paper mode only until Day 90
2. **Never merge to main directly** - Always use PRs
3. **Verify before claiming** - Test imports, run dry runs
4. **Market hours matter** - US equities: Mon-Fri 9:30-4:00 ET only
5. **Check calendar** - No trading on holidays (see `holidays` package)

## Key Entry Points

| To Do This | Start Here |
|------------|------------|
| Run trading | `src/orchestrator/main.py` |
| Execute trades | `src/execution/alpaca_executor.py` |
| Risk management | `src/risk/trade_gateway.py` |
| Core strategy | `src/strategies/core_strategy.py` |
| Check positions | `scripts/check_positions.py` |

## Directory Map

```
src/
├── orchestrator/    # Main trading logic (START HERE)
├── strategies/      # Trading strategies (5 tiers)
├── agents/          # Trading agents (momentum, sentiment, debate)
├── risk/            # Position sizing, circuit breakers
├── execution/       # Alpaca API integration
└── learning/        # Thompson Sampling, Trade Memory

data/
├── system_state.json     # Current state (CHECK FIRST)
├── trades_YYYY-MM-DD.json # Daily trade logs
└── performance_log.json   # Historical metrics

rag_knowledge/
├── lessons_learned/   # 66+ documented lessons
├── youtube/           # Phil Town transcripts
└── blogs/             # Trading wisdom
```

## State Files (Always Check First)

| File | Purpose | Check When |
|------|---------|------------|
| `data/system_state.json` | Current portfolio state | Every session |
| `claude-progress.txt` | Session continuity notes | Start of work |
| `feature_list.json` | Feature tracking | Before new features |

## RAG Knowledge Base

Located in `rag_knowledge/lessons_learned/`:
- **66+ lessons** from past mistakes
- Semantic search capability
- Query before making changes

**Top Lessons**:
- LL-051: Calendar awareness is critical
- LL-052: We do NOT trade crypto
- LL-010: Dead code causes silent failures

## For Claude Code Agents

Full context in `.claude/CLAUDE.md` including:
- Complete rules in `.claude/rules/MANDATORY_RULES.md`
- Skills in `.claude/skills/` (17 specialized capabilities)
- Commands in `.claude/commands/`

## API Keys Required

Set in `.env` or GitHub Secrets:
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` - Trading
- `OPENAI_API_KEY` - LLM reasoning
- `ANTHROPIC_API_KEY` - Claude integration
- `DEVTO_API_KEY` - Blog publishing

## Testing Before Changes

```bash
# Quick verification
python3 -c "from src.orchestrator.main import TradingOrchestrator; print('OK')"

# Full test suite
python -m pytest tests/ -v

# Lint check
ruff check src/
```

## CI/CD Pipeline

All PRs trigger:
- Lint & format check
- Unit tests
- Integration tests
- Workflow integrity check
- Phil Town RAG completeness check

**DO NOT** merge if CI is red.

## Common Tasks

### Add a new feature
1. Check `feature_list.json` for existing features
2. Query RAG for related lessons
3. Create feature branch
4. Implement with tests
5. Create PR (not direct merge)

### Fix a bug
1. Search `rag_knowledge/lessons_learned/` for similar issues
2. Write regression test FIRST
3. Fix the bug
4. Verify CI passes

### Update trading logic
1. Check `data/system_state.json` for current state
2. Review existing strategies in `src/strategies/`
3. Test in paper mode
4. Log to `rag_knowledge/lessons_learned/`

## Performance Metrics

Current targets:
- Win rate: >55%
- Sharpe ratio: >1.2
- Max drawdown: <10%
- Daily profit: $1+

---

**Last Updated**: December 24, 2025
**Maintained By**: Claude (CTO) + Igor Ganapolsky (CEO)
