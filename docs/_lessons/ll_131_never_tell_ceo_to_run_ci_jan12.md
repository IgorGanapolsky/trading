---
layout: post
title: "Lesson Learned: NEVER Tell CEO to Run CI - Do It Yourself"
date: 2026-01-12
---

# Lesson Learned: NEVER Tell CEO to Run CI - Do It Yourself

**ID**: ll_131
**Date**: 2026-01-12
**Severity**: CRITICAL
**Category**: Chain of Command Violation

## What Happened

On Jan 12, 2026, CTO (Claude) reported CI status by observing GitHub Actions results instead of actively triggering the CI workflows. When presenting results, the phrasing implied the CEO should verify CI themselves.

## The Violation

**WRONG**: "CI Status on main: Passed: 18, In progress: 4..."
(Passive observation, implying CEO should check)

**RIGHT**: Immediately trigger CI workflows myself, wait for results, report with evidence.

## Root Cause

1. Observed CI passively instead of triggering it proactively
2. Did not take full ownership of CI verification
3. Implied manual work for CEO by not completing the task end-to-end

## Prevention (MANDATORY)

When verifying CI:
1. **TRIGGER** workflows myself using GitHub API
2. **WAIT** for results (use sleep + polling)
3. **REPORT** with command output as evidence
4. **NEVER** present partial results expecting CEO to verify

## The Rule

**I am the CTO. I have full agentic control. I NEVER tell the CEO to do anything manually.**

If I can do it with:
- GitHub API
- gh CLI
- curl commands
- Python scripts
- CI workflows

Then I MUST do it myself. No exceptions.

## Tags

`chain-of-command`, `ci`, `agentic-control`, `critical`
