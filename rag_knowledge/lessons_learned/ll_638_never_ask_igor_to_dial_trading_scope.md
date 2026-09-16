# LL-638 — Never ask Igor to dial; trading money answers stay in trading

**Date:** 2026-09-16  
**Severity:** 5 (HARD permanent preference + scope failure)  
**Agent:** grok

## Mistake

On "are we winning? making real money? reaching our north star?" asked in the
`trading` workspace, the agent:

1. Diverted into RealEstate / agency cash rails and pasted a **TOP_5 dial list
   with an imperative for Igor to call**.
2. Ignored that Igor has a **disability** and the AI business exists so agents
   do not assign human dialing homework.

## Correction

1. **Never** tell Igor to dial, call, or phone anyone. Skill:
   `~/.grok/skills/never-ask-igor-to-dial/SKILL.md` (`/never-ask-igor-to-dial`).
2. In the trading repo, money / North Star answers cite **trading ledgers only**
   (`data/system_state.json`, `data/trades.json`, kill switch) unless Igor
   explicitly asks about another business.

## Trading truth at incident (do not invent)

- North Star: $6,000/mo after-tax — progress **0%**
- Paper equity ~$94.1K; live **$0** / `live_blocked`
- Paired P/L **−$7,587** (n=164, PF 0.18) — paper, not cleared income
- Put-credit cohort n=3 — below live gate

## Prevention

- Global skill auto-invoke on dial / call-sheet / TOP_5 close language
- Rule line in `.claude/rules/anti-babysitting-ralph-gsd.md` updated
