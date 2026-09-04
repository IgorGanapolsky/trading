# ExplainX trending — honest ingest (not a clone)

Linear: [AGENT-573](https://linear.app/igorganapolsky/issue/AGENT-573/honest-explainx-trending-ingest-two-ceiling-plannerexecutor-split)

Source: <https://explainx.ai/trending>

explainx.ai ranks **their** page views. That ranking is not trading ROI, not a
skill installer, and not a reason to clone their registry.

## Operator

```bash
python scripts/explainx_trending.py --fixture tests/fixtures/explainx/trending_snippet.html
python scripts/explainx_trending.py --fetch
python scripts/explainx_trending.py --ceilings
python scripts/explainx_trending.py --harness --command "python scripts/spy_put_credit.py --dry-run"
```

Zero parsed items → JSON `status=UNAVAILABLE` and exit 2.

## What we stole (FORMAT only)

1. **Rank by parsed `score`.** Never invent TF-IDF ROI. Do not dual-edit
   `mac-yolo-safeguards/tools/explainx-trending-rag-engine.js`.
2. **`/limit-reset` honesty.** Daily structure cap (session analog) is not the
   put-credit cohort gate (n=30). Resetting the daily cap does not increase
   cohort n, clear the kill switch, or unblock live. `/reset-weekly` does not
   exist.
3. **Planner vs executor.** Commerce-agent shopping/merchant split maps to
   dry-run planner vs TradeGateway executor. Different evals. Not a checkout
   clone. Anthropic cart-size figures are not ours.

## What we skip

Workshops, bootcamps, courses, third-party skills/MCP/agents, spy-satellite
simulators, RSA factoring, model-launch blogs. Never auto-install.

## Out of scope

- Makefile / `docs/EXTENSIONS.md` / `skills/trading-ops` (AGENT-571)
- SuperMemory adapter (AGENT-572)
- Live capital
