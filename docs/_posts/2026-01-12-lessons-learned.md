---
layout: post
title: "Day 76: 6 Lessons Learned - January 12, 2026"
date: 2026-01-12
day_number: 76
lessons_count: 6
critical_count: 0
---

# Day 76/90 - Monday, January 12, 2026

## Summary

| Metric | Count |
|--------|-------|
| Total Lessons | 6 |
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 2 |
| LOW | 2 |

---

## Lessons Learned

### [HIGH] LL-144: Stale Order Threshold Must Be 4 Hours, Not 24

**ID**: `ll_144_stale_order_threshold_fix_jan12`

# LL-144: Stale Order Threshold Must Be 4 Hours, Not 24  **ID**: ll_144 **Date**: 2026-01-12 **Severity**: HIGH **PR**: #1523  ## Problem System had $5K in paper account but hadn't traded in 6 days. Root cause: unfilled orders sitting for 24 hours consumed all buying power, blocking new trades.  ##...


### [HIGH] LL-135: Comprehensive Investment Strategy Review - January 12, 2026

**ID**: `ll_135_investment_strategy_comprehensive_review_jan12`

# LL-135: Comprehensive Investment Strategy Review - January 12, 2026  **ID**: ll_135 **Date**: 2026-01-12 **Severity**: HIGH **Category**: Strategy Audit  ## Summary  CEO requested comprehensive audit of all trading systems. CTO conducted thorough investigation with evidence-based answers to 15+ qu...


### [LOW] LL-133: Lesson Learned 133: Registry.py Missing Broke All Trading Strategies

**ID**: `ll_133_registry_fix_and_hygiene_jan12`

# LL-133: Lesson Learned #133: Registry.py Missing Broke All Trading Strategies  **Date:** January 12, 2026 **Author:** CTO Claude **Category:** Critical Bug Fix **Severity:** P0 - System Breaking  ## Incident  During a system health check, discovered that `src/strategies/registry.py` was deleted in...


### [LOW] LL-163: CTO Wrongly Assumed API Keys Were Invalid - January 12, 2026

**ID**: `ll_163_sandbox_vs_github_api_access_jan12`

# LL-163: CTO Wrongly Assumed API Keys Were Invalid - January 12, 2026  ## Incident Summary - **Date**: January 12, 2026 - **Severity**: P2 - CTO ERROR (not system error) - **Impact**: Caused unnecessary confusion for CEO  ## What Happened  CTO (Claude) tested Alpaca API from sandbox environment and...


### [MEDIUM] LL-137: Branch and PR Hygiene Protocol (LL-137)

**ID**: `ll_137_branch_and_pr_hygiene_jan12`

# LL-137: Branch and PR Hygiene Protocol (LL-137)  **Date**: January 12, 2026 **Category**: DevOps / Git Workflow **Severity**: Medium  ## Context CEO requested full branch and PR cleanup. Found 4 stale branches that were diverged from main.  ## Discovery - Branch `claude/fix-github-pages-lessons-EY...


### [MEDIUM] LL-131: NEVER Tell CEO to Run CI - Do It Yourself

**ID**: `ll_131_never_tell_ceo_to_run_ci_jan12`

# LL-131: NEVER Tell CEO to Run CI - Do It Yourself  **ID**: ll_131 **Date**: 2026-01-12 **Severity**: MEDIUM **Category**: Chain of Command Violation  ## What Happened  On Jan 12, 2026, CTO (Claude) reported CI status by observing GitHub Actions results instead of actively triggering the CI workflo...


---

*Auto-generated from RAG knowledge base | [View Source](https://github.com/IgorGanapolsky/trading)*
