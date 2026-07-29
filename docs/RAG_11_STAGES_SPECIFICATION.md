# 🔬 Agentic RAG: 11-Stage Production Specification & Diagnostic Framework

This document defines the 11 core stages of our production **Agentic RAG System** (`src/rag/`), detailing the rationale, failure modes, and quantitative health metrics for each stage.

---

### 1. Documents (`rag_knowledge/lessons_learned/*.md`)
- **Why does it exist?**: Canonical, immutable knowledge ledger storing 370 post-mortem trade studies, risk rules, and empirical lessons.
- **What can go wrong?**: Stale directives, duplicated lesson IDs, or missing structural frontmatter.
- **How to measure working status**: `len(rag.lessons) == 370`, zero duplicate `lesson_id` entries, 100% valid YAML header parsing.

---

### 2. Document Parsing (`LessonsLearnedRAG`)
- **Why does it exist?**: Extracts structured metadata (title, severity, tags, timestamp) from raw markdown files into memory objects.
- **What can go wrong?**: Malformed YAML frontmatter causing silent field drop or parsing exceptions.
- **How to measure working status**: 100% non-null title and severity attributes across all loaded lessons (`test_lessons_learned_rag_smoke.py`).

---

### 3. Data Cleaning (`src/rag/lessons_learned_rag.py`)
- **Why does it exist?**: Sanitizes document text, stripping accidental API keys, tokens, or formatting noise before vector embedding.
- **What can go wrong?**: Secret leak into vector database or over-aggressive scrubbing that removes technical code context.
- **How to measure working status**: `no_embedded_sk_strings` scanner test passing (`0` secret patterns found in `.claude/memory/lancedb`).

---

### 4. Chunking (`DocumentAwareRAG`)
- **Why does it exist?**: Segments lessons into semantic blocks preserving complete markdown headers and code blocks without mid-sentence cuts.
- **What can go wrong?**: Truncation of critical risk rules (e.g. 50% profit target rule cut off across chunk boundary).
- **How to measure working status**: `VectorFlatteningBenchmark` precision score $\ge 0.95$.

---

### 5. Metadata Extraction (`src/memory/document_aware_rag.py`)
- **Why does it exist?**: Attaches category, severity level (`CRITICAL`, `HIGH`), and tag metadata to each vector embedding record.
- **What can go wrong?**: Untagged documents defaulting to generic categories, reducing metadata filtering efficacy.
- **How to measure working status**: 100% of indexed LanceDB rows contain valid `lesson_id` and `category` fields.

---

### 6. Embeddings (`BAAI/bge-small-en-v1.5`)
- **Why does it exist?**: Converts text chunks into 384-dimensional dense semantic vector representations for similarity search.
- **What can go wrong?**: Dimension mismatch, high embedding latency, or out-of-vocabulary trading jargon degradation.
- **How to measure working status**: Cosine similarity $> 0.80$ between semantic synonyms (e.g., "put credit" $\leftrightarrow$ "short put spread").

---

### 7. Vector Database (**LanceDB** @ `.claude/memory/lancedb`)
- **Why does it exist?**: On-disk C++ vector database delivering sub-10ms nearest-neighbor vector retrieval.
- **What can go wrong?**: Index corruption, stale disk state, or disk read I/O bottlenecks.
- **How to measure working status**: `system_health_check.py` RAG check returns `✅ RAG System: OK` (370 indexed vectors).

---

### 8. Retrieval (`LessonsLearnedRAG.search()`)
- **Why does it exist?**: Queries LanceDB for top-10 candidate lessons matching incoming agentic trading intent.
- **What can go wrong?**: Retrieval recall failure (missing high-severity risk rules during market regime switches).
- **How to measure working status**: Retrieval recall $\ge 98.0\%$ across 185 trace-mined eval benchmark queries.

---

### 9. Reranking (`RAGReranker` @ `src/rag/rag_reranker.py`)
- **Why does it exist?**: Applies Cross-Encoder keyword weighting and term-overlap re-scoring to push exact risk rules to top-3 slots.
- **What can go wrong?**: Keyword over-weighting suppressing semantic relevance or high reranking latency.
- **How to measure working status**: **0.04 ms rerank latency**, top-1 relevance score $\ge 1.80$ for risk queries (`LL-323`, `LL-301`).

---

### 10. Prompt Assembly (`Pre-flight Audit`)
- **Why does it exist?**: Injects reranked top-k lessons directly into LLM system prompts before trade execution decisions.
- **What can go wrong?**: System context window overflow or prompt injection bypassing retrieved risk constraints.
- **How to measure working status**: 100% of generated trade decision prompts contain required retrieved safety context.

---

### 11. Structured Output (`src/mcp/governance/`)
- **Why does it exist?**: Enforces Pydantic schema validation (`OrderRequest`, `PositionSizeRequest`) on LLM output to guarantee valid JSON/params.
- **What can go wrong?**: Unvalidated LLM parameters submitting illegal strikes or oversized orders.
- **How to measure working status**: `test_mcp_governance.py` passing 100% (`0` unvalidated requests allowed).
