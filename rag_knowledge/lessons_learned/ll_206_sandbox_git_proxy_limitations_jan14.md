# Lesson Learned: Sandbox Git Proxy Limitations

**ID**: ll_206
**Date**: 2026-01-14
**Category**: Infrastructure
**Severity**: MEDIUM

## Context
During Ralph Mode autonomous operations, discovered that the web sandbox git proxy creates ephemeral branches that do not persist commits across push operations.

## Problem
- Commits pushed through sandbox proxy may not sync to actual GitHub PR
- Each push operation shows "new branch" even after previous pushes
- PR #1837 was closed without merging because commits didn't sync

## Solution
1. All local changes are preserved in the working directory
2. Changes can be committed via GitHub Actions CI job (create-pr workflow)
3. Direct API calls can create PRs when sandbox is limited

## Prevention
1. Document sandbox limitations clearly
2. Use CI jobs for critical git operations when possible
3. Verify commits actually appear on GitHub after pushing

## Related
- Sandbox environment reminder in hooks
- CLAUDE.md operational security section
