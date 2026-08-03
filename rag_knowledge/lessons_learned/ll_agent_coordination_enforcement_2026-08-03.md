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

## Prevention

1. A local preflight requires an active issue, matching agent, exact Vault file scope,
   issue-key branch, and linked worktree before writes.
2. Foreign active claims are checked for file/directory overlap.
3. Worktree cleanup refuses primary, active, dirty, unknown, and unmerged targets.
4. GitHub validates issue/branch/base/worktree/file metadata without exposing Linear tokens.
5. Herdr startup and worktree events run a read-only reconciliation; transient pane state
   never closes a Linear issue.

## Verification requirement

Test positive claims plus negative controls for missing/inactive/wrong-agent claims,
unclaimed files, overlapping foreign work, spoofed Dependabot actors, malformed PR events,
legacy exceptions, active worktree deletion, dirty worktrees, and unmerged commits. Re-run
the live Linear/Vault/Herdr/GitHub audit after merge because all four surfaces can drift.

## Tags

#linear #obsidian #herdr #github #worktrees #coordination #ci
