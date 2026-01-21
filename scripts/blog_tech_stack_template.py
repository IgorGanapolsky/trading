#!/usr/bin/env python3
"""
Tech Stack Template for Blog Posts.

Provides reusable tech stack sections with architecture diagrams
for daily reports, lesson posts, and Dev.to articles.
"""

# =============================================================================
# MAIN SYSTEM ARCHITECTURE DIAGRAM (Mermaid)
# =============================================================================

SYSTEM_ARCHITECTURE_MERMAID = """
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
        RAG["Vertex AI RAG<br/>(Lessons + Trades)"]
        GEMINI["Gemini 2.0 Flash<br/>(Retrieval)"]
    end

    subgraph CORE["Core Trading System"]
        ORCH["Trading Orchestrator"]
        GATES["Gate Pipeline<br/>(Momentum, Sentiment, Risk)"]
        EXEC["Trade Executor"]
        MCP["MCP Servers<br/>(Protocol Layer)"]
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
</div>
"""

# =============================================================================
# TRADE PIPELINE DIAGRAM (Mermaid)
# =============================================================================

TRADE_PIPELINE_MERMAID = """
<div class="mermaid">
flowchart LR
    subgraph Today["Today's Pipeline"]
        DATA["Market Data<br/>(Alpaca)"] --> GATES["Gate Pipeline"]
        GATES --> CLAUDE["Claude Opus 4.5<br/>(Risk Decision)"]
        GATES --> RAG["Vertex AI RAG<br/>(Past Lessons)"]
        CLAUDE --> EXEC["Trade Execution"]
        RAG --> CLAUDE
    end
</div>
"""

# =============================================================================
# LEARNING PIPELINE DIAGRAM (Mermaid)
# =============================================================================

LEARNING_PIPELINE_MERMAID = """
<div class="mermaid">
flowchart LR
    subgraph Learning["Learning Pipeline"]
        ERROR["Error/Insight<br/>Detected"] --> CLAUDE["Claude Opus<br/>(Analysis)"]
        CLAUDE --> RAG["Vertex AI RAG<br/>(Storage)"]
        RAG --> BLOG["GitHub Pages<br/>(Publishing)"]
        BLOG --> DEVTO["Dev.to<br/>(Distribution)"]
    end
</div>
"""

# =============================================================================
# TECH STACK TABLES
# =============================================================================

TECH_STACK_TABLE_TRADING = """
| Component | Technology | Role |
|-----------|------------|------|
| **Decision Engine** | Claude Opus 4.5 | Final trade approval, risk assessment |
| **Cost-Optimized LLM** | OpenRouter (DeepSeek/Kimi) | Sentiment analysis, market research |
| **Knowledge Base** | Vertex AI RAG | Query 200+ lessons learned |
| **Retrieval** | Gemini 2.0 Flash | Semantic search over trade history |
| **Broker** | Alpaca API | Paper trading execution |
| **Data** | FRED API | Treasury yields, macro indicators |
"""

TECH_STACK_TABLE_LEARNING = """
| Component | Role in Learning |
|-----------|------------------|
| **Claude Opus 4.5** | Analyzes errors, extracts insights, determines severity |
| **Vertex AI RAG** | Stores lessons with 768D embeddings for semantic search |
| **Gemini 2.0 Flash** | Retrieves relevant past lessons before new trades |
| **OpenRouter (DeepSeek)** | Cost-effective sentiment analysis and research |
"""

TECH_STACK_LIST_DEVTO = """
- **Claude Opus 4.5** - Primary reasoning engine for trade decisions
- **OpenRouter** - Cost-optimized LLM gateway (DeepSeek, Mistral, Kimi)
- **Vertex AI RAG** - Cloud semantic search with 768D embeddings
- **Gemini 2.0 Flash** - Retrieval-augmented generation
- **MCP Protocol** - Standardized tool integration layer
"""

# =============================================================================
# FULL SECTION GENERATORS
# =============================================================================


def generate_tech_stack_section_trading() -> str:
    """Generate tech stack section for daily trading reports."""
    return f"""
## Tech Stack in Action

Today's trading decisions were powered by our AI stack:

{TRADE_PIPELINE_MERMAID}

### Technologies Used Today

{TECH_STACK_TABLE_TRADING}

### How It Works

1. **Market Data Ingestion**: Alpaca streams real-time quotes and positions
2. **Gate Pipeline**: Sequential checks (Momentum -> Sentiment -> Risk)
3. **RAG Query**: System retrieves similar past trades and lessons
4. **Claude Decision**: Final approval with full context (86% accuracy)
5. **Execution**: Order submitted to Alpaca if all gates pass

*[Full Tech Stack Documentation](/trading/tech-stack/)*
"""


def generate_tech_stack_section_learning() -> str:
    """Generate tech stack section for lesson posts."""
    return f"""
## Tech Stack Behind the Lessons

Every lesson we learn is captured, analyzed, and stored by our AI infrastructure:

{LEARNING_PIPELINE_MERMAID}

### How We Learn Autonomously

{TECH_STACK_TABLE_LEARNING}

### Why This Matters

1. **No Lesson Lost**: Every insight persists in our RAG corpus
2. **Contextual Recall**: Before each trade, we query similar past situations
3. **Continuous Improvement**: 200+ lessons shape every decision
4. **Transparent Journey**: All learnings published publicly

*[Full Tech Stack Documentation](/trading/tech-stack/)*
"""


def generate_tech_stack_section_devto() -> str:
    """Generate tech stack section for Dev.to (no Mermaid diagrams)."""
    return f"""
## Tech Stack Behind the Scenes

Our AI trading system uses:
{TECH_STACK_LIST_DEVTO}

Every lesson is stored in our RAG corpus, enabling the system to learn from past mistakes and improve continuously.

*[Full Tech Stack Documentation](https://igorganapolsky.github.io/trading/tech-stack/)*
"""


def generate_tech_stack_section_mini() -> str:
    """Generate minimal tech stack mention for short posts."""
    return """
---

*Powered by Claude Opus 4.5, Vertex AI RAG, and OpenRouter. [See our full tech stack](/trading/tech-stack/).*
"""


# =============================================================================
# MAIN - For testing
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TECH STACK TEMPLATE TEST")
    print("=" * 70)

    print("\n--- Trading Section ---")
    print(generate_tech_stack_section_trading()[:500] + "...")

    print("\n--- Learning Section ---")
    print(generate_tech_stack_section_learning()[:500] + "...")

    print("\n--- Dev.to Section ---")
    print(generate_tech_stack_section_devto())

    print("\n--- Mini Section ---")
    print(generate_tech_stack_section_mini())

    print("\n" + "=" * 70)
    print("All templates working!")
    print("=" * 70)
