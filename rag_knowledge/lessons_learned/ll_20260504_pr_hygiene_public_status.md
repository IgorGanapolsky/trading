# Lesson Learned: PR Hygiene And Public Status Drift

Date: 2026-05-04
Severity: HIGH
Area: PR management, public status generation, automation hygiene

## What Happened

Public status validation stayed fragile after the first ledger-clean fix because
`scripts/daily_scorecard.py` can refresh the paired closed-trade ledger as a
side effect. Restoring `data/trades.json` before public-surface generation was
not enough when scorecard generation ran after the restore.

Several automation branches also appeared during cleanup. Some were legitimate
merge candidates, while stale self-heal branches were based on older `main`
SHAs and would have reverted newer generated state if promoted blindly.

## Evidence Pattern

- If `scripts/build_public_status.py --check` fails after a successful sync,
  compare committed `data/trades.json` timestamps with committed public status
  timestamps. A newer public status timestamp can prove it was built from
  transient, uncommitted ledger state.
- When GitHub PR merge succeeds but local cleanup fails, check whether the local
  branch is attached to a worktree. Remove the worktree before deleting the
  branch.
- Before promoting an `origin/auto/*` branch, verify its merge base against
  current `origin/main`. A branch from an older main head can be stale even if
  its workflow concluded successfully.

## Required Behavior

- Keep Sync Alpaca public surfaces ledger-clean after every step that may touch
  `data/trades.json`, including scorecard generation.
- Treat no-PR automation branches as one of: merge candidate, stale cleanup
  candidate, or blocked active work. Do not delete or merge without evidence.
- Prefer the current-main PR path for useful generated state, and delete stale
  auto branches that would revert newer main content.
- Do not claim system hygiene complete until `main` is pulled, local public
  status check passes, current-head CI is green, open PRs are empty, and branch
  and worktree inventories are clean.
