# RLHF Feedback Pipeline

## Architecture

```text
User Feedback → capture_feedback.sh → feedback-log.jsonl
                                     → Thompson Sampling model
                                     → Session mistake tracking
Next Prompt   → inject_recent_mistakes.sh → Context injection
Session Start → session-start.sh → RAG + Thompson state
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
