---
name: typesafe-skill-suggest-not-clone
description: >
  Steal TypeSafe skill_suggestion FORMAT (cheap shortlist → Choice/Noul gate →
  top-3 fits rerank) onto Grok/trading skill rosters. Do NOT clone TypeSafe as a
  product. Prefer scripts/typesafe_skill_suggest.py. Auto-invoke on TypeSafe skill
  suggestion, skill roster routing, progressive disclosure skills, context rot from
  loading all skills. Slash: /typesafe-skill-suggest-not-clone.
---

# TypeSafe skill suggestion FORMAT (not a clone)

## Why

Loading hundreds of skills into context causes wrong loads and needless loads.
TypeSafe's cookbook cut wrong loads ~2.3× on Hermes (182 skills) with two System One calls.

## Operator

```bash
# Offline (CI / no key)
.venv/bin/python scripts/typesafe_skill_suggest.py --offline \
  --request "Gate a profitability claim before asserting edge"

# Online Jev (TYPESAFE_API_KEY)
.venv/bin/python scripts/typesafe_skill_suggest.py \
  --request "Run Alpaca paper put-credit dry-run status"
```

Emits JSON including `suggested` (0–1 names) and `suggestion_block` for the system prompt.

## Defaults

Roots: `~/.grok/skills`, `~/.agents/skills`, `trading/skills`.

## Hard don'ts

| NEVER                          | ALWAYS                              |
| ------------------------------ | ----------------------------------- |
| Vendor TypeSafe as a SKU       | Steal progressive disclosure FORMAT |
| Force a skill when gate is low | Allow empty suggestion              |
| Require paid API in CI         | `--offline` token shortlist         |

## Related

- AGENT-651 claim gate
- Official skill: `/typesafe-ai` (installed under `~/.grok/skills/typesafe-ai`)
- Docs: [skill_suggestion cookbook](https://docs.typesafe.ai/cookbooks/skill_suggestion)
