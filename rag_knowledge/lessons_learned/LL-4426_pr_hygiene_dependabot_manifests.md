# LL-4426 PR hygiene: Dependabot blocked by tracked generated manifests

## Context

PR management session. 16 open PRs: 10 Dependabot + 1 mergeable feature (#4391) + 5 conflicting stale.

## Findings

1. Dependabot PRs (#4400–4408, #4376/#4378) failed required **Run All Tests** because
   `audit_repository_hygiene.py --check` reported tracked generated paths:
   - `data/audit/arxiv_ingestion_manifest.json`
   - `data/audit/ingestion_version_manifest.json`
     Main tip after untrack fix: hygiene **errors=0**. Rebase Dependabot onto current main.
2. Required checks for main (branch protection): Detect Changed Paths, Run All Tests, Validate Workflows.
   SonarCloud Code Analysis can fail without blocking merge.
3. **required_conversation_resolution** blocks merge when Codex review threads are open —
   resolve after addressing (or honest decline), do not admin-merge past them.
4. #4391 entry cadence: rebased onto main, fixed Codex P2s (validation_phase filter, validation closes only, NYSE holidays).
5. Openrouter pricing baseline remote branches (14) were pure noise — deleted.
6. Worktrees: removed 7 clean merged/detached/noise; left dirty WIP owned by other sessions.

## Actions that worked

- `@dependabot rebase` on all failing dep PRs after hygiene fix on main
- Force-with-lease rebase of #4391 content onto main tip
- GraphQL `resolveReviewThread` after code fixes
- Worktree remove only when `git status --porcelain` empty

## Mistakes / rails

- First dry-run without Keychain Alpaca env → false credential failure. Load paper keychain before dry-run claims.
- Do not claim "Done merging PRs" while required Run All Tests still pending.

## Operational note

`audit_open_inventory.py clean=True` can disagree with `spy_put_credit` UNCLEAN_INVENTORY reconstruction —
investigate before new entries; concurrent full book may still block.
