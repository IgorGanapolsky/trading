---
layout: post
title: "Building a Memory System for AI Trading: Vertex AI RAG"
date: 2025-12-15
categories: [technical, ai]
tags: [rag, vertex-ai, memory, lessons-learned]
description: "How we built a memory system that lets our AI trading bot learn from every mistake using Vertex AI RAG."
---

# Why Your AI Trading Bot Needs Memory

Most trading bots are stateless. They make the same mistakes over and over.

We built something different: a memory system that ensures our AI never repeats a mistake.

## The Problem with Stateless Bots

Traditional trading bots:
- Don't remember past trades
- Can't learn from losses
- Repeat the same errors
- Have no institutional knowledge

Every day is Day 1.

## Our Solution: Bidirectional RAG

RAG = Retrieval-Augmented Generation

We use Vertex AI to create a two-way learning loop:

### READ Phase (Before Trading)
```
1. Query RAG: "What lessons apply to SOFI puts?"
2. Retrieve: Past mistakes, successful patterns, risk warnings
3. Apply: Adjust trade parameters based on lessons
```

### WRITE Phase (After Trading)
```
1. Record: Trade outcome, what worked, what didn't
2. Analyze: Extract lesson if pattern detected
3. Store: Add to RAG for future queries
```

## How It Works in Practice

**Scenario**: AI suggests selling SPY puts

**RAG Query**:
```python
lessons = rag.query("SPY options trading mistakes")
```

**RAG Response**:
```
LL-148: SPY requires $58K collateral per contract.
With $5K account, SPY trades are impossible.
Prevention: Check collateral before suggesting trade.
```

**AI Decision**: Reject SPY, suggest SOFI instead.

## The Technical Architecture

```
┌─────────────────────────────────────────┐
│           BEFORE TRADE (READ)           │
├─────────────────────────────────────────┤
│ 1. Query Vertex AI RAG for lessons      │
│ 2. Check for CRITICAL/HIGH warnings     │
│ 3. Block trade if relevant lesson found │
└─────────────────────────────────────────┘
                    ↓
           [TRADE EXECUTED]
                    ↓
┌─────────────────────────────────────────┐
│           AFTER TRADE (WRITE)           │
├─────────────────────────────────────────┤
│ 1. Record outcome to RAG                │
│ 2. Extract pattern if loss occurred     │
│ 3. Create lesson for future prevention  │
└─────────────────────────────────────────┘
```

## What We Store

Each lesson contains:
- **ID**: Unique identifier (e.g., LL-148)
- **Severity**: CRITICAL, HIGH, MEDIUM, LOW
- **Category**: Trading, Technical, Process
- **Root Cause**: What went wrong
- **Prevention**: How to avoid in future

## Results After 45 Days

- **Lessons recorded**: 16
- **Mistakes prevented**: 8 (that we know of)
- **False positives**: 2 (lessons too broad)

The system is literally getting smarter every day.

## Code Sample

```python
from src.rag.vertex_rag import VertexRAG

rag = VertexRAG()

# Before trade
lessons = rag.query(f"{ticker} trading mistakes", top_k=5)
critical = [l for l in lessons if l.severity == "CRITICAL"]

if critical:
    logger.warning(f"BLOCKED: {critical[0].title}")
    return None  # Don't trade

# After trade
if trade.pnl < 0:
    rag.record_lesson(
        title=f"Loss on {ticker}: {trade.reason}",
        severity="HIGH",
        prevention="..."
    )
```

## Why Vertex AI?

We evaluated several options:
- **ChromaDB**: Removed (too complex for our needs)
- **Pinecone**: Expensive at scale
- **Vertex AI RAG**: Native GCP integration, semantic search, managed

Vertex AI won because we're already on GCP for trading infrastructure.

## The Key Insight

**Memory is a competitive advantage.**

A trading bot that learns from every trade will eventually outperform one that doesn't. It's just math.

Our bot made the SPY mistake once. It will never make it again.

---

*Our RAG system documented in LL-139, LL-149. [See all lessons](/trading/lessons/)*
