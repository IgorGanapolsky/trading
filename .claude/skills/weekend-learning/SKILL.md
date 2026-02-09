---
name: weekend-learning
description: Weekend auto-learning from YouTube transcripts, Phil Town content, trade analysis
version: 1.1.0
context: fork
triggers:
  - weekend-learn
---

# Weekend Learning Skill

Trigger continuous learning during market-closed hours.

## Trigger

- `/weekend-learn` - Manually trigger weekend learning
- Automatic: Sunday 8 AM ET via GitHub Actions

## What It Does

1. **Content Ingestion** (cost-free)
   - Phil Town YouTube transcripts
   - Options education (Option Alpha, InTheMoney)
   - Blog/podcast content

2. **RAG Vectorization** (local LanceDB - free)
   - Semantic chunking
   - BAAI/bge-small-en-v1.5 embeddings
   - No cloud RAG costs

3. **Trade Analysis**
   - Review last 30 days of trades
   - Calculate win rate by strategy
   - Identify patterns

4. **Insight Generation**
   - Recommendations for next week
   - Phil Town Rule #1 reminders

## Cost Controls

- **Budget**: $50/month GCP max
- **Strategy**: Local LanceDB instead of cloud RAG
- **Frequency**: Once per weekend (Sunday only)
- **No API calls**: Uses free YouTube API quota

## Usage

```bash
# Manual trigger
gh workflow run weekend-learning.yml

# Check status
gh run list --workflow=weekend-learning.yml

# View results
cat data/weekend_insights.json
```

## Integration

- Updates `rag_knowledge/` with new content
- Reindexes local LanceDB
- Auto-creates PR with learned content
- Auto-merges if only safe files changed
