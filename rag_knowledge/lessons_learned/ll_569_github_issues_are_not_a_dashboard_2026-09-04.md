# LL-569: GitHub Issues is not a paper-ops dashboard

**Date**: 2026-09-04
**Severity**: HIGH (4)
**Category**: CI / operator hygiene

## What Happened

The Issues board kept filling with bot cards after hygiene closed them:

- `verify-trade-execution.yml` opened `Trade Execution Failed` on every
  weekday with a flat paper book (dry-run, regime skip, or no fill).
- `north-star-blocker-watch.yml` and `weekly-health-digest.yml` upserted
  living dashboard issues, so close → next cron recreate.
- `self-healing-monitor.yml` filed UNHEALTHY issues on rolling checks.

## Lesson

No-fill on paper validation is not a GitHub bug. Dashboards belong in
Actions artifacts, not the Issues inbox.

## Prevention

Those four workflows no longer have `issues: write`. Guard:
`tests/test_workflow_issue_spam_guard.py`.
