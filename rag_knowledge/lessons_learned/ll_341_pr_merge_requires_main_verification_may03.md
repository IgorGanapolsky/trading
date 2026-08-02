# LL-341: PR Merge Requires Current Main Verification

**ID**: LL-341
**Date**: 2026-05-03
**Severity**: HIGH
**Category**: PR hygiene, CI verification, agent behavior
**Status**: ACTIVE

## Incident Summary

During PR hygiene for ATH breakout work, PR #3903 was correctly merged and its PR checks were green. The agent then almost treated the PR as sufficient proof for the whole session. A later check showed current `main` had advanced and its latest CI push run was failing on a separate Trunk formatting issue.

## Evidence

- PR #3903 merged at `2026-05-03T12:39:41Z`.
- PR merge commit: `c9cd7936e66db9eb17b634269d5c1b18bded7c54`.
- PR `Run All Tests` passed on GitHub run `25279122858`, job `74113566912`.
- Current `main` later advanced to `1f7463b3f0bc33b957230da5a2343b8be1c73129`.
- Latest `main` CI push run `25284387286` failed in Trunk because `.claude/prd.json` was missing final formatting.
- Fix commit `b38e5f33335b1b76d464d990d58c6ae0a57c30c7` restored green `main` CI on run `25284829994` and green CodeQL on run `25284830000`.

## Root Cause

The agent conflated PR readiness with repository readiness. PR checks prove only the PR ref at that time. The completion phrase requires current `main` CI and local dry-run/readiness evidence after merges and after any subsequent automation commits.

## Prevention Rule

For PR-management sessions, do not claim completion after a PR merge until all of these are true:

1. `gh pr list --state open` is empty or every open PR is explicitly blocked with evidence.
2. `gh run list --branch main` shows current `origin/main` CI and CodeQL green for the latest main SHA.
3. The merged PR changes are present on `origin/main`, either by ancestry or file-level/squash-merge verification.
4. Local readiness dry-run has executed and its result is reported truthfully, including safe blocking outcomes.
5. Task-created worktrees and branches are removed; pre-existing dirty worktrees are documented, not modified.

## Operator Trust Rule

When the user asks "did you finish everything?", answer no unless every required gate is already proven. If only a PR is done, say "the PR is done; the full session is not done yet" and continue verifying.
