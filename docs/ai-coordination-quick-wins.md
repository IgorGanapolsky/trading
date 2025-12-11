# AI Coordination Quick Wins for Trading System

**Date**: December 11, 2025
**Full Research**: See `docs/ai-agent-coordination-research-2025.md`

---

## Immediate Actions (This Week)

### 1. Create `/llms.txt` (15 minutes)

Create `/home/user/trading/llms.txt`:

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
- [Agent Adaptation](.claude/docs/ai-agent-adaptation-plan.md): A1/A2/T1/T2 modes

## System State
- [System State](data/system_state.json): Current system state and performance
- [Daily Reports](reports/): Historical performance reports

## Optional
- [Research Findings](docs/research-findings.md): Future enhancement roadmap
- [Profit Optimization](docs/profit-optimization.md): Cost-benefit analysis
```

**Benefit**: Anthropic, Claude, and other AI systems can instantly understand project structure.

---

### 2. Set Up Git Worktrees for Multi-Agent Work (10 minutes)

```bash
# Create worktree directory structure
mkdir -p .trees

# Example: Parallel development on different features
git worktree add .trees/rl-agent -b claude/rl-development
git worktree add .trees/safety-tests -b claude/safety-enhancements
git worktree add .trees/docs -b claude/documentation-update

# Each worktree = isolated working directory
# Run separate Claude instance in each
# No interference, no branch switching conflicts
```

**Benefit**: Multiple AI agents can work in parallel without conflicts.

---

### 3. Implement Artifact Pattern for Large Data (30 minutes)

**Current (Bad)**:
```python
# Dumping 5MB of data into context
context = f"Market data: {json.dumps(all_market_data)}"
# Permanently wastes tokens every subsequent turn
```

**New (Good)**:
```python
# src/utils/artifact_manager.py
class ArtifactManager:
    """Manage large data as artifacts, not context dumps"""

    @staticmethod
    def save_artifact(data, name, artifact_type="json"):
        """Save data as artifact, return reference"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"data/artifacts/{name}_{timestamp}.{artifact_type}"

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        return {
            "artifact_ref": path,
            "size_kb": os.path.getsize(path) / 1024,
            "created": timestamp
        }

    @staticmethod
    def load_artifact(artifact_ref):
        """Load artifact when needed"""
        with open(artifact_ref, 'r') as f:
            return json.load(f)

# Usage in trading code
artifacts = ArtifactManager()

# Save market data as artifact
market_ref = artifacts.save_artifact(
    all_market_data,
    name="market_snapshot"
)

# Reference in context (not full data)
context = f"Market data available at: {market_ref['artifact_ref']}"
# Load only when needed: artifacts.load_artifact(market_ref['artifact_ref'])
```

**Benefit**: 10x cost reduction on long sessions by avoiding context bloat.

---

### 4. Add Semantic Metadata to Key Modules (45 minutes)

Add to top of each critical module:

```python
# src/orchestrator/main.py
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

Context for AI:
  This is the main coordinator. It orchestrates the trading cycle by:
  1. Checking market hours and conditions
  2. Querying RL agent for trade decisions
  3. Executing trades via Alpaca API
  4. Recording results in StateManager
  5. Handling errors with circuit breakers

Related Modules:
  - intelligence/rl_agent.py: Makes trading decisions
  - state/state_manager.py: Persists system state
  - risk/portfolio_risk.py: Validates trades meet risk limits
"""
```

**Benefit**: AI agents instantly understand module purpose, relationships, and usage patterns.

---

## Medium-Term Wins (Next 2 Weeks)

### 5. Build Code Embedding Index (Weekend Project)

```bash
# Install dependencies
pip install sentence-transformers tree-sitter

# Create indexing script
```

```python
# scripts/build_code_index.py
from sentence_transformers import SentenceTransformer
import tree_sitter
import chromadb

def index_codebase():
    """Build semantic search index of entire codebase"""

    # 1. Parse all Python files with tree-sitter
    code_chunks = []
    for py_file in glob.glob('src/**/*.py', recursive=True):
        ast = parse_with_tree_sitter(py_file)
        chunks = extract_functions_and_classes(ast)
        code_chunks.extend(chunks)

    # 2. Generate embeddings with CodeBERT
    model = SentenceTransformer('microsoft/codebert-base')
    embeddings = model.encode([c['code'] for c in code_chunks])

    # 3. Store in vector database
    client = chromadb.Client()
    collection = client.create_collection("trading_codebase")
    collection.add(
        embeddings=embeddings.tolist(),
        documents=[c['code'] for c in code_chunks],
        metadatas=[{
            'file': c['file'],
            'type': c['type'],
            'name': c['name']
        } for c in code_chunks],
        ids=[f"{c['file']}:{c['name']}" for c in code_chunks]
    )

    print(f"Indexed {len(code_chunks)} code chunks")

if __name__ == "__main__":
    index_codebase()
```

**Benefit**: Semantic code search - "find momentum calculation code" returns all relevant code, even without keyword "momentum".

---

### 6. Implement Context Summarization (2-3 hours)

```python
# src/state/context_manager.py
class ContextManager:
    """Manage context window efficiency"""

    def summarize_old_trades(self, trades, cutoff_days=7):
        """Keep recent trades verbatim, summarize old trades"""

        recent = [t for t in trades if self._days_ago(t) <= cutoff_days]
        old = [t for t in trades if self._days_ago(t) > cutoff_days]

        old_summary = {
            "period": f"{len(old)} trades from {min(t.date for t in old)} to {max(t.date for t in old)}",
            "total_pnl": sum(t.pnl for t in old),
            "win_rate": len([t for t in old if t.pnl > 0]) / len(old) if old else 0,
            "avg_return": sum(t.return_pct for t in old) / len(old) if old else 0,
            "best_trade": max(old, key=lambda t: t.pnl).dict() if old else None,
            "worst_trade": min(old, key=lambda t: t.pnl).dict() if old else None
        }

        return {
            "summary": old_summary,
            "recent_trades": [t.dict() for t in recent]
        }

    def get_compact_state(self, full_state):
        """Return context-optimized state representation"""
        return {
            "portfolio": full_state["portfolio"],  # Always include
            "trades": self.summarize_old_trades(full_state["trades"]),
            "performance": full_state["performance"],  # Always include
            "system_health": full_state["system_health"],  # Always include
            # Historical data summarized, not included verbatim
            "historical_summary": {
                "days_active": full_state["days_active"],
                "total_trades": full_state["total_trades"],
                "cumulative_pnl": full_state["cumulative_pnl"]
            }
        }
```

**Benefit**: Stay below 70% context window usage even in long sessions.

---

## Advanced Wins (Month 2+)

### 7. Multi-Agent Specialization

Define specialized agents with narrow roles:

**Agent Roles**:
```yaml
# .claude/agents/rl_developer.md
Role: RL Agent Developer
Focus: Reinforcement learning system optimization
Worktree: .trees/rl-agent
Branch Pattern: claude/rl-*

Responsibilities:
- Implement and tune RL algorithms
- Test reward functions
- Optimize training loops
- Monitor agent performance

Context Files:
- src/intelligence/rl_agent.py
- docs/rl-architecture.md
- data/rl_training_log.json

Never Touch:
- Production trading code
- Risk management systems
- State management
```

```yaml
# .claude/agents/safety_engineer.md
Role: Safety Engineer
Focus: Testing and risk management
Worktree: .trees/safety
Branch Pattern: claude/safety-*

Responsibilities:
- Write safety tests
- Implement circuit breakers
- Monitor risk metrics
- Validate compliance

Context Files:
- tests/safety/
- src/risk/
- docs/safety-protocols.md

Never Touch:
- RL training code
- Strategy implementations
```

**Coordination**:
- Shared `.claude/CLAUDE.md` for system-wide context
- `claude-progress.txt` for cross-agent communication
- Git worktrees for isolation

**Benefit**: 3-5x faster development through parallel work.

---

### 8. Hybrid Search Implementation

```python
# src/utils/code_search.py
class HybridCodeSearch:
    """Multi-technique code search: embeddings + grep + AST"""

    def __init__(self):
        self.semantic_index = load_vector_db()
        self.ast_parser = TreeSitterParser()

    def search(self, query, k=10):
        """Hybrid search combining multiple techniques"""

        # 1. Semantic search (embeddings)
        semantic_results = self.semantic_index.search(query, k=k)

        # 2. Keyword search (grep/ripgrep)
        keyword_results = self.grep_search(query)

        # 3. AST-based search (structure)
        ast_results = self.ast_parser.find_by_signature(query)

        # 4. Merge and rank results
        combined = self._merge_results(
            semantic_results,
            keyword_results,
            ast_results
        )

        return combined[:k]

    def _merge_results(self, *result_sets):
        """Rank by multiple signals"""
        # Score based on:
        # - Semantic similarity
        # - Keyword match count
        # - AST structure match
        # - Recency (newer code ranked higher)
        ...
```

**Benefit**: 3x better retrieval accuracy than any single method.

---

## Key Metrics to Track

After implementing these optimizations:

1. **Context Efficiency**:
   - KV-cache hit rate (target: >80%)
   - Context window usage (target: <70%)
   - Token cost per session (expect 50-70% reduction)

2. **Development Speed**:
   - Features completed per week
   - Time to find relevant code (expect 5x faster with semantic search)
   - Merge conflicts (expect 80% reduction with worktrees)

3. **Code Quality**:
   - Test coverage (track in parallel worktrees)
   - Documentation completeness (AI-assisted with llms.txt)
   - Bug escape rate

---

## Priority Order

**Week 1** (Highest ROI):
1. Create `/llms.txt` (15 min) → Instant AI comprehension
2. Implement artifact pattern (30 min) → 10x cost reduction
3. Add semantic metadata (45 min) → Better AI understanding

**Week 2**:
4. Set up git worktrees (10 min) → Enable parallel work
5. Build code embedding index (weekend) → Semantic search

**Week 3-4**:
6. Implement context summarization (2-3 hours) → Stay under 70% context
7. Test multi-agent coordination (ongoing) → 3-5x faster development

**Month 2+**:
8. Hybrid search implementation → 3x better retrieval
9. Full multi-agent specialization → Maximum parallelization

---

## Resources

- **Full Research**: `/home/user/trading/docs/ai-agent-coordination-research-2025.md`
- **llms.txt Spec**: https://llmstxt.org/
- **Anthropic Context Engineering**: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- **Git Worktrees Guide**: https://nx.dev/blog/git-worktrees-ai-agents

---

**Bottom Line**: Start with llms.txt + artifact pattern this week. These two changes alone will provide 10x cost reduction and instant AI comprehension improvements. Build from there incrementally.
