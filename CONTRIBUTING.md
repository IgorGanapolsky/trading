# Contributing

Thanks for improving this paper-first trading lab. Operational safety and honest validation are the product; tests, dry runs, and paper fills are not proof of edge.

## Before you start

1. Read [AGENTS.md](AGENTS.md) and [skills/trading-ops/SKILL.md](skills/trading-ops/SKILL.md).
2. Confirm the active strategy in `data/runtime/strategy_kill_switch.json`.
3. Claim a Linear issue with the shared bridge and follow [docs/AGENT_COORDINATION.md](docs/AGENT_COORDINATION.md).
4. Create a dedicated worktree from current `origin/main`:

```bash
git fetch origin main
git worktree add -b feature/<issue-key>-<slug> .worktrees/<slug> origin/main
cd .worktrees/<slug>
make setup
```

Linear owns task assignment, the shared Obsidian vault records the live claim, Herdr exposes terminal lifecycle, and the issue-scoped worktree/PR is code truth.

## Development loop

```bash
make format
make check
make dry-run
```

The dry run must not submit an order. Never bypass a kill switch, halt, or risk gate to make a test pass.

## Repository contract

- `src/` contains importable code; imports must not perform network calls, start services, or require credentials.
- `scripts/` contains explicit command-line entry points. Shared behavior belongs in `src/`.
- `skills/` contains distributable agent procedures. Contributor policy belongs here and in `AGENTS.md`.
- `data/` contains only compact canonical inputs and ledgers described in `data/README.md`.
- `rag_knowledge/` contains curated evidence. Runtime indexes and provider caches are rebuilt locally.
- Generated screenshots, logs, reports, local databases, caches, coverage output, and model binaries are not source artifacts.
- Every retained workflow needs a current owner, bounded permissions, concurrency where it mutates state, and a contract test.

Add the narrowest test that proves the behavior and its failure mode. Use temporary directories for writes. Keep test/CI, plan/submission/fill, paper/live, and model/outcome evidence separate.

Add a dependency only when retained code imports it. Optional providers must follow `docs/EXTENSIONS.md`; initialize them lazily and validate data at the host boundary.

## Change boundaries

| Normal PR scope | Extra scrutiny required |
| --- | --- |
| Tests, docs, hygiene | Risk constants and mandatory gates |
| RAG lessons and retrieval | Broker submission or exit automation |
| Dead-code removal with caller evidence | Live-account paths or halt behavior |

Do not force-push `main`, hardcode credentials, re-enable killed iron-condor entry paths, or create repository-local task boards. Open a PR against `main` and include exact test and CI evidence.

Contributions use the repository's MIT license.
