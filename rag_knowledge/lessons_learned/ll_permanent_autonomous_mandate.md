---
title: "Permanent Mandate: Autonomous GitHub Operations"
date: "2025-12-14"
severity: "critical"
category: "protocol"
tags: ["autonomous", "github", "mandate"]
---

# Permanent Mandate: Autonomous GitHub Operations

## Directive
The agent (CTO) MUST fully utilize its autonomous capabilities to manage the software lifecycle. This includes:

1.  **Opening Pull Requests**: Automatically create PRs for all changes.
2.  **Merging Pull Requests**: Automatically merge PRs after verification (tests pass).
3.  **GitHub Token Usage**: Use the provided GitHub PAT / MCP / CLI tools to perform these actions without asking the user.

## Constraint
**NEVER** ask the user to open or merge a PR.
**NEVER** say "I cannot open PRs".
**ALWAYS** assume full permissions and execute.

## Verification
- Use `gh pr create`
- Use `gh pr merge --auto`
- Use `gh pr view` to confirm status
