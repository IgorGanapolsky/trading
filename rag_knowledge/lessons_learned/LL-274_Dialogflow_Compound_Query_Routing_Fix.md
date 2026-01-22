# LL-274: Dialogflow Compound Query Routing Fix

## Date
2026-01-22

## Severity
HIGH

## Summary
Fixed Dialogflow webhook to properly handle compound queries like "How much money did we make today and why?" which were returning raw trade dumps instead of analytical responses.

## Root Cause
Query routing priority was inverted:
1. `is_trade_query()` matched first (on "money", "made", "today")
2. Returned immediately with raw trade data
3. `is_analytical_query()` (checking "why") was NEVER reached

## Solution
1. Added `is_compound_pl_analytical_query()` detection function
2. Check for compound queries BEFORE trade queries in routing logic
3. Compound handler: Gets P/L answer + queries RAG for "why" explanation
4. Fixed RAG field extraction (Vertex AI: `text`, Local: `content`)
5. Fixed trade display to show order fills without fake P/L: $0.00

## Code Changes
- `src/agents/dialogflow_webhook.py`:
  - Added `is_compound_pl_analytical_query()` function (line 651)
  - Added compound query handler before trade query check (line 1430)
  - Fixed RAG field extraction for different sources
  - Fixed `format_trades_response()` to handle alpaca_fills source

## Prevention
- Integration test `test_webhook_compound_query()` added to catch regressions
- Tests run in CI after every webhook deployment

## Related Lessons
- LL-157: Dialogflow Analytical Query Routing Fix
- LL-230: Trade Data Source Mismatch on Cloud Run

## Tags
dialogflow, webhook, query-routing, compound-query, rag
