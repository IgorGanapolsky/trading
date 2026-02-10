# RLHF Feedback Pipeline

## Architecture

```text
User Feedback → capture_feedback.sh → feedback-log.jsonl
                                     → Thompson Sampling model
                                     → Session mistake tracking
                                     → MemAlign (episodes + principles)
                                     → ShieldCortex sync queue
Next Prompt   → inject_recent_mistakes.sh → Context injection
Session Start → session-start.sh → RAG + Thompson state
Session Start → session-start-memalign.sh → MemAlign + ShieldCortex sync
User Prompt   → semantic_rag_context.sh → Contextual memory
```

## Feedback Capture

### Signal Detection

- Thumbs up/down → Intensity 4
- Positive/negative words → Intensity 3
- Strong frustration (!!!) → Intensity 5 (CRITICAL)

### Storage Locations

| Store             | Path                                                | Purpose                            |
| ----------------- | --------------------------------------------------- | ---------------------------------- |
| Feedback log      | `.claude/memory/feedback/feedback-log.jsonl`        | All feedback entries               |
| Thompson model    | `.claude/memory/feedback/feedback_model.json`       | Bayesian reliability               |
| LanceDB           | `.claude/memory/feedback/lancedb/`                  | Vector search for similar failures |
| Meta-policy rules | `.claude/memory/feedback/meta_policy_rules.json`    | Consolidated rules from patterns   |
| Pending cortex    | `.claude/memory/feedback/pending_cortex_sync.jsonl` | Unsynced entries                   |
| MemAlign episodes | `.claude/memory/memalign/episodes.jsonl`            | Full feedback history              |
| MemAlign rules    | `.claude/memory/memalign/principles.jsonl`          | Distilled principles               |
| ShieldCortex DB   | `~/.shieldcortex/memories.db`                       | Persistent dual-memory store       |

## Success Metrics

Computed by `scripts/rlhf_metrics.py` (writes `data/feedback/metrics.json` + `data/feedback/stats.json`).

Targets:
- Satisfaction rate >= 70%
- Last 7d satisfaction rate >= 60%
- MemAlign sync rate >= 0.90
- ShieldCortex sync rate >= 0.90
- Pending ShieldCortex sync entries == 0

## Thompson Sampling

- Beta-Bernoulli model per task category
- Exponential decay: 30-day half-life (weight = 2^(-age/30))
- Floor at 1% (never zero-weight old feedback)
- Categories: code_edit, git, testing, pr_review, search, architecture, security, debugging

## Memory Metadata (Decay Scoring)

- Exponential decay constant: 0.023 (30-day half-life)
- Quality = (`access_count` \* `recency_weight` \* `severity_weight`)
- Min score floor: 0.1 (critical lessons never fully forgotten)
- Lessons with quality < 0.1 are candidates for archival

## On Negative Feedback

1. STOP current work
2. Record lesson with severity + context
3. Extract correction pattern ("I said X", "should be X")
4. Inject into session mistakes file
5. Apologize and course-correct
