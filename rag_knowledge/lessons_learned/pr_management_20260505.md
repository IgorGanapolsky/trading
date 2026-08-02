# PR Management Lesson - 2026-05-05

## Context
- PR #3944 refreshed public North Star status after the IC exit-only rerun and was merged after CI, Public Surface Guard, CodeQL, GitGuardian, and Socket checks passed.
- Self-Healing Auto-Fix run 25385356135 created branch `auto/self-heal-25385356135` with import-format changes.
- PR #3945 was opened for that branch, but PR CI failed Trunk Check.

## Lesson
- Do not merge self-heal formatting branches just because the self-heal workflow reports success.
- Reproduce failed PR checks locally in a task worktree before deciding whether a branch is a merge candidate.
- If repo Trunk formatting reduces an auto-heal branch to zero net diff versus `main`, close the PR and delete the branch instead of merging churn.

## Evidence
- Local reproduction command: `trunk check --force ... --ci`
- Local fix command: `trunk fmt ...`
- Outcome: applying repo formatting made the self-heal branch equivalent to `main`.
- Cleanup: PR #3945 closed, run 25385540447 cancelled, branch `auto/self-heal-25385356135` deleted.
