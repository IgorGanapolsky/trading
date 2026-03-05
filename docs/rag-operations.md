# RAG Operations

## Build Paths and Profiles

`scripts/build_rag_query_index.py` supports two write profiles:

- `RAG_WRITE_PROFILE=repo`
  - outputs: `data/rag/lessons_query.json`, `docs/data/rag/lessons_query.json`, `docs/lessons/index.html`
- `RAG_WRITE_PROFILE=local`
  - outputs: `artifacts/local/rag/lessons_query.json`, `artifacts/local/rag/lessons_index.html`

Default behavior:

- CI defaults to `repo`
- local runs should set `RAG_WRITE_PROFILE=local`

## Freshness SLO

Freshness guard checks:

- RAG query index max age (`RAG_QUERY_INDEX_MAX_AGE_MINUTES`, default 1440)
- Context index max age (`CONTEXT_INDEX_MAX_AGE_MINUTES`, default 1440)

Pre-session guard (`scripts/pre_session_rag_check.py`) now attempts one automatic refresh if stale.

## Standard Refresh Sequence

```bash
python3 scripts/build_rag_query_index.py
python3 scripts/build_context_engine_index.py --project-root .
python3 scripts/pre_session_rag_check.py --no-block
```

## Validation

- `python3 scripts/system_health_check.py`
- `python3 scripts/rag_pre_deployment_check.py --check-changed --check-workflows`

## Deployment Notes

- Keep `data/rag/lessons_query.json` and `docs/data/rag/lessons_query.json` in sync.
- If webhook deploy workflow is disabled, run endpoint validation manually from health/integration workflows.
