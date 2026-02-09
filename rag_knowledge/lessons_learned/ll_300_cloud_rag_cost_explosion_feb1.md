# LL-300: Cloud RAG Cost Explosion - $98/mo vs $20/mo Budget

**Date**: February 1, 2026
**Severity**: CRITICAL
**Category**: Cost Management

## Problem

Cloud RAG bill hit $98.70/month when budget was $20/month - 5x over budget.

## Root Cause

Multiple workflows calling cloud RAG APIs:

1. `enforce-phil-town-completeness.yml` - Every push + 2x daily schedule
2. `phil-town-ingestion.yml` - Daily weekdays (ingesting YouTube + blogs)
3. `daily-trading.yml` - Multiple RAG calls per trading day:
   - `pretrade-rag-query` job
   - `pre_session_rag_check.py`
   - `record_account_to_rag.py`
   - `sync_trades_to_rag.py`
4. Dialogflow webhook (Cloud Run) - Every voice query uses cloud RAG

## Cloud RAG Cost Breakdown (Estimated)

| Component              | Frequency           | Est. Monthly Cost |
| ---------------------- | ------------------- | ----------------- |
| RAG Query API          | ~100 calls/day      | $30-40            |
| Text Embeddings        | ~500/day            | $10-15            |
| Datastore storage      | Ongoing             | $10-20            |
| Cloud Run (webhook)    | ~50 requests/day    | $5-10             |
| YouTube/Blog ingestion | Daily vectorization | $15-20            |

## Resolution

Disabled all automated cloud RAG calls in GitHub Actions:

1. `enforce-phil-town-completeness.yml` - Disabled auto-triggers (manual only)
2. `phil-town-ingestion.yml` - Disabled schedule (manual only)
3. `daily-trading.yml`:
   - Disabled `pretrade-rag-query` job
   - Disabled `pre_session_rag_check.py`
   - Disabled `record_account_to_rag.py`
   - Disabled `sync_trades_to_rag.py`

## Alternative Approach

Use **local LanceDB + file-based storage** instead of cloud RAG:

- Trade history: `data/system_state.json` (already works)
- Lessons learned: `rag_knowledge/lessons_learned/*.md` (local search)
- Account balances: Can add to `system_state.json`

## Budget Protection

Going forward:

- Set a $15/month budget alert
- Manual cloud syncs only when truly needed
- Monitor billing weekly

## CEO Action Required

Set a provider-level budget alert for $20/month with 50%, 90%, and 100% thresholds.

## Prevention

- ALWAYS calculate API costs BEFORE enabling automated workflows
- Prefer local storage over cloud APIs for high-frequency operations
- Review GCP billing weekly

## References

- Cloud bill: $98.70 (Feb 1, 2026)
- Budget: $20/month
