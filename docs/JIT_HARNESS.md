# JIT task→harness packs (AGENT-579)

Process steal from [JIT-Agent](https://arxiv.org/abs/2608.25593) (Rohan Paul /
@rohanpaul_ai summary, 2026-09-02): **a smaller model with the right
task-specific harness can beat a stronger model** in a fat fixed runtime, with
lower token/API cost.

We do **not** train or vendor JIT-Agent. We steal the _composable four-module
harness artifact_ and select packs deterministically for trading ops.

## Four modules

| Module  | Trading mapping                                   |
| ------- | ------------------------------------------------- |
| memory  | Ledgers / kill switch / RAG paths to load         |
| plan    | Ordered operator steps                            |
| actions | Allowed scripts / make targets                    |
| skills  | Skill routes (+ hard forbids for live / freehand) |

## Operator

```bash
.venv/bin/python scripts/jit_harness.py --check-ready
.venv/bin/python scripts/jit_harness.py "account status"
.venv/bin/python scripts/jit_harness.py --json "put credit dry-run"
.venv/bin/python scripts/jit_harness.py "merge ready PRs"
```

## Task classes

`status` · `dry_run` · `inventory` · `rag_search` · `pr_hygiene` ·
`residual_ic` · `broker_sync` · `unknown` (fail-closed → status-only)

## Explicit non-goals

- Training a harness-generation model
- Auto-evolving harness archives from online RL
- Untracked theater under `scripts/jit_agent_*.py` in dirty checkouts
- Live order submission paths

## Prevention

`tests/test_jit_harness.py` locks classification, four-module shape, paper-only
forbids, and CLI readiness so agents cannot silently fall back to a fat pack.
