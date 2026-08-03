# Agent coordination

This repository uses one shared coordination path across coding agents. It deliberately
separates task ownership, live claims, and code review instead of asking one tool to do all
three jobs.

| Surface                | Authoritative for                       | Not authoritative for        |
| ---------------------- | --------------------------------------- | ---------------------------- |
| Linear                 | issue scope, assignee, status, blockers | touched files or merge state |
| Shared Obsidian vault  | live claim note and agent state         | code review or CI            |
| Git worktree and PR    | changed files, review, CI, merge SHA    | task assignment              |
| Obsidian Linear plugin | human-readable issue dashboard          | locking or agent leases      |

The bridge lives in the shared coordination repository and writes the matching Linear and
vault records atomically enough for normal agent handoff. Do not copy it into this repo or
add another task database.

## Required lifecycle

From the shared coordination repository:

```bash
node tools/linear-agent-bridge.js --list --json
node tools/linear-agent-bridge.js --claim IGO-123 --agent codex --json
```

Then:

1. Create one worktree from current `origin/main`.
2. Name the branch with the issue key, such as `fix/igo-123-short-description`.
3. Record exact intended files in the Vault claim, not merely the repository name.
4. Run the local fail-closed check before writing:

   ```bash
   make coordination-preflight
   ```

5. Put the issue key, agent, base SHA, worktree, and intended files in the PR template.
6. Update the Linear issue when scope, blockers, or evidence changes.
7. After merge, attach the PR, merge SHA, CI result, and protected-system checks, then mark
   the issue done through the bridge. Release the claim if the work is abandoned.

## Enforcement surfaces

- `scripts/agent_coordination.py preflight` validates the active Vault claim, agent,
  issue-key branch, linked worktree, exact file scope, and foreign-claim overlaps.
- `.claude/hooks/agent_coordination_guard.sh` blocks mutating Bash commands outside that
  contract. Edit/Write hooks apply the same check to the target file.
- `.github/workflows/agent-coordination.yml` validates issue/branch/PR metadata without
  requiring Linear credentials in CI. Dependabot is narrowly exempt when both its actor
  and branch identify Dependabot.
- The `trading.coordination` Herdr plugin audits pane/worktree lifecycle against durable
  claims. Herdr state is diagnostic and never marks a Linear issue done.
- `scripts/worktree_hygiene.sh` is the only supported removal path. It refuses active,
  dirty, unmerged, unknown, and primary worktrees.

Run a full read-only reconciliation at any time:

```bash
make coordination-audit
```

## Collision rule

Before writing, compare the issue list, vault claims, worktree inventory, open PRs, and
intended file scope. If any active work overlaps, stop edits and reconcile on the Linear
issue. Never delete, rename, reset, or reuse another agent's worktree or branch.

Older PRs that predate enforcement may temporarily carry the `coordination-legacy` label,
but their body must state a concrete `Coordination legacy reason`. The exception is visible,
reviewable, and must not be used for new work.

## Evidence rule

A claim is not completion. A local test is not CI. A PR is not a merge. Record these as
separate evidence surfaces, and never infer trading execution or profitability from any of
them.
