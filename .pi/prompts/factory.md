---
description: One paper factory tick (status, inventory, dry-run, scorecard)
---

# Paper factory tick

Run in order. Do not submit live. Do not treat a dry-run plan as a fill.

1. `scripts/audit_open_inventory.py` — exit 2 means no new risk
2. `scripts/spy_put_credit.py --status`
3. `scripts/spy_put_credit.py --dry-run`
4. `scripts/put_credit_cohort_scorecard.py --json` — report `closed.closed_n` and `kill_criteria.verdict` only
5. If a structure is open, `scripts/spy_put_credit.py --manage-exits --dry-run`

Cite command output. n<30 → `INSUFFICIENT_SAMPLE`. Live stays blocked.
