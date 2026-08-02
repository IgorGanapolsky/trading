# LL-231: Failure Analysis - Why Critical Fixes Were Lost (Jan 16, 2026)

## Incident Summary

The critical spread width fix (issue #1957) was **LOST** because:

1. Branch was deleted before PR was merged
2. Issue was closed without verification
3. No one verified the fix actually landed in main

## Failures Identified

### 1. Premature Issue Closure

- Issues closed when work "started", not when "verified complete"
- No proof required before marking done

### 2. Lost Branches

- Automated cleanup deleted branches
- No check if PR was merged first

### 3. "Claiming Done" Pattern

- Claude instances said "fixed" without verification
- No evidence-based confirmation

### 4. No Cross-Verification

- Workflow failures silently accumulated
- Trading system not executing but issues just logged

## Root Cause

**Lack of verification loops.** Every claim of completion should require:

1. Show the PR number
2. Verify PR is merged (state = MERGED)
3. Verify fix is in main branch
4. Only then close the issue

## Prevention Rules

### Before Claiming "Done":

1. `gh pr view <PR> --json state` → must show MERGED
2. `gh api contents/<file>` → must show the fix in main
3. Screenshot or command output as proof

### Before Closing Issues:

1. Link to merged PR
2. Verify PR references the issue (FIXES #XXX)
3. Confirm fix visible in main branch

### Before Deleting Branches:

1. Check PR state first
2. Never delete if PR is still open

## Action Items

- [ ] Add verification step to all Claude workflows
- [ ] Update CLAUDE.md with verification requirements
- [ ] Create post-merge verification workflow
