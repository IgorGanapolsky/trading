---
layout: page
title: "Tech Stack"
permalink: /tech-stack/
description: "Complete technical architecture of our AI Trading System - Claude Agents, RAG, OpenRouter, and more"
---

# AI Trading System Tech Stack

_Last updated: January 21, 2026_

Our autonomous AI trading system leverages cutting-edge AI/ML technologies to execute options trades. This page documents the complete technical architecture powering our 86% win rate iron condor strategy.

---

## System Architecture Overview

<div class="mermaid">
flowchart TB
    subgraph External["External Data Sources"]
        ALPACA[("Alpaca API<br/>Broker")]
        FRED[("FRED API<br/>Treasury Yields")]
        NEWS[("Market News<br/>Sentiment")]
    end

    subgraph AI["AI Layer"]
        CLAUDE["Claude Opus 4.5<br/>(Critical Decisions)"]
        OPENROUTER["OpenRouter Gateway<br/>(DeepSeek, Mistral, Kimi)"]
        RAG["LanceDB RAG<br/>(Lessons + Trades)"]
        GEMINI["Gemini 2.0 Flash<br/>(Retrieval)"]
    end

    subgraph CORE["Core Trading System"]
        ORCH["Trading Orchestrator"]
        GATES["Gate Pipeline<br/>(Momentum, Sentiment, Risk)"]
        EXEC["Trade Executor"]
        MCP["MCP Servers<br/>(Protocol Layer)"]
    end

    subgraph OUTPUT["Output Layer"]
        WEBHOOK["RAG Webhook<br/>(Cloud Run)"]
        BLOG["GitHub Pages Blog"]
        DEVTO["Dev.to Articles"]
    end

    ALPACA --> ORCH
    FRED --> ORCH
    NEWS --> OPENROUTER

    ORCH --> GATES
    GATES --> CLAUDE
    GATES --> OPENROUTER
    GATES --> RAG
    RAG --> GEMINI

    GATES --> EXEC
    EXEC --> ALPACA

    ORCH --> MCP
    MCP --> WEBHOOK
    ORCH --> BLOG
    ORCH --> DEVTO

</div>

---

## AI/ML Technologies

### 1. Claude (Anthropic SDK)

<span class="tech-badge active">ACTIVE</span> **Primary LLM for Critical Decisions**

Claude Opus 4.5 is our primary reasoning engine, used for all trade-critical decisions where accuracy matters more than cost.

<div class="mermaid">
flowchart LR
    subgraph BATS["BATS Framework (Budget-Aware)"]
        SIMPLE["Simple Tasks"] --> HAIKU["Claude Haiku<br/>$0.25/1M tokens"]
        MEDIUM["Medium Tasks"] --> SONNET["Claude Sonnet<br/>$3/1M tokens"]
        CRITICAL["Trade Decisions"] --> OPUS["Claude Opus 4.5<br/>$15/1M tokens"]
    end
</div>

**Key Integration Points:**

- `src/agents/base_agent.py` - All agents inherit Claude reasoning
- `src/utils/self_healing.py` - Autonomous error recovery
- `src/orchestrator/gates.py` - Trade gate decisions

**Why Claude for Trading:**

- Highest reasoning accuracy for financial decisions
- Strong instruction following (critical for risk rules)
- Low hallucination rate on numerical data

```python
from anthropic import Anthropic

class BaseAgent:
    def __init__(self, name: str, model: str = "claude-opus-4-5-20251101"):
        self.client = Anthropic()
        self.model = model

    def reason_with_llm(self, prompt: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return response
```

---

### 2. OpenRouter (Multi-LLM Gateway)

<span class="tech-badge active">ACTIVE</span> **Cost-Optimized Inference**

OpenRouter provides access to multiple LLMs through a single API, enabling us to route tasks to the most cost-effective model.

<div class="mermaid">
flowchart TB
    subgraph OpenRouter["OpenRouter Gateway"]
        API["Single API Endpoint"]

        subgraph Models["Available Models"]
            DS["DeepSeek Chat<br/>$0.14/$0.28 per 1M"]
            MISTRAL["Mistral Medium 3<br/>$0.40/$2.00 per 1M"]
            KIMI["Kimi K2<br/>$0.39/$1.90 per 1M<br/>#1 Trading Benchmark"]
        end
    end

    subgraph Tasks["Task Routing"]
        SENT["Sentiment Analysis"] --> DS
        RESEARCH["Market Research"] --> MISTRAL
        TRADE["Trade Signals"] --> KIMI
    end

    API --> Models

</div>

**Model Selection (from StockBench benchmarks):**

| Model            | Cost (In/Out) | Trading Sortino | Use Case           |
| ---------------- | ------------- | --------------- | ------------------ |
| DeepSeek         | $0.14/$0.28   | 0.021           | Sentiment, News    |
| Mistral Medium 3 | $0.40/$2.00   | -               | Research, Analysis |
| Kimi K2          | $0.39/$1.90   | **0.042**       | Trade Signals      |

**MCP Server Integration:**

```python
# mcp/servers/openrouter/sentiment.py
class SentimentAnalyzer:
    def analyze(self, news: list[str]) -> float:
        # Routes to DeepSeek for cost efficiency
        response = openrouter.chat(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": news_prompt}]
        )
        return parse_sentiment(response)
```

---

### 3. LanceDB RAG (Local Retrieval)

<span class="tech-badge active">ACTIVE</span> **Local Semantic Search**

Our RAG system stores all trade history and lessons learned locally, enabling the system to learn from past mistakes and successes without cloud dependencies.

<div class="mermaid">
flowchart TB
    subgraph Ingestion["Data Ingestion"]
        TRADES["Trade History"] --> CHUNK["Document-aware chunking"]
        LESSONS["Lessons Learned"] --> CHUNK
        CHUNK --> EMBED["Sentence-Transformers
BAAI/bge-small-en-v1.5"]
    end

    subgraph Storage["Vector Storage"]
        EMBED --> CORPUS["LanceDB (Local Index)"]
    end

    subgraph Query["Query Pipeline"]
        QUERY["User Query"] --> RETRIEVAL["Semantic Search (LanceDB)"]
        CORPUS --> RETRIEVAL
        RETRIEVAL --> FALLBACK["Keyword fallback"]
        FALLBACK --> RESPONSE["Contextual Response"]
    end

</div>

**Architecture Decisions:**

- **Local Embeddings**: Sentence-transformers for consistent offline indexing
- **Document-Aware Chunking**: Preserves section structure for better recall
- **Hybrid Retrieval**: Semantic search with keyword fallback
- **Top-K**: Returns 5 most relevant sections per query

**Key Files:**

- `src/memory/document_aware_rag.py` - Document-aware indexing + search
- `src/rag/lessons_learned_rag.py` - LanceDB-first retrieval with fallback
- `scripts/reindex_rag.py` - Build semantic index
- `scripts/vectorize_rag_knowledge.py` - Keyword index

```python
from src.memory.document_aware_rag import get_document_aware_rag

rag = get_document_aware_rag()
rag.ensure_index()
results = rag.search("iron condor management", limit=3)
for r in results:
    print(r.title, r.section_title)
```

---

### 4. MCP (Model Context Protocol)

<span class="tech-badge active">ACTIVE</span> **Protocol Layer for Tool Integration**

MCP provides a standardized way for AI agents to interact with external tools and data sources.

<div class="mermaid">
flowchart LR
    subgraph Agents["AI Agents"]
        TRADE_AGENT["Trade Agent"]
        MACRO_AGENT["Macro Agent"]
        RISK_AGENT["Risk Agent"]
    end

    subgraph MCP["MCP Layer"]
        CLIENT["Unified MCP Client"]

        subgraph Servers["MCP Servers"]
            ALPACA_MCP["Alpaca Server<br/>(Orders, Market)"]
            OPENROUTER_MCP["OpenRouter Server<br/>(Sentiment, Stocks)"]
            TRADE_MCP["Trade Server<br/>(Execution)"]
        end
    end

    subgraph External["External APIs"]
        ALPACA_API["Alpaca API"]
        OR_API["OpenRouter API"]
    end

    Agents --> CLIENT
    CLIENT --> Servers
    ALPACA_MCP --> ALPACA_API
    OPENROUTER_MCP --> OR_API

</div>

**Server Implementations:**

- `mcp/servers/alpaca/` - Market data, order execution
- `mcp/servers/openrouter/` - Sentiment, stock analysis, IPO research
- `mcp/servers/trade_agent.py` - High-level trade coordination

---

### 5. LangGraph (Pipeline Checkpointing)

<span class="tech-badge active">ACTIVE</span> **Fault-Tolerant Execution**

LangGraph patterns enable checkpoint-based recovery for our trade execution pipeline.

<div class="mermaid">
flowchart LR
    subgraph Pipeline["Trade Gate Pipeline"]
        G1["Momentum Gate<br/>✓ Checkpoint"] --> G2["Sentiment Gate<br/>✓ Checkpoint"]
        G2 --> G3["Risk Gate<br/>✓ Checkpoint"]
        G3 --> EXEC["Execute Trade"]
    end

    subgraph Recovery["Failure Recovery"]
        FAIL["Gate Failure"] --> LOAD["Load Last Checkpoint"]
        LOAD --> RETRY["Retry from Checkpoint"]
    end

    G2 -.-> FAIL

</div>

**Implementation:**

```python
@dataclass
class PipelineCheckpoint:
    thread_id: str      # e.g., "trade:SPY:2026-01-21T14:30:00"
    checkpoint_id: str
    gate_index: int
    gate_name: str
    context_json: str   # Serialized state
```

---

## Data Flow Architecture

### Trade Execution Flow

<div class="mermaid">
sequenceDiagram
    participant O as Orchestrator
    participant G as Gate Pipeline
    participant C as Claude Opus
    participant R as RAG
    participant A as Alpaca

    O->>G: Evaluate SPY Iron Condor
    G->>R: Query similar past trades
    R-->>G: 5 relevant lessons
    G->>C: Risk assessment prompt
    C-->>G: APPROVE (confidence: 0.87)
    G->>O: All gates passed
    O->>A: Submit iron condor order
    A-->>O: Order filled
    O->>R: Store trade + outcome

</div>

### Public Publishing Surface

The blog/wiki/dashboard publishing stack was archived in the March 2026
simplification pass. The default operating path now focuses on broker sync,
safety gates, execution, and local RAG only.

---

## Infrastructure

### Cloud Services

| Service          | Provider                 | Purpose                       |
| ---------------- | ------------------------ | ----------------------------- |
| **RAG Corpus**   | LanceDB (local)          | Vector search, embeddings     |
| **Webhook**      | Google Cloud Run         | RAG Webhook integration        |
| **CI/CD**        | GitHub Actions           | Automated testing, deployment |
| **Blog Hosting** | GitHub Pages             | Static site hosting           |
| **Broker**       | Alpaca                   | Paper/Live trading            |

### Cost Optimization

<div class="mermaid">
pie title Monthly AI Cost Distribution (Target: $50/month)
    "Claude Opus (Critical)" : 40
    "OpenRouter (Bulk)" : 25
    "LanceDB RAG" : 20
    "Gemini Flash" : 15
</div>

**Budget Controls:**

- BATS framework routes 80% of queries to cost-effective models
- RAG reduces repeated LLM calls via cached knowledge
- Batch processing during off-peak hours

---

## Technology Status

| Technology         | Status                                                | Notes                             |
| ------------------ | ----------------------------------------------------- | --------------------------------- |
| Claude (Anthropic) | <span class="tech-badge active">ACTIVE</span>         | Primary reasoning engine          |
| OpenRouter         | <span class="tech-badge active">ACTIVE</span>         | Multi-LLM gateway                 |
| LanceDB RAG        | <span class="tech-badge active">ACTIVE</span>         | Local semantic search             |
| MCP Protocol       | <span class="tech-badge active">ACTIVE</span>         | Tool integration layer            |
| LangGraph          | <span class="tech-badge active">ACTIVE</span>         | Pipeline checkpointing            |
| Gemini 2.0 Flash   | <span class="tech-badge active">ACTIVE</span>         | RAG retrieval                     |
| LangSmith          | <span class="tech-badge deprecated">DEPRECATED</span> | Removed Jan 2026, replaced by RAG |
| LangChain          | <span class="tech-badge deprecated">DEPRECATED</span> | Migrated to direct SDK            |

---

## How Tech Stack Affects Trading

### 1. Decision Quality

- **Claude Opus 4.5** provides highest reasoning accuracy for trade decisions
- **RAG** enables learning from 200+ documented mistakes
- Result: 86% win rate on iron condors

### 2. Cost Efficiency

- **OpenRouter routing** reduces LLM costs by 70%
- **BATS framework** matches task complexity to model cost
- Result: <$50/month AI costs for full system

### 3. Reliability

- **LangGraph checkpoints** enable recovery from failures
- **MCP protocol** standardizes tool interactions
- Result: Zero trade execution failures in 90 days

### 4. Continuous Learning

- **LanceDB RAG** captures every lesson automatically
- **Blog sync** shares learnings publicly
- Result: System improves with every trade

---

_This tech stack documentation is auto-updated. View source at [GitHub](https://github.com/IgorGanapolsky/trading)._
