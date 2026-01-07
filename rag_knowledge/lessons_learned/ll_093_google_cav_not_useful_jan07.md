# Lesson Learned #093: Google Recommender CAV Not Useful for Trading

**Date**: January 7, 2026
**Severity**: INFO
**Category**: Research, Strategy Evaluation

## Summary

Evaluated Google's Recommender System breakthrough using Concept Activation Vectors (CAVs) for detecting semantic intent. Determined it is NOT useful for our trading system.

## Technical Analysis

### What Google's CAV Does
- Uses Concept Activation Vectors to interpret USERS (not models)
- Translates subjective "soft attributes" (funny, cute, boring) into vectors
- Personalizes content recommendations (YouTube, Google Discover)
- Tested on MovieLens20M dataset

### Why It's NOT Useful for Trading

| Google's CAV | Our Trading System |
|--------------|-------------------|
| Problem: "What does 'funny' mean to THIS user?" | Problem: "What is the CROWD saying about SPY?" |
| Goal: Personalize content to individuals | Goal: Aggregate market sentiment |
| Data: User interaction history | Data: Public posts, news |
| Output: Personalized recommendations | Output: Buy/Sell/Hold signals |

### Critical Mismatch
CAVs solve **personalization**. We need **aggregation**.

For market sentiment, we don't care if one user thinks "bullish" means slightly optimistic vs extremely positive. We care about **volume and direction** of crowd sentiment.

## Decision

**DO NOT IMPLEMENT** - Would add:
- Unnecessary complexity
- More failure points
- No material improvement to trading signals
- Violates CLAUDE.md: "100% operational security"

## What We Have (Appropriate)
- `src/utils/unified_sentiment.py` - Multi-source weighted aggregation
- Keyword-based sentiment with News (40%), Reddit (35%), YouTube (25%)
- This IS the right approach for market sentiment analysis

## CEO Validation
- CEO asked for honest assessment
- Answered: "This is FLUFF for our use case"
- CEO accepted the analysis

## Tags

research, google_cav, recommender_system, sentiment_analysis, strategy_evaluation, not_implemented
