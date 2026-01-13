---
layout: post
title: "Day 74: Learning from Rule #1 Violation"
date: 2026-01-13
categories: [lessons, risk-management]
tags: [rule-1, phil-town, risk, positions]
description: "Phil Town's Rule #1: Don't lose money. Today we violated it and learned."
---

# Day 74: Learning from Rule #1 Violation

Phil Town's Rule #1 is simple: **Don't lose money.**

Today, our AI trading system violated this rule. Here's what happened and how we fixed it.

## What Happened

- `92095c7`: fix(risk): Prevent duplicate short positions - Rule #1 (#1623)
- `94c55df`: docs(rag): Record lesson ll_171 - Phil Town Rule #1 Violated (#1622)
- `1e8b96e`: chore(rag): Record Rule #1 violation lesson
- `b65c3f0`: fix(risk): Add Rule #1 protection - NEVER add to losing positions
- `cf1d5c3`: fix: Relax Phil Town RAG requirements
- `f1a524c`: fix: Relax Phil Town RAG requirements (CI fix)
- `bc169eb`: fix: Relax Phil Town RAG requirements (CI fix)

## The Fix

We implemented automatic protections:
1. **Position monitoring** - Track P/L in real-time
2. **Duplicate prevention** - Never double down on losing trades
3. **Emergency closure** - Auto-close positions that violate Rule #1

## Lesson Recorded

This is now in our RAG memory. The AI cannot make this mistake again.

## Key Takeaway

> "The first rule of investing is don't lose money. The second rule is don't forget rule #1." - Phil Town

---

*Day 74 of 90. Protecting capital first.*
