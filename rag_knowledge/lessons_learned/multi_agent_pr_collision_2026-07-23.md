# LL-342: Check open/merged PRs before building a fix

**Date:** 2026-07-23
**Severity:** 3 (wasted a work cycle, no capital/data impact)

## What happened

Investigating "are we placing trades," I found `spy_put_credit` had an entry
path but no exit path (`check_exits()`/guardian both hard-require a 4-leg IC
shape and silently skip a 2-leg put-credit position). I built
`check_put_credit_exits()`, wired it into `ic-simple.yml`, added tests, and
opened PR #4257 — without first checking whether another in-flight PR already
covered it.

PR #4252 ("Replace failed IC entry system with evidence-gated put-credit
validation") had already merged to `main` with a more complete version:
`manage_put_credit_exits()` / `evaluate_put_credit_exit()` /
`_pending_exit_is_active()` (the last one I hadn't built), wired via
`--manage-exits`, plus `exit_reason` in `sync_closed_positions.py` and test
coverage in `tests/test_active_strategy.py`. My branch was stale relative to
`main` by 5 commits when I started; merging `origin/main` surfaced the
conflict and made the duplication obvious. PR #4257 was closed as superseded.

## Root cause

This repo has multiple agents (Claude, Codex, others) working the same
problem space concurrently via separate worktrees/branches. Local `git log`
and `data/runtime/strategy_kill_switch.json` told me *what* strategy is
active, but not *what other agents are actively fixing right now*.

## Prevention

Before implementing a fix for a gap found via code inspection:
1. `gh pr list --state open` first — check titles/bodies for topical overlap.
2. `git fetch --prune`, then inspect both `git worktree list` and
   `git branch -r --no-merged origin/main` — include remote in-flight work,
   not just local branches and merged commits.
3. If a candidate gap looks "obviously missing," search for the function name
   you're about to write against `origin/main` — a fresh check-in from another
   agent may have already landed it.

## How this surfaces again

If a new PR duplicates functionality already on `main` or in another open PR,
`git merge origin/main` on the feature branch will conflict or the function
names will already exist — that's the trigger to stop and check `gh pr list`
before continuing, not to force a merge resolution.
