# Lesson Learned #132: RAG Stuck on December 2025 Content (CRISIS)

**ID**: LL-132
**Date**: January 11, 2026
**Severity**: CRITICAL
**Category**: RAG, Operational Failure, Trust Breach

## What Happened

CEO tested Vertex AI RAG via Dialogflow and it returned OLD December 2025 incident reports instead of useful current trading guidance. The RAG thought we were in December 11th, 2025.

## Root Cause

1. **No recency filtering**: RAG search scored content by keyword match only
2. **Old incidents matched keywords**: Dec 2025 lessons had words like "trading", "CI", "failure"
3. **No actionable content**: RAG lacked current trading rules document
4. **Semantic search trap**: Old verbose incident reports ranked higher than new concise content

## Impact

- CEO lost trust in the system
- RAG was useless for decision support
- System appeared broken and outdated

## Fix Applied

1. **Added `trading_rules_2026.md`**: Actionable trading guidance document
2. **Added recency boosting to RAG scoring**:
   - 4x boost: `trading_rules` and `2026` in filename
   - 3x boost: Last 3 days (jan09, jan10, jan11)
   - 2x boost: January 2026 content
   - 0.3x penalty: Old December 2025 incidents

## PRs Merged

- PR #1418: Added trading_rules_2026.md
- PR #1419: Added recency boost to RAG scoring

## Prevention Measures

1. **Test RAG queries after every deployment**
2. **Add date-based filtering as default**
3. **Prioritize actionable content over incident reports**
4. **Regular RAG quality audits (weekly)**

## Lesson

RAG systems need RECENCY AWARENESS. Semantic search alone isn't enough - newer content should score higher for current operations.

## Tags

`rag`, `operational-failure`, `trust-breach`, `crisis`, `recency-bias`
