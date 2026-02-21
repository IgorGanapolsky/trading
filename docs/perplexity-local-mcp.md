# Perplexity Local MCP: Read-Only Trading Snapshot

This repo now ships a local read-only snapshot command:

```bash
python3 scripts/perplexity_local_mcp_snapshot.py --format json
```

It returns compact operational state from local files:
- latest system state timestamp and age
- trading equity / daily P&L / position count
- latest verification report snapshot
- RAG lesson index freshness
- latest publication status summary
- stale/missing health flags

## Why this is high ROI

- Fast local context for Perplexity desktop queries.
- No write-side effects.
- Helps avoid stale-data hallucinations by exposing exact freshness.

## Anchor vs Local Browser Pilot

Use the pilot runner to compare reliability/cost before production cutover:

```bash
python3 scripts/run_browser_automation_pilot.py \
  --providers local,anchor \
  --runs-per-task 1 \
  --summary-out data/analytics/browser_automation_pilot_latest.json \
  --jsonl-out data/analytics/browser_automation_pilot_history.jsonl
```

With no `ANCHOR_API_KEY`, Anchor runs are recorded as `skipped`, not fabricated.

## Suggested Perplexity local connector command

Configure a local command connector to run:

```bash
python3 /absolute/path/to/trading/scripts/perplexity_local_mcp_snapshot.py --format json
```

Then ask Perplexity things like:
- "What is the latest trading sync freshness?"
- "Is the RAG index stale?"
- "What was the latest verified daily P/L?"

