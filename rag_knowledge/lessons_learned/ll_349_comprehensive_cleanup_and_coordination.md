# LL-349: Comprehensive cleanup needs durable ownership and post-merge re-audits

**Date:** 2026-08-02

**Severity:** HIGH (4)

**Category:** repository hygiene, multi-agent coordination, CI truth

## What happened

A whole-repository cleanup overlapped two other agents' documentation and audit work. A competing audit merged while this branch was active, and a later Herdr-style documentation PR moved `main` again. Merging current `main` also reintroduced generated `graphify-out/` content that had already been classified as disposable.

The cleanup additionally found a README-advertised lessons query command that did not exist, a stale coverage threshold for a zero-caller iron-condor option-chain module, five weak fingerprint hashes, a yanked dependency lock entry, and CI workflows whose schedules outlived their code owners.

## Coordination rule

Use four layers with different responsibilities:

1. **Linear issue** is the durable task owner.
2. **Shared Obsidian vault claim** records live WIP and touched-file scope.
3. **Herdr** exposes transient pane and agent lifecycle; it is not a durable lock.
4. **Issue-scoped worktree and PR** are the authoritative code record.

An agent visible as `done` in Herdr disappeared before the next `agent get`, which directly demonstrates why terminal presence cannot replace an issue lock. The Obsidian Linear plugin is useful as a human dashboard but cannot arbitrate concurrent writes.

## Cleanup rule

- Re-run the hygiene scanner after every rebase or merge; generated artifacts can return through the new base.
- Prove dead code with repository-wide caller and workflow searches before deletion.
- Keep one canonical skill tree (`skills/`), one docs hub, and one contributor contract.
- Treat generated reports, indexes, screenshots, logs, caches, and runtime databases as rebuildable outputs.
- If documentation advertises a command, enforce the command with a contract test.

## Verification rule

- Compare coverage only when source scopes match. The old 63.445% report covered a smaller source set; it cannot be presented as a regression against combined `src + scripts` branch coverage.
- A passing targeted test is not a passing full suite, and a local suite is not green GitHub CI.
- RAG reliability means query plus isolated read/write proof; file presence alone is insufficient.
- Dry runs prove planning and safety boundaries, not order submission, fills, live capital, or profit.
- Claim judges must keep foreign-agent text out of the current claim's risk/evidence corpus, redact matched credential material, and test every supported agent identity. A concurrent merge violated all three rules until the post-merge audit caught it.

## Mistakes and prevention

- A task worktree was removed and had to be reconstructed. Never delete a worktree without checking its branch, owner, dirtiness, and recovery path.
- A diagnostic shell loop used zsh's reserved `path` variable and failed read-only. Use task-specific variable names in shell diagnostics.
- The first secret scan traversed local caches and was needlessly slow. Scope security scans to repository candidates and report only finding types and paths, never values.
- A double-quoted PR body allowed Markdown backticks to execute as shell command substitution and polluted the draft description with Git help text. Use an `apply_patch`-created body file with `gh pr edit --body-file`; verify the rendered body before relying on it.

## Tags

#hygiene #linear #obsidian #herdr #worktrees #coverage #rag #ci
