# LL-660 — github-actions[bot] cannot approve its own auto PR

**Date:** 2026-09-18  
**Severity:** 4  
**Issue:** AGENT-659  
**Evidence:** PR #4805 job `Agent PR required review` failed:
`GraphQL: Review Can not approve your own pull request`

## Mistake

#4804 made `chore/auto-*` PRs run the required-review job so they are not
SKIPPED. The job still called `gh pr review --approve` with `GITHUB_TOKEN`
(the same bot that opened the PR). Required check went red; owner approve
alone did not green the job.

## Fix

If this HEAD already has any APPROVED review, exit 0. If the PR author is
`github-actions[bot]`, do not self-approve; exit 0 and leave CODEOWNERS
review to a human.

File: `.github/workflows/dependency-review.yml`
