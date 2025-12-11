# AI Agent Coordination Research - December 2025

**Research Date**: December 11, 2025
**Focus Areas**: Multi-agent coordination, context optimization, RAG for codebases, machine-readable documentation, semantic code organization

---

## Executive Summary

This research identifies emerging standards and best practices for AI agent coordination in codebases as of December 2025. Key findings include:

1. **Multi-Agent Coordination**: Git worktrees + specialized agent roles enable true parallel development
2. **Context Optimization**: KV-cache optimization provides 10x cost reduction; context engineering is "the runtime of AI agents"
3. **Codebase RAG**: AST parsing + embeddings + knowledge graphs achieve 3x better retrieval than any single method
4. **Documentation Standards**: llms.txt specification adopted by Cloudflare, Anthropic, Perplexity for AI-readable docs
5. **Semantic Organization**: Tree-sitter AST parsing + semantic embeddings enable meaning-based code search

---

## 1. Multi-Agent Coordination Patterns

### Core Coordination Architectures

#### **Orchestrator-Worker Pattern** (Anthropic, Microsoft)
- **Lead agent** coordinates strategy and spawns specialized subagents
- **Subagents** operate in parallel on different aspects
- **Benefits**: Clear hierarchy, efficient delegation, parallel execution
- **Implementation**: Microsoft Agent Framework, Anthropic's research system

#### **Sequential and Concurrent Patterns** (AutoGen)
- **Sequential**: Linear pipeline where each agent processes previous output
- **Concurrent**: Agents work in parallel on independent tasks
- **Benefits**: Simple coordination, predictable flow
- **Implementation**: AutoGen framework with flexible routing

#### **Swarm Pattern** (Decentralized)
- **Peer agents** work together, exchanging information directly
- **No central controller**: Coordination is emergent, not managed
- **Benefits**: Resilient, scalable, adaptive to complex problems
- **Implementation**: Inspired by swarm intelligence in nature

#### **Hierarchical Multi-Agent** (AgentOrchestra)
- **Two-tier architecture**: Top-level planning agent + domain-specific sub-agents
- **Flexible composition**: Modular agents can be composed dynamically
- **Benefits**: Scalability, domain specialization, robust adaptation
- **Implementation**: AgentOrchestra framework

#### **Group Chat Orchestration**
- **Shared conversation thread**: Multiple agents collaborate through discussion
- **Chat manager**: Coordinates flow, determines response order
- **Benefits**: Natural collaboration, validation through discussion
- **Implementation**: AutoGen, CrewAI

### Git Worktrees for Multi-Agent Development

**Critical Pattern**: Multiple AI agents working on same repository simultaneously.

#### **Why Worktrees Matter**
```bash
# Create worktree for feature branch
git worktree add ../trading-feature-name -b claude/feature-name

# Each worktree = isolated working directory
# Multiple Claude instances can work independently
# No branch switching conflicts
# Each agent maintains deep context about its task
```

#### **Real-World Usage**
- Developers running **5+ worktrees** in large monorepos
- Each worktree has its own Claude Code instance
- Independent tasks: component updates, refactoring, docs, performance
- **No interference**: Each agent works at full speed without waiting

#### **Tools & Orchestration**
- **ccswarm**: Rust-native multi-agent orchestration with Git worktree isolation
- **gwq**: Git worktree manager with status dashboard and tmux session management
- **Best Practice**: Create worktrees under `.trees/{TASK_ID}` directory

#### **Benefits for AI Workflows**
1. **Independent testing**: Run tests in one tree while developing in another
2. **Dedicated context**: Each Claude instance maintains task-specific context
3. **No confusion**: AI agents don't mix up different features
4. **Specialized focus**: Each agent becomes expert in assigned task

### Key Challenges

1. **Context and data sharing**: Agents must exchange information accurately without duplication or loss
2. **Scalability and fault tolerance**: Handle complex interactions while recovering from failures
3. **Infrastructure design**: "Scaling multi-agent systems isn't a prompt engineering problem—it's an infrastructure design problem"
4. **Observability**: Treat agents like distributed systems—observable, composable, compliant

### Framework Landscape (2025)

- **Microsoft Agent Framework**: Enterprise-grade, supports Agent2Agent (A2A) protocol, MCP integration
- **AutoGen**: Adaptive agents with flexible routing, asynchronous communication
- **CrewAI**: Role-based design, each agent has defined role and skills
- **LangGraph**: State-based agent orchestration with graph structure

---

## 2. Context Window Optimization Techniques

### Core Principle
> "Context engineering is the art and science of filling the context window with just the right information at each step of an agent's trajectory." - LangChain

> "Most agent failures are not model failures anymore, they are context failures." - Industry CEO

### Critical Optimization: KV-Cache Hit Rate

**Most Important Metric**: KV-cache hit rate directly affects both latency and cost.

#### **10x Cost Reduction Strategy** (Manus AI)
- **Avoid dynamic tool changes**: Tool definitions live near front of context
- Any change invalidates KV-cache for all subsequent actions
- Keep tool definitions stable across iterations

### Compression Techniques

#### **1. Observation Masking**
- Keep agent's reasoning and actions intact
- Replace older observations with placeholders outside fixed window
- **Benefits**: Simple, preserves decision chain
- **Results**: +2.6% solve rate, 52% cheaper (with Qwen3-Coder 480B)

#### **2. LLM Summarization**
- Separate summarizer model compresses older interactions
- Preserves recent turns verbatim
- **Benefits**: Better semantic preservation
- **Hybrid approach**: 7% cheaper than pure masking, 11% cheaper than LLM-only

#### **3. Context Summarization & Compression**
- Compress prior messages into structured summaries
- Inject summaries into conversation history
- **Claude Code implementation**: Auto-compaction at 95% context usage
- Preserves objectives, key decisions while summarizing details

#### **4. Context Trimming (Sliding Window)**
- Drop older turns, keep last N turns
- Store older parts as vectors for retrieval
- **Benefits**: Balance between immediate context and searchable history

#### **5. Artifact & Handle Pattern** (Agent Developer Kit)
- Treat large data as **Artifacts**: named, versioned objects
- Store URLs not web pages, file paths not contents
- **Anti-pattern**: "Context dumping" (placing 5MB CSV directly in chat)
- **Benefit**: Reversible compression, permanent tax removal

#### **6. Cache-Friendly Context Structure**
- **Stable prefixes**: System instructions, agent identity, long-lived summaries
- **Variable suffixes**: Latest user turn, new tool outputs, small updates
- **Benefit**: Frequently reused segments stable at front, dynamic content at end

#### **7. Multi-Technique Retrieval** (Windsurf)
- Combine embedding search, grep, knowledge graphs, AST parsing
- **Result**: 3x better retrieval accuracy than any single method

### Advanced Strategies

#### **Optical Compression** (DeepSeek-OCR)
- Transform textual information into visual modality
- **Result**: 10x effective context window expansion
- Leverages efficiency of visual data representation

#### **Agent Context Optimization (Acon)**
- Task- and environment-specific guidelines
- Systematic and adaptive context compression
- **Key finding**: Optimized contexts reduce costs AND improve decision quality

#### **Proactive Memory Management**
- Agents recognize natural breakpoints
- Self-directed compression at completed phases
- **Future direction**: Intelligent, agent-driven compression

### Context Engineering Patterns (4 Buckets)

1. **Writing context**: Save outside context window
2. **Selecting context**: Pull in when needed
3. **Compressing context**: Retain only required tokens
4. **Isolating context**: Separate concerns

### Common Pitfalls

#### **Don't use RAG to manage tool definitions**
- Fetching tools dynamically breaks KV cache
- Confuses model with "hallucinated" tools
- **Best practice**: Keep tool definitions stable

#### **Context Rot**
- Performance degrades as context window fills
- "Effective context window" << advertised token limit
- **Solution**: Proactive compression before hitting limits

#### **Format matters**
- Raw HTML wastes tokens with unnecessary markup
- **Best practice**: Convert HTML to Markdown
- Cleaner, easier for AI to understand

---

## 3. RAG Patterns for Codebases

### Why Codebase RAG?

> "RAG for codebases is the essential technique if you want to use powerful LLMs to work with your own private company code, documents, or Jira tickets. It is the bridge that securely connects a generic AI with your specific, proprietary project data."

### How It Works

1. **Indexing Phase**:
   - Convert code/docs into embeddings (numerical representations)
   - Store in vector database for efficient search
   - Parse code structure with AST for semantic chunks

2. **Retrieval Phase**:
   - User query: "Write a test for calculate_tax function"
   - Search codebase for relevant context
   - Augment prompt with retrieved code/docs

3. **Generation Phase**:
   - LLM receives original question + relevant context
   - Generates accurate, project-specific answer
   - No guessing—uses retrieved information as "temporary memory"

### Enterprise-Scale Challenges

#### **Intelligent Chunking**
- **Problem**: Naive chunking breaks semantic boundaries
- **Solution**: AST-based chunking preserves complete functions/classes
- Paragraphs work for natural language; code needs structure-aware splitting

#### **Enhanced Embeddings**
- Pre-trained models for code (CodeBERT, GraphCodeBERT, UniXcoder)
- Capture syntax, semantics, and code structure
- Better than generic text embeddings

#### **Advanced Retrieval**
- **Hybrid search**: Combine vector similarity + keyword matching
- **Multi-technique**: Embeddings + grep + knowledge graphs + AST
- **Windsurf result**: 3x better accuracy than single method

#### **Scalable Architecture**
- Distributed vector databases
- Incremental indexing for large codebases
- Metadata enrichment (author notes, dependencies, timestamps)

### Implementation Stack

#### **Vector Databases**
- Pinecone, Weaviate, Milvus, Qdrant
- ChromaDB, FAISS (open-source options)
- Store and query embeddings efficiently

#### **Embedding Models**
- **Code-specific**: CodeBERT, GraphCodeBERT, UniXcoder
- **General-purpose**: OpenAI text-embedding-3, Cohere
- **Best practice**: Use code-trained models for better semantic understanding

#### **Code Parsing**
- **Tree-sitter**: Multi-language AST parsing
- Identify functions, classes, methods, imports
- Structure-aware chunking

### Available Tools & Projects

#### **code-graph-rag**
- Analyzes multi-language codebases with Tree-sitter
- Builds comprehensive knowledge graphs
- Natural language querying + editing capabilities
- **Benefit**: Understands code relationships, not just text similarity

#### **CodeRAG**
- Indexes entire codebase (not just limited context window)
- Provides contextual suggestions based on complete project
- Real-time codebase querying and augmentation

#### **Code Context (MCP Server)**
- Tree-sitter analysis + semantic embeddings
- Hybrid search: vector similarity + keyword matching
- Enables contextual code retrieval in natural language

### Best Practices

1. **AST-based chunking**: Parse code structure, don't split arbitrarily
2. **Metadata enrichment**: Add author, dependencies, timestamps
3. **Workflow alignment**: Integrate with team's development process
4. **Incremental updates**: Re-index on commits, not full rebuilds
5. **Multi-technique retrieval**: Don't rely on embeddings alone

---

## 4. Machine-Readable Documentation Standards

### llms.txt Specification

> "Think of llms.txt as robots.txt for AI language models—a standardized way to help AI systems understand and navigate your documentation."

#### **Overview**
- **Proposed**: September 2024 by Jeremy Howard (Answer.AI Co-Founder)
- **Standard**: Defined at [llmstxt.org](https://llmstxt.org/)
- **Adoption**: Cloudflare, Anthropic, Perplexity, LangChain, many others

#### **Why It's Needed**
1. **Limited context windows**: AI can't process entire documentation sites
2. **HTML bloat**: Navigation, JavaScript, CSS waste tokens
3. **SEO vs. AI**: Traditional SEO optimizes for crawlers, not reasoning engines
4. **Efficiency**: Give AI exactly what it needs in format it understands

#### **File Types**

**`/llms.txt`** (Index file):
- Streamlined navigation view
- Links with brief descriptions
- AI must follow links for detailed content

**`/llms-full.txt`** (Complete documentation):
- Full documentation in markdown
- Self-contained, no link following needed
- For comprehensive context

#### **Format Structure**
```markdown
# Project Name
> Brief project summary (one sentence)

## Core Documentation
- [Quick Start](url): Description of the resource
- [API Reference](url): API documentation details
- [Configuration](url): Setup and configuration guide

## Optional
- [Additional Resources](url): Supplementary information
- [Examples](url): Code examples and tutorials
```

**Requirements**:
- Start with H1 project name
- Blockquote summary immediately after
- H2 sections to organize content
- "Optional" section for less critical resources

#### **Integration Tools**

**MCP Server** (LangChain):
- Integrates llms.txt into Cursor, Windsurf, Claude, Claude Code
- Automatic discovery and parsing
- Available as MCP server package

**Mintlify**:
- Automatic llms.txt generation from existing docs
- Simplifies creation and maintenance
- Built into documentation platform

### AI-Readable Documentation Best Practices

#### **Semantic HTML**
```html
<!-- Good: Semantic structure -->
<h1>Main Title</h1>
<h2>Section</h2>
<ul>
  <li>Bullet point</li>
</ul>

<!-- Bad: Divs for everything -->
<div class="title">Main Title</div>
<div class="section">Section</div>
<div class="list">
  <div>Bullet point</div>
</div>
```

**Benefits**:
- Clear document structure
- Improved chunking and retrieval
- Screen reader compatibility as bonus

#### **Content Format Hierarchy**
1. **Markdown**: Best for AI comprehension
2. **Semantic HTML**: Good with proper tags
3. **PDF**: Difficult to parse, migrate if possible

#### **Writing Style**
- Frequent headings to describe sections
- Organized lists (bulleted or numbered)
- Define key terms explicitly
- Provide document metadata
- Clear, concise language

#### **Specification-First Development**

> "A profound shift moving to spec-driven development. It's not about code-first; modern software engineers are creating (or asking AI for) implementation plans first."

**Spec-Kit Plus Methodology**:
- Clear, machine-readable specifications
- Specifications become executable blueprints
- AI-readable documentation enables non-engineers to collaborate

#### **RAG-Optimized Content**

> "When documentation serves both humans and machines well, it creates a self-reinforcing loop: clear documentation improves AI answers, and those answers help surface gaps that further improve the docs."

**Principles**:
- Optimizing for AI = optimizing for accessibility
- Clear structure helps both screen readers and LLMs
- Semantic richness improves retrieval quality

---

## 5. Semantic Code Organization for AI Comprehension

### Core Technology: Abstract Syntax Tree (AST)

> "An Abstract Syntax Tree is a data structure that represents the syntactic organization of source code—its functions, classes, imports, control flow, dependencies—without the noise of raw text like whitespace, punctuation, formatting."

#### **Why AST Matters**
- **Semantic boundaries**: Understand where functions/classes begin and end
- **Complete chunks**: Never cut off mid-function
- **Structural relationships**: Dependencies, inheritance, imports
- **Language-agnostic**: Tree-sitter supports 50+ languages

### Semantic Code Search Pipeline

#### **1. Code Splitting (AST-Based)**
```python
# Traditional splitting (bad)
chunk_size = 2000  # Arbitrary character count
chunks = [code[i:i+chunk_size] for i in range(0, len(code), chunk_size)]
# Result: Broken functions, incomplete context

# AST-based splitting (good)
ast = parse_with_tree_sitter(code, language="python")
chunks = extract_complete_functions_and_classes(ast)
# Result: Semantically complete, meaningful units
```

**Implementation**:
- LlamaIndex `CodeSplitter` function
- Tree-sitter for AST parsing
- Depth-first traversal with token limits
- Merge sibling nodes to avoid tiny chunks

#### **2. Embedding Generation**
```python
# Convert code snippet to fixed-size vector
embedding = model.encode(code_chunk)
# Result: [0.23, -0.45, 0.89, ...] (e.g., 768 dimensions)
```

**Code-Specific Models**:
- **CodeBERT**: BERT pre-trained on code
- **GraphCodeBERT**: Incorporates data flow
- **UniXcoder**: Multi-language, cross-modal
- **Better than**: Generic text embeddings (don't understand code semantics)

#### **3. Vector Database Indexing**
- Store embeddings with metadata
- Efficient similarity search (HNSW, IVF)
- Scale to millions of code snippets

#### **4. Semantic Retrieval**
```python
# Query by meaning, not keywords
query = "error handling functions"
query_embedding = model.encode(query)
results = vector_db.search(query_embedding, k=10)
# Returns: All error handling code, even if they don't contain exact phrase
```

### Hybrid Search: The Winning Approach

**Multi-Technique Retrieval** (Windsurf, Code Context):
1. **Vector embeddings**: Semantic similarity ("find authentication code")
2. **Keyword matching**: Exact text search (grep, ripgrep)
3. **Knowledge graphs**: Relationship-based retrieval
4. **AST parsing**: Structure-aware search

**Result**: 3x better accuracy than any single method

### Implementation Tools

#### **Roo Code**
- AST parsing for semantic code blocks
- Cross-project discovery
- Pattern recognition

#### **Continue**
- Vector database embeddings
- Tree-sitter AST parsing
- Ripgrep for fast text search
- Combined approach for best results

#### **Code Context (MCP Server)**
- Automatic splitting into logical units (functions, classes)
- Never cuts off mid-function
- Hybrid search: semantic + keyword

#### **Code-Graph-RAG**
- UniXcoder embeddings for semantic search
- Knowledge graph for relationships
- Natural language querying
- Query by description, not name

### Semantic Code Graph (Research)

**Problem**: Traditional dependency analysis only captures surface relationships.

**Solution**: Semantic Code Graph (SCG)
- Detailed abstract representation of code dependencies
- Close relationship to source code
- Enables faster comprehension
- Critical for large codebase maintenance

### Advanced: Hybrid AI Models

**RoBERTa + Graph Neural Networks**:
- RoBERTa: Semantic comprehension (text understanding)
- GNN: Structural learning (code graph relationships)
- **Result**: Outperforms single-model approaches for error detection

### Future: Multi-Agent Systems

> "The future of AI coding assistants is in multi-agent systems: specialized agents that communicate with each other, each handling distinct tasks under safe guardrails."

**Context-Aware Agents**:
- Understand codebase structure
- Follow coding standards
- Know compliance requirements
- Provide truly contextualized recommendations

---

## Implementation Recommendations for Trading System

### 1. Multi-Agent Coordination

**Immediate Actions**:
```bash
# Set up git worktrees for parallel agent work
git worktree add ../trading-rl-agent -b claude/rl-development
git worktree add ../trading-safety -b claude/safety-tests
git worktree add ../trading-docs -b claude/documentation
```

**Agent Roles**:
- **RL Agent Developer**: Focus on reinforcement learning system
- **Safety Engineer**: Build and maintain safety tests
- **Documentation Agent**: Keep docs AI-readable and current
- **Orchestrator**: Coordinate across agents (your CLAUDE.md already does this)

**Coordination Pattern**: Hierarchical multi-agent
- CLAUDE.md acts as "lead agent" with strategic context
- Specialized agents work in worktrees with narrow focus
- claude-progress.txt serves as shared knowledge base

### 2. Context Optimization

**Immediate Actions**:

**A. Implement Artifact Pattern**:
```python
# Instead of dumping full market data in context:
# ❌ Bad
context = f"Here's 5MB of market data: {json.dumps(all_market_data)}"

# ✅ Good
context = f"Market data available at: data/market_snapshot_{timestamp}.json"
# Reference by path, load only when needed
```

**B. Create llms.txt for Trading System**:
```bash
# /home/user/trading/llms.txt
```
```markdown
# AI Trading System
> Multi-platform automated trading with AI decision-making, combining Alpaca, RL agents, and momentum strategies

## Core Documentation
- [System Architecture](docs/architecture.md): Overall system design and components
- [R&D Phase](docs/r-and-d-phase.md): Current 90-day research and development strategy
- [Trading Strategies](docs/trading-strategies.md): Five-tier strategy implementation
- [Verification Protocols](docs/verification-protocols.md): "Show, Don't Tell" data validation

## Agent Instructions
- [CLAUDE.md](.claude/CLAUDE.md): Primary agent coordination and memory
- [Agent Adaptation](.claude/docs/ai-agent-adaptation-plan.md): A1/A2/T1/T2 modes for improvement

## System State
- [System State](data/system_state.json): Current system state and performance
- [Daily Reports](reports/): Historical performance reports

## Optional
- [Research Findings](docs/research-findings.md): Future enhancement roadmap
- [Profit Optimization](docs/profit-optimization.md): Cost-benefit analysis
```

**C. Enable KV-Cache Optimization**:
- Keep tool definitions stable (don't add/remove mid-session)
- Use stable system prompts at conversation start
- Dynamic content at end of context

**D. Implement Context Summarization**:
```python
# In StateManager or new ContextManager
def summarize_old_trades(self, cutoff_days=7):
    """Summarize trades older than cutoff, keep recent verbatim"""
    recent = [t for t in trades if days_ago(t) <= cutoff_days]
    old = [t for t in trades if days_ago(t) > cutoff_days]

    summary = {
        "total_trades": len(old),
        "total_pnl": sum(t.pnl for t in old),
        "win_rate": calculate_win_rate(old),
        "avg_return": calculate_avg_return(old)
    }

    return {"summary": summary, "recent_trades": recent}
```

### 3. Codebase RAG

**Immediate Actions**:

**A. Implement AST-Based Code Chunking**:
```python
# Add to new file: src/utils/code_indexer.py
import tree_sitter
from tree_sitter import Language, Parser

def chunk_code_by_ast(filepath, language="python"):
    """Split code into semantic chunks using AST"""
    parser = Parser()
    parser.set_language(Language(tree_sitter.Language.build_library(
        'build/my-languages.so',
        ['/path/to/tree-sitter-python']
    ), 'python'))

    with open(filepath, 'rb') as f:
        tree = parser.parse(f.read())

    chunks = []
    for node in tree.root_node.children:
        if node.type in ['function_definition', 'class_definition']:
            chunks.append({
                'type': node.type,
                'name': extract_name(node),
                'code': extract_code(node),
                'start_line': node.start_point[0],
                'end_line': node.end_point[0]
            })

    return chunks
```

**B. Build Knowledge Graph**:
```python
# Track relationships between components
knowledge_graph = {
    "TradingOrchestrator": {
        "uses": ["StateManager", "AlpacaAPI", "RLAgent"],
        "called_by": ["main.py", "scheduler"],
        "description": "Main trading loop coordinator"
    },
    "RLAgent": {
        "uses": ["MarketAnalyzer", "PositionSizer"],
        "called_by": ["TradingOrchestrator"],
        "description": "Reinforcement learning trading decisions"
    }
}
```

**C. Create Semantic Search**:
```python
# Enable "find momentum calculation code"
# Instead of grep "momentum"
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('microsoft/codebert-base')
query = "momentum calculation with MACD and RSI"
query_embedding = model.encode(query)

# Search pre-indexed code chunks
results = vector_db.search(query_embedding, k=5)
# Returns: All momentum-related code, even if doesn't contain exact phrase
```

### 4. Machine-Readable Documentation

**Immediate Actions**:

**A. Create /llms.txt** (see example in section 2B above)

**B. Add /llms-full.txt**:
```bash
# Generate comprehensive markdown of all docs
cat docs/*.md > llms-full.txt
# Or use tool to extract from HTML/existing docs
```

**C. Improve Existing Docs**:
```markdown
# ✅ Good: Semantic structure
# Trading Strategies

## Overview
Five-tier system balancing risk and return.

## Tier 1: Core ETFs
- **Purpose**: Stability and diversification
- **Allocation**: 40% of daily investment
- **Instruments**: SPY, QQQ, IWM

## Tier 2: Growth Stocks
- **Purpose**: Higher returns with moderate risk
...

# ❌ Bad: Flat structure, no hierarchy
Trading Strategies

We have a five-tier system. Tier 1 is core ETFs like SPY, QQQ, IWM for 40% allocation. Tier 2 is growth stocks...
```

**D. Enable MCP Integration**:
```json
// .claude/mcp_config.json (add llms.txt server)
{
  "mcpServers": {
    "llms-txt": {
      "command": "npx",
      "args": ["-y", "@langchain/mcp-server-llms-txt"]
    }
  }
}
```

### 5. Semantic Code Organization

**Immediate Actions**:

**A. Reorganize by Semantic Domains**:
```
src/
├── trading/               # Trading execution domain
│   ├── orchestrator.py
│   ├── executor.py
│   └── position_sizer.py
├── intelligence/          # AI/ML decision domain
│   ├── rl_agent.py
│   ├── sentiment_analyzer.py
│   └── multi_llm_analyzer.py
├── market_data/          # Data fetching domain
│   ├── alpaca_client.py
│   ├── yahoo_finance.py
│   └── news_fetcher.py
├── risk/                 # Risk management domain
│   ├── portfolio_risk.py
│   ├── position_limits.py
│   └── circuit_breakers.py
└── state/                # State management domain
    ├── state_manager.py
    └── performance_tracker.py
```

**B. Add Semantic Metadata**:
```python
# At top of each module
"""
Module: TradingOrchestrator
Domain: Trading Execution
Purpose: Coordinates daily trading loop, delegates to specialists
Dependencies: StateManager, AlpacaAPI, RLAgent
Called By: main.py, scheduler
Key Functions:
  - execute_daily_trade(): Main entry point for trading cycle
  - validate_market_hours(): Ensures trades only during market hours
  - handle_error(): Error recovery and alerting
"""
```

**C. Build Import Graph**:
```python
# scripts/build_import_graph.py
import ast
import os

def extract_imports(filepath):
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)

    return imports

# Generate graph for all files
import_graph = {}
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            import_graph[filepath] = extract_imports(filepath)

# Save for AI consumption
with open('docs/import_graph.json', 'w') as f:
    json.dump(import_graph, f, indent=2)
```

### 6. Priority Implementation Plan

**Week 1: Foundation**
1. Create `/llms.txt` and `/llms-full.txt`
2. Set up git worktrees structure (`.trees/` directory)
3. Implement artifact pattern for large data
4. Add semantic metadata to key modules

**Week 2: RAG Infrastructure**
1. Install tree-sitter for AST parsing
2. Build code chunking pipeline
3. Generate code embeddings (CodeBERT)
4. Create vector database index

**Week 3: Context Optimization**
1. Implement context summarization for old trades
2. Refactor to stable tool definitions
3. Build import/dependency graph
4. Test KV-cache optimization

**Week 4: Multi-Agent Coordination**
1. Define agent roles and responsibilities
2. Create worktrees for parallel work
3. Test coordination patterns
4. Measure performance improvements

---

## Key Metrics to Track

### Context Efficiency
- **KV-cache hit rate**: Target >80%
- **Context window usage**: Should stay <70% with summarization
- **Token cost per session**: Track before/after optimizations

### RAG Performance
- **Retrieval accuracy**: Can AI find relevant code?
- **Semantic search quality**: Meaning-based queries vs. keyword
- **Index freshness**: How quickly new code is searchable?

### Multi-Agent Coordination
- **Parallel work sessions**: How many agents working simultaneously?
- **Context isolation**: Are agents interfering with each other?
- **Merge conflicts**: Should decrease with worktrees

### Documentation Quality
- **AI answer accuracy**: Test with common queries
- **llms.txt coverage**: Percentage of docs indexed
- **Retrieval speed**: Time to find relevant docs

---

## Sources

### Multi-Agent Coordination
- [AI Agent Orchestration Patterns - Microsoft Learn](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [How we built our multi-agent research system - Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Deep Dive into AutoGen Multi-Agent Patterns 2025](https://sparkco.ai/blog/deep-dive-into-autogen-multi-agent-patterns-2025)
- [AgentOrchestra: A Hierarchical Multi-Agent Framework](https://arxiv.org/html/2506.12508v1)
- [Introducing Microsoft Agent Framework](https://azure.microsoft.com/en-us/blog/introducing-microsoft-agent-framework/)
- [Git Worktrees: Multi-Agent AI Development](https://medium.com/@mabd.dev/git-worktrees-the-secret-weapon-for-running-multiple-ai-coding-agents-in-parallel-e9046451eb96)
- [How Git Worktrees Changed My AI Agent Workflow - Nx](https://nx.dev/blog/git-worktrees-ai-agents)
- [Parallel AI Coding with Git Worktrees - Agent Interviews](https://docs.agentinterviews.com/blog/parallel-ai-coding-with-gitworktrees/)
- [ccswarm: Multi-agent orchestration with Git worktree](https://github.com/nwiizo/ccswarm)

### Context Management
- [Effective context engineering for AI agents - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- [Cutting Through the Noise: Smarter Context Management - JetBrains](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)
- [Compressing Context - Factory.ai](https://factory.ai/news/compressing-context)
- [Acon: Optimizing Context Compression for Long-horizon LLM Agents](https://arxiv.org/html/2510.00615v1)
- [Deep Dive into Context Engineering for Agents - Galileo.ai](https://galileo.ai/blog/context-engineering-for-agents)

### Codebase RAG
- [What Is RAG for Codebases - CodeForGeek](https://codeforgeek.com/rag-retrieval-augmented-generation-for-codebases/)
- [code-graph-rag: Ultimate RAG for monorepo](https://github.com/vitali87/code-graph-rag)
- [Evaluating RAG for large-scale codebases - Qodo](https://www.qodo.ai/blog/evaluating-rag-for-large-scale-codebases/)
- [CodeRAG-Bench: Can Retrieval Augment Code Generation?](https://arxiv.org/html/2406.14497v1)
- [Software Development with Retrieval Augmentation - GitHub](https://github.com/resources/articles/software-development-with-retrieval-augmentation-generation-rag)

### Machine-Readable Documentation
- [The /llms.txt file - Official Specification](https://llmstxt.org/)
- [Instructor Adopts llms.txt](https://python.useinstructor.com/blog/2025/03/19/instructor-adopts-llms-txt/)
- [What is llms.txt? The AI-Readable File Standard](https://llmstxt.studio/docs/what-is-llmstxt)
- [Simplifying docs for AI with /llms.txt - Mintlify](https://www.mintlify.com/blog/simplifying-docs-with-llms-txt)
- [Writing documentation for AI: best practices - kapa.ai](https://docs.kapa.ai/improving/writing-best-practices)
- [AI-Readable Documentation - AI Native Development](https://ai-native-development.gitbook.io/archived/introduction/ai-native-documentation)

### Semantic Code Organization
- [Code Context (Semantic Code Search) MCP Server](https://www.aitoolhouse.com/mcp-servers/code-context)
- [Semantic Code Graph - IEEE](https://ieeexplore.ieee.org/document/10385091/)
- [Leveraging Semantic Analysis for Better AI Code Generation](https://zencoder.ai/blog/semantic-analysis-ai-code-generation)
- [Codebase Indexing - Roo Code](https://docs.roocode.com/features/codebase-indexing)
- [Building an Open-Source Alternative to Cursor - Milvus](https://milvus.io/blog/build-open-source-alternative-to-cursor-with-code-context.md)
- [Semantic Code Search - Medium](https://medium.com/@wangxj03/semantic-code-search-010c22e7d267)

---

## Conclusion

The landscape of AI-native development is rapidly evolving. Key takeaways:

1. **Infrastructure over prompts**: Scaling multi-agent systems requires infrastructure design, not just better prompts
2. **Context is critical**: "Most agent failures are context failures" - optimize aggressively
3. **Hybrid approaches win**: Combining multiple techniques (embeddings + AST + graphs) beats any single method
4. **Standards emerging**: llms.txt adoption by major players signals convergence on AI-readable documentation
5. **Semantic understanding**: AST parsing + embeddings enable true semantic code search and comprehension

The trading system is well-positioned to adopt these patterns incrementally, starting with llms.txt and worktrees, then building toward full RAG and multi-agent coordination.
