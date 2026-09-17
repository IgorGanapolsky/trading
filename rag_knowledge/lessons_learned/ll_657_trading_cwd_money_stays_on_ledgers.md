# LL-657 — Trading-cwd money questions stay on trading ledgers (LL-638 recurrence)

**Date:** 2026-09-17  
**Severity:** CRITICAL (5) — thumbs-down after repeating LL-638  
**Agent:** grok  
**Feedback:** `fb_1789677611624_i9ryki` · memory `mem_1789677611627_y5fk33`

## Mistake

User asked in `IgorGanapolsky/trading`: "what is stopping us from making real money?"

Agent answered from off-repo cash rails, then after "you are working on trading. why do you keep talking about real estate????" explained the skill switch instead of executing a trading residual. Thumbs down followed.

This is a **recurrence of LL-638** (2026-09-16). RAG already recorded the correction; it was not applied.

## Correction

If cwd is this repo and the user did not name another rail:

1. Cite `data/system_state.json`, `data/trades.json`, `data/runtime/strategy_kill_switch.json`, `scripts/spy_put_credit.py --status`.
2. Execute a trading residual (inventory, dry-run/exits, own PR/CI).
3. Do not open other-business call sheets or checkouts.

Paper P/L is not live cash. That fact is stated from the trading ledger — it is not a license to change the topic.

## Prevention

- `~/.grok/skills/trading-scrap-theater-make-money/SKILL.md` scope lock: stay in trading unless the user names another rail.
- Do not treat `/trading-scrap-theater-make-money` as an automatic repo switch on every money word.
