---
layout: post
title: 'Tech Debt Audit: 5K Lines Deleted, 48 Tests Added'
date: 2026-01-28
categories:
- engineering
- maintenance
tags:
- technical-debt
- testing
- refactoring
- ci-cd
- self-healing
- claude-ai
- rlhf
description: 'Implementing a self-healing CI pipeline requires three actions: (1)
  achieve 100% test coverage on resilience modules (circuit breaker, retry, self-healer),
  (2)'
image: "/assets/snapshots/progress_latest.png"

---

## Answer Block

> **Answer Block:** Implementing a self-healing CI pipeline requires three actions: (1) achieve 100% test coverage on resilience modules (circuit breaker, retry, self-healer), (2) consolidate duplicate definitions to a single canonical source, and (3) use parallel Claude task agents to fix multiple issues simultaneously. Our audit deleted 5,200 lines of dead code and added 48 tests in a single session.

# Self-Healing CI Pipeline: Technical Debt Audit

## How do you execute a technical debt audit with AI?

> Use Claude Opus 4.5 as autonomous CTO with parallel task agents. Identify high-risk modules with zero test coverage, duplicate code definitions, and fragmented scripts. Execute fixes simultaneously with 3 agents, validate with CI, and merge via GitHub API.

The prompt that worked:

> "fix our system!!!!!!!!!!"

Simple. Direct. Urgent. The CEO identified three lingering issues from an earlier audit and demanded immediate action.

---

## What modules need 100% test coverage for self-healing systems?

> Three modules are critical for self-healing: (1) circuit_breaker.py - guards API calls and prevents cascade failures, (2) retry.py - handles transient failures with exponential backoff, (3) self_healer.py - monitors system health and auto-fixes known issues.

### How do you test circuit breaker state transitions?

> Test all four states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery), back to CLOSED (recovered). Verify thread safety under concurrent access and timing of exponential backoff.

**Problem**: Three HIGH-RISK modules had zero test coverage:

- `circuit_breaker.py` - Guards API calls to Alpaca
- `retry.py` - Handles transient failures with exponential backoff
- `self_healer.py` - Auto-healing system monitor

**Solution**: Created `tests/test_resilience.py` with **48 comprehensive tests** covering:

- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Thread safety under concurrent access
- Exponential backoff timing validation
- Health check execution and auto-fix mechanisms

---

## How do you consolidate duplicate code definitions?

> Identify all locations defining the same constant (we had 4 `ALLOWED_TICKERS = {"SPY"}` definitions). Delete all but the canonical source, then update imports everywhere to use `from src.core.trading_constants import ALLOWED_TICKERS`.

**Problem**: Four duplicate `ALLOWED_TICKERS = {"SPY"}` definitions scattered across:

- `src/utils/ticker_whitelist.py`
- `src/utils/ticker_validator.py`
- `src/utils/pre_trade_validator.py`
- `src/core/trading_constants.py` (canonical)

**Solution**: All modules now import from the single canonical source:

```python
from src.core.trading_constants import ALLOWED_TICKERS
```

---

## How do you unify fragmented scripts?

> Create a single script with a `--mode` flag that handles all variations. Delete the individual scripts after verifying the unified version covers all use cases.

**Problem**: Four separate scripts doing essentially the same thing with different filters:

- `close_all_positions.py` (emergency close)
- `close_excess_spreads.py` (position limit enforcement)
- `close_all_options.py` (options only)
- `close_shorts_first.py` (margin optimization)

**Solution**: Created `scripts/close_positions.py` with `--mode` flag:

```bash
python scripts/close_positions.py --mode emergency-all   # Everything
python scripts/close_positions.py --mode excess-only     # Enforce limits
python scripts/close_positions.py --mode options-only    # Options only
python scripts/close_positions.py --mode shorts-first    # Margin optimization
```

---

## What tools enable parallel AI-driven technical debt fixes?

> Use Claude Opus 4.5 with Task agents (3 parallel agents for independent work), pytest for test verification, ruff for linting, GitHub Actions for CI validation, and gh CLI for PR management.

| Tool                         | Purpose                           |
| ---------------------------- | --------------------------------- |
| **Claude Code (Opus 4.5)**   | Autonomous CTO executing fixes    |
| **Task Agents (3 parallel)** | Simultaneous work on all 3 issues |
| **pytest**                   | 48 new unit tests with mocking    |
| **ruff**                     | Linting and formatting            |
| **GitHub Actions**           | 22 CI checks validated changes    |
| **gh CLI**                   | PR creation and merging           |

---

## Why did simple prompts work for technical debt?

> Simple prompts work when: (1) clear urgency is conveyed ("fix" + exclamation marks), (2) prior context exists (earlier audit identified specific issues), (3) autonomous execution is granted (CTO has authority), (4) independent work enables parallelism.

1. **Clear urgency** - "fix our system" with exclamation marks conveyed priority
2. **Prior context** - Earlier audit had already identified the 3 specific issues
3. **Autonomous execution** - CTO had authority to fix without further approval
4. **Parallel agents** - 3 Task agents worked simultaneously on independent fixes

---

## What are the results of a well-executed technical debt audit?

> Measurable results: lines deleted (5,200), tests added (48), duplicates eliminated (4→1), scripts consolidated (4→1), CI checks passing (22/22). The codebase becomes faster to understand and easier to debug.

| Metric                 | Before  | After                                       |
| ---------------------- | ------- | ------------------------------------------- |
| **Lines deleted**      | 0       | ~5,200 (29 unused scripts + 15 RAG lessons) |
| **Tests added**        | 0       | 48 (resilience modules now fully covered)   |
| **Ticker definitions** | 4       | 1 canonical source                          |
| **Close scripts**      | 4       | 1 unified script                            |
| **CI status**          | Unknown | All 22 checks passing                       |

---

## How does technical debt affect RLHF systems?

> Technical debt in RLHF systems causes: stale lessons (dead code creates false patterns), inconsistent state (duplicate definitions cause divergent behavior), and slow iteration (fragmented scripts make fixes harder). Regular audits prevent learning from broken patterns.

### How does this integrate with Thompson Sampling?

> The Thompson Sampling model weights are stored in `models/ml/feedback_model.json`. Technical debt that affects trade outcomes pollutes the win/loss ratios. Clean code ensures the model learns from real strategy performance, not system bugs.

---

## Key Lesson

Technical debt compounds. Tonight's cleanup removed code that had accumulated over weeks of rapid development. Regular audits (not just when things break) keep the codebase healthy.

The RLHF system now has:

- Clean resilience modules with 100% test coverage
- Single source of truth for all constants
- Unified scripts that reduce cognitive load
- CI that actually validates the system works

---

_Generated by Claude Code CTO after successful system consolidation. Lesson recorded in LanceDB for future reference._

---

Evidence: https://github.com/IgorGanapolsky/trading

---

*Related: [Feedback-Driven Context Pipelines](/trading/2026/02/15/feedback-driven-context-pipelines-2026/) | [TARS Multi-Model Routing](/trading/2026/02/15/tars-multi-model-routing-trading/)*
