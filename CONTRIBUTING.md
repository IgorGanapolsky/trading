# Contributing

Thanks for improving this lab. The product here is **operational safety and honest validation**, not a marketed edge.

## Before you start

1. Read [AGENTS.md](./AGENTS.md) if you are an AI agent (or working with one).
2. Read [skills/trading-ops/SKILL.md](./skills/trading-ops/SKILL.md) for operator commands and hard gates.
3. Confirm active strategy in `data/runtime/strategy_kill_switch.json` — do not “revive” killed IC entry paths.

## Development workflow

```bash
git fetch origin main
git worktree add -b feature/<slug> .worktrees/<slug> origin/main
cd .worktrees/<slug>

# validate
pytest tests/ -q
ruff check src/
```

Open a PR against `main`. Include evidence for claims (command output, CI run IDs).

### Do

- Keep paper-first defaults
- Prefer dry-run for strategy changes
- Update tests when changing gates or kill switches
- Keep secrets out of the repo

### Don’t

- Force-push `main`
- Hardcode API keys
- Delete or bypass the guardian / halt files without an explicit override path
- Re-enable iron condor **entry** workflows without a written hypothesis + CEO-visible kill-criteria update

## Scope of changes

| Welcome                              | Needs extra care                         |
| ------------------------------------ | ---------------------------------------- |
| Tests, docs, hygiene                 | Risk constants in `trading_constants.py` |
| RAG lessons, reports                 | Order submission / exit automation       |
| Dead-code removal with grep evidence | Live-account paths                       |

## Docs

Human-facing index: [docs/README.md](./docs/README.md).

## License

By contributing, you agree your contributions are under the same license as the repository.
