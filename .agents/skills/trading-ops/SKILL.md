---
name: trading-ops
description: Audit and operate this repository's paper-only SPY put-credit path without confusing plans, submissions, fills, or profit evidence.
---

# Trading operations

Use this skill for repository health, RAG checks, strategy status, paper dry runs, broker reconciliation, or CI cleanup.

## Safety gate

Require `TRADING_ENV=paper` for any broker-aware operation. Never override `data/runtime/strategy_kill_switch.json`, never pass `--live`, and never treat a dry run as an order.

## Start

1. Read `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md`.
2. Query current lessons with `.venv/bin/python scripts/query_lessons_learned.py "<task keywords>" --limit 8`.
3. Inspect the worktree, open PRs, and current CI before editing.
4. Work in a dedicated Git worktree based on current `origin/main`.

## Verify

```bash
make check
TRADING_ENV=paper make dry-run
```

For RAG changes, prove keyword read and a temporary-directory write/read round trip. For orchestration changes, run targeted tests plus bounded health. For workflow changes, inspect current GitHub status and wait for PR checks.

Report local tests, CI SHA/run, strategy plan, broker submission, broker fill, and closed-trade cohort evidence as separate surfaces. Put-credit remains paper validation until the configured promotion thresholds pass.
