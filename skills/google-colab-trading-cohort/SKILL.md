---
name: google-colab-trading-cohort
description: >
  Use existing Google Colab Pro+ (iganapolsky@gmail.com) for put-credit cohort
  scorecards. Never buy compute units. Pack ledgers via scripts/colab_cohort_pack.py
  and open notebooks/put_credit_cohort_colab.ipynb. Auto-invoke on Colab signup,
  Colab Pro, GPU offload, cohort notebook. Slash: /google-colab-trading-cohort.
---

# Colab Pro+ trading cohort rail

## Verified

- Colab home UI label: **Colab Pro+ home** (signed in as `iganapolsky@gmail.com`)
- Signup page Pay-As-You-Go buttons disabled (already subscribed)
- **Never** click Pro / Pro+ purchase or `colab pay` unless CEO authorizes spend same turn

## Operator

```bash
.venv/bin/python scripts/colab_cohort_pack.py --json
# Open notebook (after merge to main, or upload pack JSON in Colab):
# https://colab.research.google.com/github/IgorGanapolsky/trading/blob/main/notebooks/put_credit_cohort_colab.ipynb
```

Optional CLI (installed via `uv tool install google-colab-cli`):

```bash
colab version
colab new --gpu t4
colab upload data/audit/colab_packs/.../put_credit_cohort.json /content/put_credit_cohort.json
colab exec -f notebooks/put_credit_cohort_colab.ipynb
colab stop
```

## Hard don'ts

| NEVER                                  | ALWAYS                                  |
| -------------------------------------- | --------------------------------------- |
| Auto-buy compute units / upgrade plans | Use existing Pro+ allocation            |
| Claim edge from Colab charts           | Cite `kill_verdict` from scorecard JSON |
| Leave GPU runtimes idle                | `colab stop` / disconnect runtime       |

## Related

- `scripts/put_credit_cohort_scorecard.py`
- Fleet skill: `google-colab-pro-runner` (Claude global)
- Colab CLI: [googlecolab/google-colab-cli](https://github.com/googlecolab/google-colab-cli)
