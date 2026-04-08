# AI Trading System

Project instructions live in `.claude/CLAUDE.md`. Rules auto-load from `.claude/rules/`.

## Dual-Track Strategy (Aligned Feb 23, 2026)

- **The Lab ($100K Paper)**: Formulation and GRPO self-training.
- **The Field (Live)**: $0 equity. Inactive — no capital deployed.
- **North Star**: $6,000/month after-tax passive income.

## Active Operating Scope

- Primary execution path: `scripts/iron_condor_trader.py`
- Canonical ledgers: `data/system_state.json` and `data/trades.json`
- Archived from the default operating path: blog/wiki/dashboard/pages publishing and discovery marketing workflows
- Never describe the system as profitable or validated unless current ledger data proves it

## Session Directive: PR Management & System Hygiene

- Execute session start protocol each run: read CLAUDE directives, query RAG lessons, inspect open PRs/branches, then check CI.
- Use evidence-based reporting for all PR/CI/branch claims (include command output and run IDs/SHAs).
- Merge PRs only when review criteria are met; report blockers immediately when present.
- Keep branch hygiene: remove stale/orphan branches after merges.
- Run operational readiness checks (CI on `main` + local dry-run health checks) before declaring completion.
- Record lessons learned in RAG after task completion.
- Completion confirmation phrase for this workflow:
  - "Done merging PRs. CI passing. System hygiene complete. Ready for next session."

Note: Never store secrets or tokens in this file.
