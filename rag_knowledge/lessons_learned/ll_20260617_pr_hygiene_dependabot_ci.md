# LL-20260617: PR Hygiene Dependabot CI and Orphan Branch Cleanup

**ID**: LL-20260617
**Date**: 2026-06-17
**Severity**: PROCESS
**Category**: PR hygiene, CI verification, branch cleanup
**Status**: ACTIVE

## Context

During PR-management hygiene, 11 open Dependabot PRs were inspected and all were updated against current `main`.
No PR was merge-ready after update because required checks were still failing or pending.

## Evidence

- Open PR count: 11.
- Remote non-main branch count before orphan cleanup: 19.
- Remote orphan branches deleted: 8 `chore/openrouter-pricing-baseline-*` branches.
- Remote orphan branch count after cleanup: 0.
- Latest `main` SHA checked: `ea4fda241`.
- Latest `main` CI evidence: CI, Main Head Verification, CodeQL, SonarCloud, OpenSSF Scorecard, and no-direct-submit-order were green on `ea4fda241`.
- Local clean-main dry run: `python3 scripts/system_health_check.py` passed.
- Trading readiness remained intentionally blocked: `TRADING_HALTED` present, weekly gate in quarantine, and new risk-on entries blocked.

## Lessons

1. Do not merge Dependabot PRs until updated-branch checks complete and required CI is green.
2. If many Dependabot PRs fail Trunk immediately after update, treat them as blocked, not merge-ready, until logs are available from completed workflow runs.
3. Orphan auto-baseline branches without PRs can be deleted when their only diff is generated baseline churn and no PR references them.
4. Dirty local worktrees and branches with uncommitted changes must be documented, not deleted.
5. Chat-provided GitHub tokens are action-time credentials only and must not be written to directives, RAG, logs, or commits.

## Tags

pr-management, branch-hygiene, dependabot, ci-verification, rag, secrets
