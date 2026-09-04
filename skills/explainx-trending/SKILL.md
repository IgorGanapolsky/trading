---
name: explainx-trending
description: >
  Honest ingest of https://explainx.ai/trending into the trading lab: parse
  live page-view scores, map onto existing rails, two-ceiling honesty, planner
  vs executor split. Never auto-install. Never clone ExplainX.
---

# ExplainX trending (trading lab)

```bash
python scripts/explainx_trending.py --fixture tests/fixtures/explainx/trending_snippet.html
python scripts/explainx_trending.py --ceilings
python scripts/explainx_trending.py --harness --command "python scripts/spy_put_credit.py --dry-run"
```

Fail-closed: zero parsed items → `UNAVAILABLE`.

Do not install trending skills/MCP. Do not treat ExplainX score as edge.
Do not invent `/reset-weekly`. A dry-run is not an executed trade.
