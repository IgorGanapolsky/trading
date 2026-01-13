# LL-157: Dialogflow Analytical Query Routing Fix

**Date:** 2026-01-13
**Severity:** HIGH
**Category:** Dialogflow, Query Routing, User Experience

## Problem

When users asked analytical questions like "Why did we not make money yesterday in paper trades?", the Dialogflow webhook was returning generic portfolio status instead of actually analyzing and answering the WHY question.

**Root Cause:** The `is_trade_query()` function detected keywords like "money", "trades", "paper" and routed these to the trade handler, which showed portfolio status when no trades were found - ignoring the analytical nature of the question.

## Solution

Added `is_analytical_query()` function to detect analytical/causal questions:
- WHY questions: "why", "how come"
- Explanation requests: "explain", "tell me about"
- Analysis requests: "in detail", "what happened", "what went wrong"
- Causal investigation: "reason", "cause", "analyze"

Updated webhook routing logic:
1. Readiness queries -> Readiness assessment
2. Trade queries with trades found -> Trade history
3. **Trade queries + analytical -> RAG semantic search** (NEW)
4. Trade queries without trades -> Portfolio status
5. Everything else -> RAG search

## Prevention

- Always consider the INTENT of user queries, not just keyword matching
- Analytical questions need semantic understanding, not data lookups
- Test with real user questions before deploying

## Code Reference

`src/agents/dialogflow_webhook.py:307` - `is_analytical_query()` function
`src/agents/dialogflow_webhook.py:933-1005` - Routing logic for analytical queries

## Tests Added

`tests/test_dialogflow_webhook.py:1072` - `TestAnalyticalQueryDetection` class
- 5 test methods covering WHY, explain, in-detail, negative cases, case insensitivity
