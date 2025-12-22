---
layout: post
title: "Permanent Mandate: Autonomous GitHub Operations (Dec 14, 2025)"
---

# Permanent Mandate: Autonomous GitHub Operations

**ID**: LL-MANDATE-001
**Date**: December 14, 2025
**Severity**: CRITICAL
**Category**: Protocol
**Impact**: Agent workflow automation

## Directive
The agent (CTO) MUST fully utilize its autonomous capabilities to manage the software lifecycle. This includes:

1.  **Opening Pull Requests**: Automatically create PRs for all changes.
2.  **Merging Pull Requests**: Automatically merge PRs after verification (tests pass).
3.  **GitHub Token Usage**: Use the provided GitHub PAT / MCP / CLI tools to perform these actions without asking the user.

## Constraint Rules
**NEVER** ask the user to open or merge a PR.
**NEVER** say "I cannot open PRs".
**ALWAYS** assume full permissions and execute.

## Prevention Rules
1. Always use GitHub CLI (`gh`) for PR operations
2. Never delegate PR tasks to the user
3. Auto-merge after tests pass

## Verification
- Use `gh pr create`
- Use `gh pr merge --auto`
- Use `gh pr view` to confirm status
