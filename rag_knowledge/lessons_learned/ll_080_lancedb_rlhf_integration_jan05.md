# Lesson Learned #080: LanceDB Integration for RLHF

**Date**: 2026-01-05
**Category**: RLHF, Machine Learning, Infrastructure, Vector Database
**Severity**: High
**Status**: Implemented

## Summary

Integrated LanceDB vector database for RLHF feedback storage, replacing flat JSON files with semantic search and time-travel query capabilities.

## Problem

Previous RLHF implementation used flat JSON files (`data/feedback/feedback_*.jsonl`) for storing feedback:

**Limitations:**
- No semantic search - couldn't find "similar decisions that got thumbs down"
- No time-travel - couldn't debug model drift at specific checkpoints
- Limited context matching - couldn't leverage similar trading contexts
- Manual model versioning - checkpoints stored separately in JSON

**Evidence:**
```python
# src/learning/feedback_trainer.py:232 (before)
pattern = str(self.feedback_dir / "feedback_*.jsonl")
for filepath in glob(pattern):
    # Parse JSONL manually
```

## Solution

Implemented LanceDB vector database for RLHF with:

### 1. **Semantic Search**
Find similar feedback based on trading context:
```python
trainer.search_similar_feedback(
    context={"decision_type": "entry", "ticker": "AAPL", "market_regime": "high_volatility"},
    limit=10,
    filter_positive=True  # Only successful decisions
)
```

### 2. **Time-Travel Queries**
Debug model drift by querying feedback at specific checkpoints:
```python
trainer.get_feedback_at_checkpoint(
    alpha=10.0,
    beta=5.0,
    tolerance=0.5
)
# Returns: "What feedback did we see when the model was at α=10?"
```

### 3. **Pattern Analysis**
Extract common features in positive vs negative feedback:
```python
patterns = trainer.analyze_feedback_patterns(limit=100)
# Returns: Most common contexts in thumbs up vs thumbs down
```

### 4. **Automatic Versioning**
Every feedback stores model checkpoint automatically:
```python
{
    "feedback_id": "uuid",
    "timestamp": "2026-01-05T14:28:00",
    "model_alpha": 10.5,
    "model_beta": 3.2,
    "feature_weights": {...},
    "vector": [0.123, -0.456, ...]  # FastEmbed embedding
}
```

## Architecture

### Vector Database Stack (4 databases total)

| Database | Purpose | Storage | Search Type |
|----------|---------|---------|-------------|
| **ChromaDB** | Lessons learned | Local | Semantic |
| **Vertex AI RAG** | Dialogflow queries | Cloud | Semantic |
| **LangSmith** | Trade observability | Cloud | Metadata |
| **LanceDB** | RLHF training data | Local | Semantic + Time-travel |

### Why LanceDB for RLHF?

1. **Fast incremental updates** - Optimized for continuous learning (RLHF writes on every feedback)
2. **Time-travel built-in** - Query any historical checkpoint naturally
3. **Multimodal storage** - Embeddings + metadata + raw context in one record
4. **Zero-copy reads** - Apache Arrow format for performance
5. **Backward compatible** - Optional, falls back to JSON if unavailable

## Implementation Details

### Files Created

1. **`src/learning/lancedb_feedback_store.py`** (310 lines)
   - `LanceDBFeedbackStore` class
   - Semantic search using FastEmbed (BAAI/bge-small-en-v1.5)
   - Time-travel queries by model checkpoint
   - Statistics and analytics

2. **`tests/test_lancedb_feedback.py`** (13 tests, 100% pass)
   - Installation verification
   - Semantic search tests
   - Time-travel query tests
   - FeedbackTrainer integration tests
   - Backward compatibility tests

### Files Modified

1. **`src/learning/feedback_trainer.py`**
   - Added `use_lancedb` parameter (default: True)
   - Store feedback in LanceDB on every `record_feedback()`
   - Exposed semantic search methods
   - Include LanceDB stats in `get_model_stats()`

### Context Embedding

Converts trading context to text for semantic search:
```python
def _context_to_text(context: dict) -> str:
    # "Decision: entry | Market: high_volatility | Ticker: AAPL | Signal: 0.8"
    parts = []
    if "decision_type" in context:
        parts.append(f"Decision: {context['decision_type']}")
    if "market_regime" in context:
        parts.append(f"Market: {context['market_regime']}")
    if "ticker" in context:
        parts.append(f"Ticker: {context['ticker']}")
    return " | ".join(parts)
```

## Key Metrics

| Metric | Value |
|--------|-------|
| Tests added | 13 (all pass) |
| Lines of code | ~600 (2 new files + modifications) |
| Test time | 15.73s |
| Dependencies added | `lancedb>=0.4.0`, `fastembed>=0.2.0` |
| Backward compatible | Yes (optional, fallback to JSON) |

## Usage Examples

### Basic Feedback Recording
```python
from src.learning.feedback_trainer import FeedbackTrainer

trainer = FeedbackTrainer(use_lancedb=True)

# Record feedback (automatically stores in LanceDB)
trainer.record_feedback(
    is_positive=True,
    context={
        "decision_type": "entry_signal",
        "ticker": "AAPL",
        "strategy": "momentum",
        "market_regime": "trending",
        "signal_strength": 0.85
    }
)
```

### Semantic Search for Similar Decisions
```python
# "What feedback did we get for similar trading contexts?"
similar_feedback = trainer.search_similar_feedback(
    context={
        "decision_type": "entry_signal",
        "ticker": "AAPL",
        "market_regime": "high_volatility"
    },
    limit=10,
    filter_positive=True  # Only successful decisions
)

for fb in similar_feedback:
    print(f"Feedback: {fb['is_positive']}, Reward: {fb['reward']}, Context: {fb['context_text']}")
```

### Time-Travel Debugging
```python
# "What feedback caused the model to drift from alpha=10?"
checkpoint_feedback = trainer.get_feedback_at_checkpoint(
    alpha=10.0,
    beta=5.0,
    tolerance=0.5
)

print(f"Found {len(checkpoint_feedback)} feedback records at α=10, β=5")
```

### Pattern Analysis
```python
patterns = trainer.analyze_feedback_patterns(limit=100)

print(f"Positive feedback count: {patterns['positive_count']}")
print(f"Common features in positive feedback: {patterns['positive_common_features']}")
print(f"Common features in negative feedback: {patterns['negative_common_features']}")
```

## Benefits

### Before (Flat JSON)
- ❌ No semantic search
- ❌ No time-travel
- ❌ Manual checkpoint management
- ❌ Limited context matching
- ❌ Linear scan for queries

### After (LanceDB)
- ✅ Semantic search over feedback contexts
- ✅ Time-travel queries for debugging
- ✅ Automatic checkpoint versioning
- ✅ Rich context matching for better learning
- ✅ Fast vector search (sub-second)

## Prevention/Best Practices

1. **Use semantic search for context-aware RLHF** - Find similar decisions to learn faster
2. **Time-travel for debugging** - Query historical checkpoints when model drifts
3. **Store rich context** - Include market conditions, strategy, signal strength
4. **Optional by default** - LanceDB is optional, falls back to JSON gracefully
5. **Test backward compatibility** - Ensure system works without LanceDB

## Research Support

**Thompson Sampling + Context**: Research shows contextual bandits benefit from rich context matching. LanceDB enables semantic context matching, improving sample efficiency.

**References:**
- ll_073: Feedback Training Pipeline (Thompson Sampling baseline)
- Meta RLHF papers: Context-aware reward models outperform context-free

## Related Files

- `src/learning/lancedb_feedback_store.py`
- `src/learning/feedback_trainer.py`
- `tests/test_lancedb_feedback.py`
- `requirements-rag.txt`

## Tags

#rlhf #lancedb #vector-database #semantic-search #time-travel #thompson-sampling #feedback #context-aware
