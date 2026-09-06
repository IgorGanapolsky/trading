# JIT task→harness packs (AGENT-579 / AGENT-580)

Process steal from [JIT-Agent](https://arxiv.org/abs/2608.25593) (v2, Sept 2026):
**harness quality can dominate model quality**. A smaller model with the right
task-specific harness can beat a stronger model in a fat fixed runtime.

We do **not** train or vendor JIT-Agent. We implement a **deterministic**
task→pack selector aligned to Sept 2026 harness craft.

## Four modules (JIT protocol → trading)

| JIT module | Trading mapping                                    |
| ---------- | -------------------------------------------------- |
| memory     | Ledgers / kill switch / RAG paths to load          |
| planning   | Ordered operator steps (`plan`)                    |
| action     | Allowed scripts / make targets (`actions`)         |
| capability | Skills allowlist + forbid denylist (`tool_policy`) |

## Sept 2026 standards we keep

1. **Task-specific packs** beat one fat fixed context dump.
2. **Minimal skill surface** — in-repo `skills/` only; readiness fails closed.
3. **Fail-closed capability gates** — paper-only forbids; unknown → status-only.
4. **Explicit intent conflicts** — e.g. `--status` + `dry-run` → `dry_run` with note.
5. **Selection receipts** — `logs/jit_harness_receipts.jsonl` for archive/eval
   (not online RL / not training a harness model).
6. **Lazy disclosure** — load the pack for the task, not every skill.

## Operator

```bash
.venv/bin/python scripts/jit_harness.py --check-ready
.venv/bin/python scripts/jit_harness.py "account status"
.venv/bin/python scripts/jit_harness.py --json "put credit dry-run"
.venv/bin/python scripts/jit_harness.py --receipt "spy_put_credit --status --dry-run"
.venv/bin/python scripts/jit_harness.py --receipt --record "merge ready PRs"
.venv/bin/python -m pytest tests/test_jit_harness.py -q
```

## Task classes

`status` · `dry_run` · `inventory` · `rag_search` · `pr_hygiene` ·
`residual_ic` · `broker_sync` · `unknown` (fail-closed → status-only)

## Explicit non-goals

- Training a harness-generation model / vendoring JIT-Agent-27B
- Auto-evolving harness weights from online RL
- Untracked theater under `scripts/jit_agent_*.py`
- Live order submission paths

## Prevention

`tests/test_jit_harness.py` locks classification (incl. flag order + conflicts),
four-module/capability shape, paper-only forbids, readiness honesty, and receipt
CLI so agents cannot silently fall back to a fat pack.
