---
id: LL-654
title: Colab Pro+ cohort rail without new spend
date: 2026-09-17
severity: 3
tags: [colab, pro-plus, cohort, agent-654]
---

## LL-654 — Colab signup → use Pro+, do not buy again

### Context

Operator opened
[Colab signup](https://colab.research.google.com/signup)
while signed in as `iganapolsky@gmail.com`. Home UI shows
**Colab Pro+ home**. Pay-As-You-Go purchase buttons were disabled.

### Transfer

- Pack ledgers with `scripts/colab_cohort_pack.py`
- Notebook: `notebooks/put_credit_cohort_colab.ipynb`
- Install free CLI: `uv tool install google-colab-cli` (uses existing Pro+)
- Never auto-buy compute units

### Prevention

Skill `skills/google-colab-trading-cohort` + tests for packer.
