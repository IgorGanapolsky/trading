# AI Trading System - Universal Agent Instructions

> AI-powered trading system using Alpaca API with multi-LLM consensus analysis.
> Current Phase: R&D (Days 1-90) - Paper trading to build profitable edge.

## Quick Reference

```bash
# Setup
pip install -r requirements.txt

# Run tests
pytest tests/unit -v                    # Fast unit tests (~30s)
pytest tests/safety -v                  # Safety tests (critical)
pytest tests/ -v --ignore=tests/e2e     # All except E2E

# Type checking
mypy src/ --ignore-missing-imports

# Syntax verification (MANDATORY before merge)
find src -name "*.py" -exec python3 -m py_compile {} \;
python3 -c "from src.orchestrator.main import TradingOrchestrator; print('OK')"
```

## Tech Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Primary language |
| Alpaca Trade API | 3.0.2 | Brokerage integration |
| Pandas | 2.1.3+ | Data analysis |
| Pydantic | 2.5.0+ | Validation & type safety |
| pytest | 7.4.3+ | Testing framework |
| yfinance | 0.2.66 | Market data (local wheel) |

## Architecture Overview

```
src/
├── orchestrator/       # Main trading orchestrator (entry point)
├── strategies/         # Trading strategy implementations
├── safety/            # Risk management & circuit breakers
├── agents/            # Multi-agent system components
├── ml/                # Machine learning models
├── rag/               # RAG knowledge system
├── analytics/         # Performance tracking
├── backtesting/       # Strategy backtesting
└── utils/             # Shared utilities

data/                  # Runtime data (system_state.json, trades, etc.)
tests/                 # Test suites mirroring src/ structure
docs/                  # Human documentation
rag_knowledge/         # Lessons learned, decisions
scripts/               # Utility scripts
```

## Critical Business Rules

**Risk Management (NEVER VIOLATE)**:
- Max risk per trade: 2% of portfolio
- Max position size: 5% of portfolio
- Max concurrent positions: 5
- Trading hours: 9:35 AM - 3:55 PM ET (5min buffer)
- Daily budget: $10.50 (weekdays)

**Trade Execution**:
- All trades via Alpaca API (paper mode during R&D)
- Validate all signals through safety checks before execution
- Log all trades to `data/trades_YYYY-MM-DD.json`

## Coding Standards

### Python Style
- PEP 8 compliance (Black formatter, 88 char lines)
- Type hints REQUIRED for all function signatures
- Google-style docstrings with Args, Returns, Raises
- Pydantic models for data validation

### Good Pattern
```python
from typing import Optional
from decimal import Decimal

def calculate_position_size(
    equity: Decimal,
    risk_percent: float,
    entry_price: Decimal,
    stop_loss: Decimal
) -> int:
    """Calculate position size using volatility-adjusted risk.

    Args:
        equity: Total account equity in USD
        risk_percent: Maximum portfolio risk (0.01 = 1%)
        entry_price: Planned entry price per share
        stop_loss: Stop loss price per share

    Returns:
        Number of shares to purchase (integer)

    Raises:
        ValueError: If stop_loss >= entry_price
    """
    if stop_loss >= entry_price:
        raise ValueError("Stop loss must be below entry price")
    risk_per_share = entry_price - stop_loss
    max_risk = equity * Decimal(str(risk_percent))
    return int(max_risk / risk_per_share)
```

### Anti-Pattern (AVOID)
```python
# No types, no docstring, unclear naming
def calc(e, r, p, s):
    return int((e * r) / (p - s))
```

## Boundaries (NEVER TOUCH)

- `data/` - Managed by system, never manually edit
- `*.env*` - Environment files with secrets
- `credentials*.json` - API credentials
- `node_modules/`, `venv/`, `.venv/` - Dependencies
- Production configs in `config/prod/`

## Git Workflow

- Branch naming: `claude/feature-description-<unique-id>`
- Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- **NEVER push directly to main** - always use PRs
- **NEVER merge without passing CI** - verify ALL jobs green
- Pre-merge: Run `python3 scripts/pre_merge_gate.py`

## Verification Protocol

**Before claiming success, VERIFY**:
1. Run command and check exit code = 0
2. Read output for errors (not just "completed")
3. For file writes, verify content persisted
4. For git operations, check `git status`

**HONESTY > SPEED**: Better to say "still waiting" than to claim premature success.

## Key Files

| File | Purpose |
|------|---------|
| `data/system_state.json` | Current system state (read first each session) |
| `.claude/CLAUDE.md` | Claude-specific instructions |
| `claude-progress.txt` | Session progress tracking |
| `feature_list.json` | Feature completion status |
| `rag_knowledge/lessons_learned/` | Past mistakes to avoid |

## Session Start Protocol

1. Read `claude-progress.txt` for recent work
2. Check `data/system_state.json` for current state
3. Run `git status` to see branch/uncommitted changes
4. Run `./init.sh` to verify environment
5. Consult `rag_knowledge/lessons_learned/` before complex changes

## RAG Knowledge System

Before implementing complex logic, QUERY the RAG system:
```bash
# Check for lessons learned
python3 scripts/query_rag.py "lessons learned backtesting"

# After finding a bug, ingest a lesson
python3 scripts/ingest_lesson.py --title "Bug description" --content "What happened and how to avoid"
```

## Multi-Agent Coordination

This repo supports multiple AI agents working in parallel:
- Use git worktrees for parallel branch work
- Module ownership documented in nested AGENTS.md files
- State shared via `data/system_state.json`
- Progress tracked in `claude-progress.txt`

## Tool-Specific Notes

**Claude Code**: See `.claude/CLAUDE.md` for extended instructions
**Cursor IDE**: See `.cursorrules` for IDE-specific rules
**GitHub Copilot**: This AGENTS.md file is auto-detected

---

## STRICT INTEGRITY PROTOCOL

1. **NEVER ASSUME SUCCESS** - Verify all commands completed
2. **VERIFY BACKGROUND COMMANDS** - Check exit codes and output
3. **VERIFY FILE WRITES** - Confirm changes persisted
4. **ADMIT MISTAKES** - Never double down on errors

## AUTONOMOUS EXECUTION

- I am the CTO; user is CEO
- Full GitHub PAT access for autonomous PR management
- Create AND merge PRs without asking
- Never tell user to do manual work - DO IT MYSELF
- Commit and push all changes immediately

**Violation of integrity rules is a critical failure.**
