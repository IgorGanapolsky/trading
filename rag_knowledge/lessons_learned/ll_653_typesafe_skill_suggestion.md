---
id: LL-653
title: TypeSafe skill-suggestion FORMAT for large skill rosters
date: 2026-09-17
severity: 4
tags: [typesafe, skill-suggestion, progressive-disclosure, agent-653]
---

## LL-653 — skill suggestion from TypeSafe Playground

### Context

Operator signed into the
[TypeSafe Playground](https://console.typesafe.ai/playground)
and pointed at the skill-install tip plus helpdesk triage example.
Playground run (jev-latest): wifi ticket → `it_helpdesk` 100%,
`ticket-status` 76% over a 200-option Choice in ~300ms.

### Transfer

Cookbook
[skill_suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion)
FORMAT: cheap shortlist → gate Nouls → top-3 fits rerank → at most one skill name.

Installed official skill to `~/.grok/skills/typesafe-ai`.
Repo CLI: `scripts/typesafe_skill_suggest.py` (offline + online).

### Prevention

- Skill: `skills/typesafe-skill-suggest-not-clone`
- Tests: `tests/test_typesafe_skill_suggest.py`
- Never claim commercial A+ from this ops rail alone
