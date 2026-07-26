# Weekend prep plan → Monday open (2026-07-25 → 2026-07-27)

**Goal:** process ready for paper validation Monday. **Not** live capital. **Not** “make money every day.”

## Already done (Sat)

- [x] Fresh Alpaca paper/live sync (paper ~$94,090; live $0)
- [x] Inventory audit clean (8 legs, 1 residual IC + 2 PCS)
- [x] Put-credit manage dry-run: both **hold** (not at TP/SL/7 DTE)
- [x] Residual IC dry-run: **hold** (~18% of max profit, DTE 27)
- [x] Journal reconcile: 2 filled ↔ 2 journaled
- [x] Counterfactuals stamped on open PCS journal rows
- [x] Ralph hourly LaunchAgent loaded (`com.igor.trading.ralph-gsd-profit-tick`)
- [x] Greptile safety PR **#4285** open (tests green; fixing Sonar + new Greptile P1s)
- [x] Cohort: 0 closed / 30; concurrent **2/2** full; live_blocked

## Do rest of weekend (priority order)

### P0 — Land safety before Monday runtime

1. **Merge #4285** once Run All Tests green again after entry-only/ET/juror-opt-in fix  
   - Unset bad `GH_TOKEN` if 401 (`unset GH_TOKEN GITHUB_TOKEN`)
2. **Pull main** into primary checkout so Monday scripts match merged gates
3. **Do not** enable live, Mercury funding, or `MULTI_MODEL_JUROR_ENABLED` without a real secondary model

### P0 — Monday execution automation (paper only)

Today Ralph only **dry-runs**. Monday needs **real paper manage** during RTH:

| Time (ET) | Action |
|---|---|
| 09:20 | `sync_alpaca_state.py` (GH pre-market-sync is 09:25) |
| 09:25 | `audit_open_inventory.py` — must exit 0 |
| 09:30–15:45 every 30m | `spy_put_credit.py --manage-exits` (**no** `--dry-run` on paper) |
| same | residual IC manage dry → only guardian/exit path if should_exit |
| after free slot | `spy_put_credit.py --dry-run` then `--execute-paper` if concurrent&lt;2 + regime OK |
| never | `--live` / Mercury deposit |

Wire one of:
- GH workflow schedule Mon–Fri 14:00–20:00 UTC every 30m calling manage-exits paper, **or**
- LaunchAgent StartCalendarInterval market hours

### P1 — Hygiene (reduces Monday agent collisions)

1. Remove **merged** worktrees: hard-rag, max-daily, regime, ralph-gsd, sync-closed (already on main)
2. Keep only: primary + `fix-greptile-p1-weekend-prep` until #4285 merges
3. Discard or commit **only intentional** research under `data/research/` — do not commit runtime JSON noise
4. Confirm no `GH_TOKEN` env override breaks `gh` on Monday

### P1 — Regime data quality

- SPY 200-DMA soft-flag fails: SIP subscription message  
- Decide: accept soft-flag only (current) **or** fund SIP **or** use free daily bars path before treating trend as hard gate

### P2 — Throughput (only after process solid)

- Concurrent still **2/2** → no new entry until a close  
- Do **not** raise max concurrent this weekend without CEO policy change  
- Focus Monday: manage exits so sample can grow toward n=30

### Explicitly NOT this weekend

- Deposit real money / Mercury live funding  
- Re-enable iron condor entries  
- Claim profitability  
- Force-close residual IC outside guardian rules  
- Wire live juror with fake AGREE  

## Monday open checklist (copy)

```bash
unset GH_TOKEN GITHUB_TOKEN
cd /Users/igorganapolsky/workspace/git/igor/trading
git fetch origin main && git checkout main && git pull --ff-only
.venv/bin/python scripts/sync_alpaca_state.py
.venv/bin/python scripts/audit_open_inventory.py          # must clean
.venv/bin/python scripts/spy_put_credit.py --manage-exits  # paper exits
.venv/bin/python scripts/put_credit_cohort_scorecard.py
.venv/bin/python scripts/spy_put_credit.py --regime-status
.venv/bin/python scripts/spy_put_credit.py --dry-run       # only if concurrent < 2
# if dry-run allowed: --execute-paper (never --live)
```

## Success criteria for Monday (honest)

- Inventory stays clean  
- Open PCS managed under TP 25% / stop 200% / 7 DTE / min-hold  
- Zero live orders  
- Prefer ≥1 clean paper close or documented hold reason  
- Still **not** deposit-ready until n≥30 + expectancy>0 + PF>1  
