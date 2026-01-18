---
layout: post
title: "Day 76: What We Learned - January 12, 2026"
date: 2026-01-12
day_number: 76
lessons_count: 7
critical_count: 1
excerpt: "Every mistake is a lesson in disguise. Today we uncovered a critical flaw in our system - the kind that separates amateur traders from professionals w..."
---

# Day 76 of 90 | Monday, January 12, 2026

**14 days remaining** in our journey to build a profitable AI trading system.

Every mistake is a lesson in disguise. Today we uncovered a critical flaw in our system - the kind that separates amateur traders from professionals who survive long-term.

---

## The Hard Lessons

*These are the moments that test us. Critical issues that demanded immediate attention.*

### API Key Environment Variable Mismatch

Trading system failed to execute for multiple days with "401 Unauthorized" errors.


## Important Discoveries

*Not emergencies, but insights that will shape how we trade going forward.*

### Stale Order Threshold Must Be 4 Hours, Not 24

System had $5K in paper account but hadn't traded in 6 days. Root cause: unfilled orders sitting for 24 hours consumed all buying power, blocking new trades.

### Comprehensive Investment Strategy Review - January 12, 2026

CEO requested comprehensive audit of all trading systems. CTO conducted thorough investigation with evidence-based answers to 15+ questions.


## Quick Wins & Refinements

- **Branch and PR Hygiene Protocol (LL-137)** - LL-137: Branch and PR Hygiene Protocol (LL-137)

Date: January 12, 2026
Category: DevOps / Git Workf...
- **Lesson Learned 133: Registry.py Missing Broke All Trading...** - During a system health check, discovered that `src/strategies/registry.py` was deleted in the NUCLEA...
- **NEVER Tell CEO to Run CI - Do It Yourself** - On Jan 12, 2026, CTO (Claude) reported CI status by observing GitHub Actions results instead of acti...
- **CTO Wrongly Assumed API Keys Were Invalid - January 12, 2026** - CTO (Claude) tested Alpaca API from sandbox environment and received "Access denied"....


---

## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **7** |
| Critical Issues | 1 |
| High Priority | 2 |
| Improvements | 4 |

---

## The Journey So Far

We're building an autonomous AI trading system that learns from every mistake. This isn't about getting rich quick - it's about building a system that can consistently generate income through disciplined options trading.

**Our approach:**
- Paper trade for 90 days to validate the strategy
- Document every lesson, every failure, every win
- Use AI (Claude) as CTO to automate and improve
- Follow Phil Town's Rule #1: Don't lose money

Want to follow along? Check out the [full project on GitHub](https://github.com/IgorGanapolsky/trading).

---

*Day 76/90 complete. 14 to go.*
