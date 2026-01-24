# LL-303: PR Management and System Hygiene Protocol

**ID**: LL-303
**Date**: 2026-01-24
**Severity**: PROCESS
**Category**: Development Operations
**Status**: DOCUMENTED

## Context
During Ralph Mode iteration 18, executed comprehensive PR management and system hygiene protocol as CTO.

## Actions Taken

### 1. PR Review and Management
- **PR #2922**: Closed (state: dirty/conflicts from stale branch)
- **PR #2923**: Created and merged (SHA: `fa603fb`)
  - ML trade gate integration
  - Thompson Sampling confidence scoring
  - 16 new tests

### 2. Branch Cleanup
| Before | After |
|--------|-------|
| 2 remote claude/* branches | 0 remote |
| 5 local claude/* branches | 0 local |

Deleted stale branches:
- claude/fix-dialogflow-rag-query-8VWfA
- claude/investigate-gcp-charges-8VWfA
- claude/rl-staleness-improvements-8VWfA
- claude/tax-strategy-planning-Fc73z
- claude/vertex-ai-cost-optimize-8VWfA

### 3. Git Rebase Conflict Resolution
When rebasing on main, encountered conflicts in:
- `models/ml/feedback_model.json` (timestamp conflicts)
- `data/system_state.json` (auto-sync conflicts)

**Resolution strategy**:
- For key commits (ML integration): Resolve conflict manually
- For state updates: Skip (`git rebase --skip`) as they're auto-synced

## Key Learnings

### 1. Stale PRs with Conflicts
PRs marked as "dirty" have merge conflicts. Options:
- Rebase branch on main, resolve conflicts, force push
- Close PR if changes are obsolete

### 2. Auto-Sync Causes Conflicts
System state files (`system_state.json`, `feedback_model.json`) are auto-synced by hooks, causing frequent conflicts during rebases.

**Best practice**: Skip state update commits during rebase; the auto-sync will repopulate on next session.

### 3. GitHub API for PR Management
```bash
# Check open PRs
curl -s -H "Authorization: token $PAT" \
  "https://api.github.com/repos/OWNER/REPO/pulls?state=open"

# Merge PR
curl -s -X PUT -H "Authorization: token $PAT" \
  "https://api.github.com/repos/OWNER/REPO/pulls/NUMBER/merge" \
  -d '{"merge_method": "squash"}'

# Delete branch
curl -s -X DELETE -H "Authorization: token $PAT" \
  "https://api.github.com/repos/OWNER/REPO/git/refs/heads/BRANCH"
```

## Verification Commands
```bash
# Check CI status on main
curl -s -H "Authorization: token $PAT" \
  "https://api.github.com/repos/OWNER/REPO/actions/runs?branch=main&per_page=5"

# List remote branches
git branch -r | grep claude/

# Prune stale refs
git remote prune origin
```

## Tags
pr-management, git, system-hygiene, devops, cleanup
