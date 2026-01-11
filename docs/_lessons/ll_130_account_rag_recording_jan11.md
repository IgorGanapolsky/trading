---
layout: post
title: "Lesson Learned #130: Account Balance RAG Recording Failure"
date: 2026-01-11
---

# Lesson Learned #130: Account Balance RAG Recording Failure

**Date**: January 11, 2026
**Category**: Operational Integrity
**Severity**: CRITICAL

## Context

CEO asked: "What makes you say we have thirty dollars? Are you hallucinating?"

CTO had claimed $30 brokerage balance based on stale local data that was 4+ days old.

## The Failure

1. **RAG had NO account balance records** - We had lessons ABOUT needing fresh data, but no actual balance history
2. **Sandbox cannot reach Alpaca API** - Network restrictions prevent live verification
3. **CI workflows weren't recording balances to RAG** - Only updating local JSON files
4. **CTO couldn't verify the actual balance** - Had to admit uncertainty

## Impact

- CEO lost trust in reported values
- CTO could not answer: "What is our actual account balance?"
- Violated mandate: "Record every single trade in Vertex AI RAG"

## Fix Applied

1. Created `scripts/record_account_to_rag.py` - Records live balances to RAG
2. Added mandatory step to `daily-trading.yml` - Runs automatically
3. Created `rag_knowledge/account_history/` directory - Dedicated location

## Prevention

- ALWAYS record account balances in RAG (not just local files)
- CI must sync balances daily
- Never trust calculated estimates - verify with source of truth
- If data is stale, say "I cannot verify"

## Key Lesson

**When you don't know something, say "I don't know" instead of making claims based on stale data.**
