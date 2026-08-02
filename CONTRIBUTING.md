# Contributing

Use Python 3.11 and make each change in a dedicated Git worktree branched from current `origin/main`. Preserve unrelated worktree changes.

## Development loop

```bash
make setup
make format
make check
```

For changes to trading, broker state, RAG, orchestration, workflows, dependencies, or configuration, also run `make dry-run`. The dry run must not submit an order. Never bypass the live kill switch to make a test pass.

## Repository contract

- `src/` contains importable code; imports must not perform network calls, start services, or require credentials.
- `scripts/` contains explicit command-line entry points. Shared behavior belongs in `src/`.
- `data/` contains only compact canonical inputs and ledgers described in `data/README.md`.
- `rag_knowledge/` contains curated evidence. Runtime indexes and provider caches are rebuilt locally.
- Generated screenshots, logs, reports, local databases, caches, coverage output, and model binaries are not source artifacts.
- Every retained GitHub workflow needs a current owner, bounded permissions, concurrency where it mutates state, and a contract test.

Add the narrowest test that proves the behavior and its failure mode. Use temporary directories for anything that writes. Keep test/CI, plan/submission/fill, paper/live, and model/outcome evidence separate.

Add a dependency only when retained production code imports it. Optional providers must follow `docs/EXTENSIONS.md`; keep provider initialization lazy and validate data at the host boundary.

Never commit credentials, `.env` files, provider databases, or user-specific absolute paths.

