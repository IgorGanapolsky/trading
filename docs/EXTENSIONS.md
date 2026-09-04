# Extension contract

The core is intentionally small. Integrations are adapters, not a second application framework.

The host owns configuration and secret lookup, validation, timeouts/retries/circuit breakers, safety gates, submission decisions, lifecycle, and cleanup. An integration owns only provider-specific request/response translation behind a narrow protocol under `src/adapters/` or its domain package.

1. Core imports are side-effect free.
2. Initialize optional integrations lazily at a command or service boundary.
3. Keep dependencies in an optional group when the default path does not need them.
4. Validate provider output before trading or safety logic; missing/stale data is blocked or degraded, never invented.
5. An unavailable optional provider must not disable keyword RAG, local tests, or strategy status.
6. Add unit tests for the adapter and a contract test for the host boundary. Network tests are opt-in.
7. Do not create an extension registry until at least two retained adapters need the same lifecycle contract.

This takes the useful part of a plugin architecture—clear ownership and optionality—without introducing a plugin loader the repository does not need.

Official Graphify-Labs/graphify is an optional code-graph adapter (`src/rag/graphify/`, `scripts/graphify_ops.py`). The PyPI package is `graphifyy`; retrieval is `graph.json` via query/path/explain. It must not become a required core import, must not dump into `financial_graph.sqlite`, and must not treat `graph.html` as retrieval. See `docs/GRAPHIFY.md`.
