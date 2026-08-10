# Continuous arXiv Paper Ingestion (DS / ML / Agentic RAG)

**Issue:** AGENT-364  
**Source:** [https://arxiv.org/](https://arxiv.org/) via `https://export.arxiv.org/api/query`  
**Scope:** Research only — never submits trades, never re-opens killed IC entries.

## Purpose

Continuously discover quantitative finance, options, risk, GRPO/RL, multi-agent, and
financial RAG papers, grade them for relevance to this lab, and feed accepted
documents into:

1. **Local paper store** — `data/arxiv/*.md` (generated, gitignored)
2. **DocumentIngestionPipeline** — versioned chunks + SHA256 dedupe
3. **Curated RAG corpus** — high-relevance only → `rag_knowledge/research/arxiv/`
4. **Operator status** — `data/runtime/arxiv_ingestion_latest.json`
5. **Durable manifest** — `data/audit/arxiv_ingestion_manifest.json` (gitignored)

## Operator commands

```bash
# One-shot continuous pull
make arxiv-ingest

# Status of last run
make arxiv-ingest-status
# or
.venv/bin/python scripts/arxiv_paper_ingestion.py --status

# Custom query
.venv/bin/python scripts/arxiv_paper_ingestion.py \
  --query "put credit spread options" --max-results 20 --json

# Local continuous job (every 6 hours via launchd)
bash scripts/setup_arxiv_ingest_launchagent.sh install
bash scripts/setup_arxiv_ingest_launchagent.sh status
bash scripts/setup_arxiv_ingest_launchagent.sh run-once
```

## GitHub Actions

Workflow: `.github/workflows/arxiv-paper-ingest.yml`

- **Schedule:** daily 07:15 UTC
- **Manual:** Actions → ArXiv Paper Ingestion → Run workflow
- Promoted curated markdown may open an auto PR under `chore/arxiv-ingest-*`

## Relevance gate

Composite score (0..1):

- Faithfulness / answer relevance / groundedness vs trading+RAG context (lexical metrics)
- Domain boost for tokens such as `option`, `GRPO`, `SPY`, `microstructure`, `RAG`, …

Defaults:

| Gate    | Threshold | Effect                                     |
| ------- | --------- | ------------------------------------------ |
| Ingest  | ≥ 0.18    | Write `data/arxiv/` + pipeline chunks      |
| Promote | ≥ 0.28    | Also write `rag_knowledge/research/arxiv/` |

Low-signal papers are recorded only as skip counts (not RAG pollution).

## Data Science / ML hooks

- **DS:** status JSON + manifest for coverage/recency dashboards
- **ML:** curated abstracts as optional GRPO/research context (not training labels for edge claims)
- **Agentic RAG:** `build_rag_query_index` / `vectorize_rag_knowledge` pick up
  `rag_knowledge/research/**` after `--rebuild-index`

## Hard rules

- Paper mode only; no broker order paths
- Papers ≠ evidence of expectancy or profit
- Do not promote arXiv content into paired trade metrics or kill-criteria math
- Deduplicate by `arxiv_id` in the manifest

## Code map

| Path                                              | Role                              |
| ------------------------------------------------- | --------------------------------- |
| `src/research/arxiv_collector.py`                 | API fetch, score, ingest, promote |
| `scripts/arxiv_paper_ingestion.py`                | CLI                               |
| `scripts/setup_arxiv_ingest_launchagent.sh`       | local continuous install          |
| `ops/launchd/com.igor.trading-arxiv-ingest.plist` | launchd template                  |
| `tests/test_arxiv_collector.py`                   | unit tests (mocked network)       |
