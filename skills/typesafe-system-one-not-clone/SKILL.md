---
name: typesafe-system-one-not-clone
description: >
  Steal TypeSafe System One FORMAT (Choice/Score/Noul + confidence-gated routing)
  onto trading evidence honesty. Do NOT clone TypeSafe as a product SKU. Prefer
  scripts/typesafe_claim_gate.py for edge/profit claim gating. Auto-invoke on
  TypeSafe, Jev, console.typesafe.ai/hook, System One, confidence routing, false
  edge claim. Slash: /typesafe-system-one-not-clone.
---

# TypeSafe System One FORMAT (not a clone)

## What we stole

From signed-in `console.typesafe.ai/hook` + docs:

| Primitive              | Returns                     | Trading use                              |
| ---------------------- | --------------------------- | ---------------------------------------- |
| **Noul**               | P(yes)                      | Is this claim supported by ledger facts? |
| **Choice**             | option + probs + confidence | allow / abstain / deny                   |
| **Score**              | weighted level + confidence | harm if asserted falsely                 |
| **Confidence routing** | second axis                 | low confidence → abstain                 |

## Operator path

```bash
# Offline honesty (CI / no key)
.venv/bin/python scripts/typesafe_claim_gate.py --offline \
  --claim "Put credit has proven positive expectancy"

# Live Jev (needs TYPESAFE_API_KEY)
.venv/bin/python scripts/typesafe_claim_gate.py \
  --claim "Put credit has proven positive expectancy"
```

Exit codes: `0` allow · `2` abstain · `3` deny.

## Credentials

- Keychain: service `TYPESAFE_API_KEY`, account `hermes-fleet`
- Fallback file: `~/.resume_secrets/TYPESAFE_API_KEY` (mode 600)
- Console keys: [TypeSafe keys](https://console.typesafe.ai/keys)
- Global retrieve skill: `/typesafe-ai-api`
- Official API skill (Claude): `~/.claude/skills/typesafe-ai` (upstream)

Never print the API key. Never commit it.

## Hard don'ts

| NEVER                                        | ALWAYS                                     |
| -------------------------------------------- | ------------------------------------------ |
| Clone TypeSafe / sell a Jev wrapper SKU      | Steal typed questions + confidence routing |
| Claim edge from paper theater                | Gate profitability claims through this CLI |
| Require paid API for CI                      | `--offline` deterministic heuristic        |
| Dual-edit sibling Typesafe WIP without claim | AGENT-651 worktree + vault claim           |

## Related

- `src/adapters/typesafe_client.py`
- `scripts/typesafe_claim_gate.py`
- `scripts/superpowers_verify_complete.py` (completion evidence)
- LL-651
