# LL-658 — Unusual Whales FORMAT steal, not a paid flow product

**Date:** 2026-09-17  
**Severity:** 3 (process)  
**Agent:** grok  
**Issue:** AGENT-657

## Source

[Unusual Whales pricing](https://unusualwhales.com/pricing) (Retail Basic $50 /
Pro $75 / Max $120 monthly; API is a **separate** subscription; free tape is
15-minute delayed). Public agent docs:
[skill.md](https://unusualwhales.com/skill.md).

## What transfers

1. **Predefined-risk P/L receipt** (their options profit calculator FORMAT) —
   credit, max profit, max loss, TP dollars, stop dollars on the Buffett 1-lot
   bull put before entry.
2. **size>OI unusual tag** as a **SPY-only honesty overlay** from the local
   option chain. Soft flag. Not a chase signal.
3. **Anti-hallucination:** do not invent `/api/flow` clients; we do not call
   `api.unusualwhales.com` at all.

## What does not transfer

- Buying the dashboard or API ($50–$750/mo) for a paper lab
- Multi-name whale tape, dark pool, politician trades, prediction markets
- Mr. Whale AI trade finder as an entry engine
- Discord bot SKU

Paper `spy_put_credit` + kill switch stay authoritative.
