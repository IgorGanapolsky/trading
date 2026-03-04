---
layout: post
title: "North Star Operating Strategy: Fast, Gated, Coherent"
date: 2026-02-17 13:20:00 -0500
last_modified_at: "2026-02-17"
categories: [strategy, north-star, operations]
tags: [north-star, spy, iron-condor, rag, risk-management, alpaca]
description: "Canonical operating strategy: reach $6K/month after-tax using SPY iron condors, paper-first validation, and opportunistic execution."
excerpt: "Our operating strategy is now explicit and consistent across repo, dashboard, and judge demo: fastest safe path to $6K/month with strict RAG + risk gates."
---

## Canonical Strategy (Single Source of Truth)

- North Star: **$6K/month after-tax financial independence**
- Timing policy: **not calendar-constrained in execution**; reach the goal **as fast as safely possible**
- Core setup: **SPY iron condors**, **15-20 delta** short strikes, **$10-wide wings**, **up to 8 open option legs** (typically ~2 concurrent condors)

## Capital Allocation Policy

- **Paper account ($100K Alpaca)** is the primary validation engine.
- **Brokerage account** is traded opportunistically only when the same setup and gates pass:
  - strategy eligibility
  - risk policy checks
  - lessons-informed constraints from RAG

## Why This Matters

Coherence beats velocity theater. If the strategy text differs across repo, dashboard, and social channels, execution quality degrades. This update makes every primary surface align with one operating policy.

## Evidence Endpoints

- Judge demo: [/trading/lessons/judge-demo.html](/trading/lessons/judge-demo.html)
- RAG query: [/trading/rag-query/](/trading/rag-query/)
- Live status: [/trading/lessons/ops-status.html](/trading/lessons/ops-status.html)
