---
name: bogleheads-forum
description: >
  Ingest and participate on Bogleheads.org for the trading repo: public RSS →
  rag_knowledge/bogleheads, Chrome login via Keychain (eazyigz), draft value-first
  replies, optional gated post. Trigger when: Bogleheads, bogleheads.org, forum
  research, three-fund, passive investing ingest, eazyigz. Slash: /bogleheads-forum.
---

# Bogleheads forum automation

**Account:** Keychain `BOGLEHEADS_USERNAME` / `BOGLEHEADS_PASSWORD` (forum user `eazyigz`),
email `iganapolsky@gmail.com`. Google Chrome for login-walled pages.

## Commands

```bash
# Full automate: RSS + promote + Chrome login + enrich + drafts (no live post)
python scripts/bogleheads_ops.py pipeline

# RSS + RAG promote only (no Chrome)
python scripts/bogleheads_ops.py ingest

# Ensure Chrome session logged in
python scripts/bogleheads_ops.py login

# Draft replies only
python scripts/bogleheads_ops.py draft

# Live post ONE draft (explicit gate)
python scripts/bogleheads_ops.py post --confirm-token BOGLEHEADS_POST_CONFIRMED
```

## Outputs

| Path                                            | Purpose                  |
| ----------------------------------------------- | ------------------------ |
| `data/research/bogleheads_latest.json`          | RSS snapshot             |
| `data/research/bogleheads_rag_index.json`       | Promote report           |
| `data/research/bogleheads_pipeline_latest.json` | Last full run            |
| `data/research/bogleheads_drafts/*.json`        | Reply drafts             |
| `rag_knowledge/bogleheads/*.md`                 | Promoted lessons for RAG |

## Rules

1. **Never hardcode the password** — Keychain only.
2. **Default is draft-only** — live post requires `--confirm-token BOGLEHEADS_POST_CONFIRMED`.
3. Replies must be **value-first / Bogleheads norms** (allocation, tax location, simplicity). No spam, no ThumbGate promo, no put-credit sales pitch.
4. Ingested threads are **context for FI/tax/passive** — never treat as spy_put_credit entry signals.
5. Prefer **Chrome** (Igor's profile) over Playwright for login truth.

## Architecture fit

- **Memory plane:** RSS → markdown under `rag_knowledge/bogleheads/` for defended/hybrid retrieve.
- **Strategy plane:** does **not** open risk; research only.
- **Chrome:** `src/integrations/bogleheads/chrome_session.py` via AppleScript JS.
