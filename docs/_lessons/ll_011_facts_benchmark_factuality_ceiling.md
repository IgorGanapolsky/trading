---
layout: post
title: "Lesson Learned: FACTS Benchmark & 70% Factuality Ceiling"
date: 2025-12-11
---

# Lesson Learned: FACTS Benchmark & 70% Factuality Ceiling

**ID**: LL-011
**Impact**: Identified through automated analysis

**Date**: December 11, 2025
**Category**: LLM Safety, Verification
**Severity**: Medium
**Source**: Google DeepMind FACTS Benchmark (Dec 2025)

## Summary

Google DeepMind's FACTS Benchmark revealed that NO top LLM achieves >70% factuality:
- Gemini 3 Pro leads at 68.8%
- Claude models ~66-67%
- GPT-4o ~65.8%

This means ~30% of LLM claims may be hallucinations or inaccurate.

## Impact on Trading System

For a trading system relying on LLM Council decisions:
- 30% error rate on financial claims is unacceptable
- Could lead to wrong buy/sell signals
- Could misreport portfolio values, P/L, positions

## Root Cause

LLMs have fundamental factuality limitations:
- "Contextual factuality" - grounding in provided data
- "World knowledge factuality" - retrieving from memory/web
- Both have <70% accuracy ceiling

## Prevention Implemented

1. **FACTS Benchmark Weighting**: Weight LLM votes by their benchmark scores
2. **Ground Truth Validation**: Cross-check LLM signals against technical indicators (MACD, RSI, Volume)
3. **API Verification**: Always verify claims against Alpaca API before acting
4. **Hallucination Logging**: Track all discrepancies in RAG for pattern learning
5. **Factuality Ceiling**: Cap confidence scores at model's FACTS score

## Files Created/Modified

- `src/verification/factuality_monitor.py` - New factuality monitoring system
- `src/core/llm_council_integration.py` - Integrated FACTS weighting
- `tests/test_factuality_monitor.py` - Unit tests

## Key Takeaway

**LLMs advise, APIs decide.** Never trust LLM claims without ground truth verification.

## References

- [Google DeepMind FACTS Benchmark](https://deepmind.google/blog/facts-benchmark-suite)
- [VentureBeat Analysis](https://venturebeat.com/ai/the-70-factuality-ceiling-why-googles-new-facts-benchmark-is-a-wake-up-call)
