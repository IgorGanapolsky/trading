---
name: never-ask-igor-to-dial
description: >
  HARD permanent (CEO 2026-09-16 / LL-638): NEVER tell Igor to dial, call, phone,
  or "you dial TOP_5". Disability — agents own outreach automation. Auto-invoke
  before dial sheets, call-now lists, or phone-first close language.
  Slash: /never-ask-igor-to-dial.
---

# Never ask Igor to dial

**CEO 2026-09-16 (permanent HARD):** agents must not assign human dialing homework.

## Rule

- Never tell Igor to dial, call, or phone anyone.
- Dial cards / TOP_5 files are **agent/automation inventory**, not user homework.
- Trading money / North Star answers stay on trading ledgers unless another business is asked about.
- Never auto-send email.

## Repo enforcement

- Lesson: `rag_knowledge/lessons_learned/ll_638_never_ask_igor_to_dial_trading_scope.md`
- Rule: `.claude/rules/anti-babysitting-ralph-gsd.md`
- Ops brief: `scripts/ops_daily_brief.py` must recommend agent-owned residuals only

## Global mirror

`~/.grok/skills/never-ask-igor-to-dial/SKILL.md` (fleet-wide). This tracked copy keeps fresh checkouts fail-closed.
