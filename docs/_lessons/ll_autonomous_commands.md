---
layout: post
title: "---"
date: 2026-01-10
---

---
title: "Lesson: Always Execute Commands Autonomously"
date: "2025-12-12"
severity: "high"
tags: ["autonomous", "protocol", "error-correction"]
---

# Lesson: Always Execute Commands Autonomously

**ID**: LL-AUTO-001
**Impact**: Identified through automated analysis

## Context
The agent (CTO) asked the user (CEO) to run a command manually (`streamlit run dashboard/trading_dashboard.py`) to verify a fix. This violates the core directive that the autonomous agent should execute all necessary commands itself.

## Decision
**Mistake**: Delegating manual execution to the user.
**Correction**: The agent must run all verification commands, scripts, and fixes itself. The user should only be notified of the *results*, not asked to perform the work.

## Prevention
1.  **Never Suggest Commands**: Do not output "Run X to verify". Instead, run X and report "I ran X and verified Y".
2.  **Autonomous Mindset**: Treat the user as a supervisor who reviews *outcomes*, not a worker who executes *tasks*.
3.  **Self-Correction**: If a tool is needed (e.g., verifying a UI), finding a way to verify it programmatically (syntax check, unit test, curl request) or running it in the background is preferred over asking the user.
