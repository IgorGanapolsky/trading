---
name: graphify
description: >
  Official Graphify-Labs/graphify for this trading repo. Query graph.json
  (query/path/explain), never graph.html, never pip install graphify (wrong
  package). Package is graphifyy. Slash: /graphify
---

# Graphify (official)

Upstream: [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify)

```bash
uv tool install graphifyy
python scripts/graphify_ops.py extract          # code-only AST, no LLM
graphify query "what calls TradeGateway"
graphify path "plan_put_credit" "TradeGateway"
graphify explain "TradeGateway"
python scripts/graphify_ops.py fuse "what calls TradeGateway"
```

If `graphify-out/graph.json` exists, answer architecture questions from the graph first. Fuse search hits with 1–2 hop traversal. Do not treat `graph.html` as retrieval. Do not merge into `financial_graph.sqlite`. Details: `docs/GRAPHIFY.md`.
