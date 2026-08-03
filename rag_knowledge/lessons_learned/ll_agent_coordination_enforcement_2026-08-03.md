# LL-350: Coordination documents need executable collision guards

**Date:** 2026-08-03

**Severity:** HIGH (4)

**Category:** multi-agent coordination, repository hygiene, CI truth

## Incident

Linear, the shared Obsidian Vault, Herdr, and GitHub had a correct documented role split,
but no repository gate enforced the lifecycle. Herdr showed multiple agents in the primary
checkout while the trading Linear claim was Backlog. Two verification worktrees disappeared
during concurrent cleanup, and a new PR plus new RAG worktrees appeared without issue-key
branches tied to current Vault claims.

A diagnostic loop also reused zsh's reserved `path` variable, which removed `git` from the
command lookup for the rest of that loop. Shell diagnostics must use task-specific variable
names such as `worktree_dir`.

Runtime testing found three additional failure modes. A live-agent audit invoked from a
linked worktree ignored agents in the primary checkout, and its parent-first path match
could shadow a nested `.worktrees/<issue>` checkout. The fix reconciles against every
registered worktree and selects the deepest matching path. A Trunk monitor started from one
worktree also reformatted 81 unrelated files in another; stop the worktree-specific daemon
before restoring only the proven formatter diff from the index. Finally, a fresh `pip-audit`
found three advisories because `uv.lock` lagged the already-updated direct constraints; lock
consistency and vulnerability checks must run together.

## Prevention

1. A local preflight requires an active issue, matching agent, exact Vault file scope,
   issue-key branch, and linked worktree before writes.
2. Foreign active claims are checked for file/directory overlap.
3. Worktree cleanup refuses primary, active, dirty, unknown, and unmerged targets.
4. GitHub validates issue/branch/base/worktree/file metadata without exposing Linear tokens.
5. Herdr startup and worktree events run a read-only reconciliation; transient pane state
   never closes a Linear issue.
6. Squash-merged worktrees are removable only when `git cherry origin/main HEAD` marks every
   remaining patch equivalent; a different commit SHA alone is not proof of unique work.
7. Stop per-worktree formatter daemons before cross-worktree cleanup and verify the target
   file hash remains stable across the test run.

## Verification requirement

Test positive claims plus negative controls for missing/inactive/wrong-agent claims,
unclaimed files, overlapping foreign work, spoofed Dependabot actors, malformed PR events,
legacy exceptions, active worktree deletion, dirty worktrees, and unmerged commits. Re-run
the live Linear/Vault/Herdr/GitHub audit after merge because all four surfaces can drift.
Require 100% statement and branch coverage for the new deterministic coordination core,
plus `uv lock --check`, `pip-audit`, and the full repository regression suite.

## Tags

#linear #obsidian #herdr #github #worktrees #coordination #ci
