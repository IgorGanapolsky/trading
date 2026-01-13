# LL-139: Vertex AI Strategic Deployment Assessment

**Date**: January 12, 2026
**Category**: Architecture
**Severity**: INFO

## Summary

Evaluated Vertex AI "Secrets of Strategic Deployment" video recommendations against our trading system. Determined that Model Garden, Agent Builder, and Vertex AI Studio features would add complexity without operational benefit for our use case.

## Key Findings

### What We Already Have (Lean & Effective)
- Vertex AI RAG with text-embedding-004 (semantic search)
- Gemini 2.0 Flash for LLM sentiment
- Local keyword-based fallback (LessonsSearch)
- 952 LOC total for RAG modules

### Video Suggestions NOT Adopted
1. **Model Garden browsing** - Already picked our model
2. **Vertex AI Studio prompt tuning** - Direct API calls work
3. **Agent Builder** - Trading needs deterministic rules, not autonomous agents
4. **ADK (Agent Development Kit)** - Overkill for function calls

### Real Vulnerabilities Fixed
1. **RAG Lesson Fallback Gap**: Added local CRITICAL lesson check when Vertex AI unavailable
2. **Sentiment Gate SKIP Behavior**: Changed to REJECT on LLM failure (conservative)

## Prevention

Before adopting new cloud features:
1. Audit current implementation for actual gaps
2. Prioritize operational resilience over feature adoption
3. Fix real vulnerabilities before adding complexity
4. Follow Rule #1: Don't lose money (conservative defaults)

## Code Changes
- `src/orchestrator/gates.py`: RAGPreTradeQuery fallback + Gate3Sentiment conservative reject
