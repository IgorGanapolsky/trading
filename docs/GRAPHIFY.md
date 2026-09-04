# Graphify (official Graphify-Labs/graphify)

This repository uses **[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify)**, not a lookalike.

| Fact         | Value                                                                                   |
| ------------ | --------------------------------------------------------------------------------------- |
| PyPI package | `graphifyy` (double-y). Other `graphify*` packages are unaffiliated.                    |
| CLI          | `graphify`                                                                              |
| Install      | `uv tool install graphifyy` then `graphify install`                                     |
| Retrieval    | `graphify query`, `graphify path`, `graphify explain` against `graphify-out/graph.json` |
| Edge tags    | `EXTRACTED` (in source) / `INFERRED` (resolved) / `AMBIGUOUS`                           |
| Code extract | local tree-sitter AST, no LLM (`graphify extract . --code-only --no-cluster`)           |
| HTML         | `graphify-out/graph.html` is visualization only — never retrieval                       |
| Git          | `graphify-out/` stays gitignored (LL-349). Rebuild locally.                             |

Financial Graph RAG (`src/rag/graph`, SQLite lessons/trades/strategies) is a **different** graph. Do not dump Graphify AST nodes into `financial_graph.sqlite`. Do not clone Cosmos/Gremlin.

```bash
python scripts/graphify_ops.py status --json
python scripts/graphify_ops.py extract
python scripts/graphify_ops.py query "what calls TradeGateway"
python scripts/graphify_ops.py path plan_put_credit TradeGateway
python scripts/graphify_ops.py explain TradeGateway
python scripts/graphify_ops.py fuse "what calls TradeGateway"
make graphify-check
```

`.graphifyignore` is merged with `.gitignore` and can only exclude more files.

Graphify AST edges have **no validity window**. Time filters belong on the financial graph, not on AST `imports`/`calls`.
