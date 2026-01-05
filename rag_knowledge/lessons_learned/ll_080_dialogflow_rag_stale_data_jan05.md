# Lesson Learned #080: Dialogflow RAG Returning Stale Lessons

**ID**: ll_080
**Date**: January 5, 2026
**Severity**: HIGH - Trust violation with CEO
**Category**: RAG, Vector Database, Dialogflow

## Problem Statement

CEO asked Dialogflow agent "What was the last date and time of your lesson?" and the agent returned lessons from **December 11, 2025** when lessons exist up to **January 5, 2026**.

## Root Cause Analysis

1. **Semantic search mismatch**: The query "last date and time of your lesson" was being matched semantically to lessons containing words like "date", "time", "lesson" - NOT the most recent lessons by date.

2. **No recency-aware query**: The RAG system had no endpoint to return lessons sorted by date. It only supported semantic similarity search.

3. **Date extraction not implemented**: Lessons have dates in their filenames (e.g., `ll_079_hallucination_jan05.md`) but no system extracted and indexed these dates.

## Evidence

```bash
# Query for "last date" returns Dec 11 lessons (wrong)
curl -s "https://webhook/test?query=What+was+the+last+date"
# Returns: ci_failure_blocked_trading (Dec 11, 2025)

# But lessons from Jan 5 exist
curl -s "https://webhook/test?query=ll_079+hallucination+january"
# Returns: ll_079_hallucination_tomorrow_incident_jan05 (Jan 5, 2026)
```

## The Fix

1. Added `/recent` endpoint that:
   - Extracts dates from lesson IDs (pattern: `dec12`, `jan05`, etc.)
   - Falls back to parsing `**Date**: December 11, 2025` from content
   - Returns lessons sorted by date descending

2. Redeployed webhook with fix

## Verification

After fix, `/recent` endpoint returns:
```json
{
  "recent_lessons": [
    {"id": "ll_079_hallucination_jan05", "date": "2026-01-05"},
    {"id": "ll_074_hook_ambiguity_jan5", "date": "2026-01-05"},
    {"id": "ll_073_options_theta_dec30", "date": "2025-12-30"}
  ]
}
```

## Prevention Rules

1. **RAG systems must support recency queries** - not just semantic similarity
2. **Test RAG with temporal queries** - "recent", "last", "today's", "this week's"
3. **Extract and index dates** from all knowledge base entries
4. **Verify before claiming** - run `curl /recent` to check actual recency

## Files Changed

- `src/agents/dialogflow_webhook.py` - Added `/recent` endpoint
- `tests/test_dialogflow_webhook_recent.py` - 22 unit tests
- `rag_knowledge/lessons_learned/ll_080_dialogflow_rag_stale_data_jan05.md` - This lesson

## Tags

`rag`, `dialogflow`, `recency`, `semantic_search`, `date_extraction`, `trust_violation`
