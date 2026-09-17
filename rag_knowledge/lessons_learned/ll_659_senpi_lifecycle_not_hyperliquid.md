# LL-659 — Senpi 5-phase FORMAT, not a Hyperliquid agent

**Date:** 2026-09-17  
**Severity:** 3  
**Agent:** grok  
**Issue:** AGENT-658

## Source

[Senpi](https://senpi.ai) — AI quant on Hyperliquid. Logged-in 2026-09-17 as
Google `iganapolsky@gmail.com` (profile SmoothBronzeKey, Pro free trial,
**$10 credits left**, wallet **$0.00**, "Fund your wallet to start trading").

Capabilities: Discover → Decide → Execute → Manage → Exit. Scanner proposes;
runtime disposes. Two-phase DSL exits. 260+ perps. Do not clone.

## What transferred

Named five-phase receipt on **local** `spy_put_credit` ledgers:

- DISCOVER = SPY only (universe 1)
- DECIDE = kill-switch confluence (paper_only + live_blocked)
- EXECUTE = `submitted: 0` (no wallet, no Hyperliquid)
- MANAGE = journal open / exit_pending + Buffett stop 200% / TP 50% / 30 DTE
- EXIT = paired n toward 30; edge claim stays false

CLI: `python scripts/put_credit_lifecycle.py --json`

## What did not transfer

- Funding the Senpi wallet / depositing USDC
- Subscribe / buy credits
- Copy-trade Hyperliquid, 80 strategy templates, `@senpi-ai/runtime`
- Treating $10 trial credits as trading capital
- Multi-name "what's moving" as an entry engine
