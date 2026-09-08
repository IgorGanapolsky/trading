# LL-585 — Dependabot auto-merge waits on Run All Tests; vault NFF needs worktree rail (2026-09-08)

## Context
PR hygiene after Scorecard/Dependabot batch. #4505 merged (29a2bb059). #4500-#4504 APPROVED + auto-merge stayed BLOCKED until required Run All Tests finished (SonarCloud pending is non-required). Tip main after #4505 showed only pages/deploy check-runs — not the required matrix.

## Mistakes / rails
1. Do not claim tip-main CI green from pages build/deploy alone. Required: Detect Changed Paths, Run All Tests, Validate Workflows, CodeQL, Dependency Review.
2. Primary-checkout destructive sync commands are hook-denied — use an origin/main worktree plus scripts/worktree_hygiene.sh.
3. Vault pull --rebase with 1000+ local ahead commits conflicts on Agent-State/grok.md. Rail: detached worktree from origin/main, add only grok-owned handoff paths, push that commit.
4. Empty commit via Git Data API cannot PATCH refs/heads/main under PR-required rules — and empty PRs fail coordination metadata (#4509 closed).
5. make dry-run exit 2 with regime_gate_blocked (IVR < 30) is expected readiness, not a broken dry-run path. Health can still be ALL CHECKS PASSED.
6. New RAG lesson IDs must be unique — duplicate LL-572 broke audit_repository_hygiene and blocked all Dependabot rebuilds after #4511.

## Prevention
- Hygiene completion phrase gated on Dependabot MERGED (or required-fail evidence) + tip required checks + vault push + dry-run/health evidence.
- Scorecard residuals are not GitHub Issues (never_opens_github_issues).
- Before writing ll_NNN_*.md, list existing NNN on main.
