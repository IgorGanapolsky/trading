# LL-568: Rogue GitHub Actions Cron Issue Spam and Outdated Repo Metadata

**Date**: 2026-09-04
**Severity**: MEDIUM-HIGH (3)
**Category**: CI/CD hygiene / Repository metadata / Automation guardrails

## What Happened

1. **Issue Spam (130+ Issues)**:
   - A daily cron workflow `.github/workflows/openrouter-price-monitor.yml` scheduled at 6am ET attempted to run `gh pr create` with the default GitHub Actions `GITHUB_TOKEN`.
   - Actions lacked workflow permissions to create PRs, causing `gh pr create` to fail.
   - The workflow script fallback logic executed `gh issue create` upon PR failure, spawning 76+ duplicate issue cards on the repo board and pushing 18 orphan `origin/chore/openrouter-pricing-baseline-*` branches.
2. **Outdated Repo "About" Section**:
   - The repo GitHub "About" description was outdated referencing an old real-money control plane, defunct "$1k/mo" target, broken GitHub Pages URL, and obsolete `iron-condor` topic tag.
   - The ground truth is paper validation on SPY put-credits with a $6,000/mo after-tax target and broker-backed ledgers.

## Resolution & Evidence

1. **Purged Issue Spam**: Closed 76 duplicate OpenRouter pricing baseline issues and 14 stale issues using `gh issue close`, reducing open issues from 130 to 9.
2. **Pruned Remote Branches**: Deleted 18 orphan `origin/chore/openrouter-pricing-baseline-*` branches.
3. **Workflow Deleted (PR #4472)**: Deleted `.github/workflows/openrouter-price-monitor.yml` via isolated worktree PR #4472 with full CI checks passing (`Run All Tests`, `Validate Workflows`, `CodeQL`, `Trunk Check`).
4. **Repo Metadata Ground Truth Synchronized**:
   - Updated description to: `SPY put-credit paper validation lab with broker-backed ledgers, deterministic risk gates, hybrid RAG, reconciliation, and $6k/mo after-tax target tracking.`
   - Removed dead website URL and killed `iron-condor` topic.
   - Preserved accurate topics: `algorithmic-trading`, `alpaca-api`, `automated-trading`, `options-trading`, `paper-trading`, `python`, `quantitative-finance`, `spy-etf`, `trading-bot`.
5. **Broker Reconciliation**: Verified 2 open paper SPY put-credit positions on Alpaca with broker inventory verified (`residual_ics=0`, `pcs_legs=4`, `unresolved=0`).

## Prevention & Operating Rules

- Never use fallback `gh issue create` in cron jobs when a PR creation fails; crons must fail cleanly or notify structured logging without polluting the issue tracker.
- Obsolete monitoring crons outside active operating scope must be deleted promptly per `CLAUDE.md`.
- Maintain repository "About", homepage URL, and topic metadata in sync with active operating truth.
