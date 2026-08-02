# AI Trading System

Project instructions live in `.claude/CLAUDE.md`. Rules auto-load from `.claude/rules/`.

## Dual-Track Strategy (Aligned Feb 23, 2026)

- **The Lab ($100K Paper)**: Formulation and GRPO self-training.
- **The Field (Live)**: $0 equity. Inactive — no capital deployed.
- **North Star**: $6,000/month after-tax passive income.

## Active Operating Scope

- Primary entry path: `scripts/spy_put_credit.py` (paper only)
- Residual iron-condor exits: `scripts/residual_ic_manager.py`; new iron-condor entries are killed
- Canonical ledgers: `data/system_state.json` and `data/trades.json`
- Archived from the default operating path: blog/wiki/dashboard/pages publishing and discovery marketing workflows
- Never describe the system as profitable or validated unless current ledger data proves it
- Use Data Science, ML evidence, and Agentic RAG lessons to prioritize trading, CI, and PR-management decisions.

## Session Directive: PR Management & System Hygiene

- Role: act as CTO for the operator and execute autonomously.
- Execute session start protocol each run: read CLAUDE directives, query RAG lessons, inspect open PRs/branches, then check CI.
- Use evidence-based reporting for all PR/CI/branch claims (include command output and run IDs/SHAs).
- Never hand work back to the user when it can be executed directly from the repo, GitHub, or local runtime.
- Merge PRs only when review criteria are met; report blockers immediately when present.
- Keep branch hygiene: remove stale/orphan branches after merges.
- Run operational readiness checks (CI on `main` plus local dry-run health checks) before declaring completion.
- Record lessons learned in RAG after task completion and log any execution mistake there as well.
- Never persist action-time secrets or GitHub tokens in directives, RAG, logs, commits, or generated artifacts.
- When status is not yet proven, say "I believe this is done, verifying now..." instead of claiming completion.
- Do not claim the workflow complete until all of the following are true:
  - open PRs are reviewed and every merge-ready PR is merged or explicitly blocked with evidence
  - orphan branches/worktrees are either cleaned up or documented as blocked by active local changes
  - CI on `main` is green
  - dry-run readiness checks have passed
- Completion confirmation phrase for this workflow:
  - "Done merging PRs. CI passing. System hygiene complete. Ready for next session."

## Repository Hygiene

- Run `make check` before pushing and `make dry-run` before an operational change.
- Keep canonical source and small ledgers in Git; keep screenshots, caches, local databases, reports, and generated indexes out of Git.
- Every workflow needs a current owner and tested contract. Delete disabled one-off workflows.
- Optional integrations belong behind narrow adapters and core imports remain side-effect free.
- Reusable agent instructions live under `.agents/skills/`; human guidance lives in `README.md`, `CONTRIBUTING.md`, and `docs/`.

Never store secrets or tokens in this file.
