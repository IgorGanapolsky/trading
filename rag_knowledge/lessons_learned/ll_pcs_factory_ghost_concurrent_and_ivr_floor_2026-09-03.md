# LL-566: Put-credit factory stalled on ghost concurrent + IVR paper floor

**Date**: 2026-09-03
**Severity**: HIGH (4)
**Category**: Validation cadence / evidence honesty

## What Happened

Weekday `put-credit-validation.yml` was green while no new paper structures opened
for 13 trading days. North Star income stayed 0%.

1. 11:00 ET 2026-09-03 (run 33770724955): broker `pcs_legs=0` after a profit-target
   exit, then `Concurrent put credits 2/2`. Journal still had `status=open` rows,
   one with `exit_reason=broker_reconcile_flat`.
2. 13:00 ET (run 33782397616): book flat, then `IV rank proxy 4.9 < min 5.0`
   while VIX was 14.61 (under the crash veto of 30).
3. `data/audit/grpo_quarantine_status.json` said 35 outcomes / 100% WR /
   UNQUARANTINED because a unit test persisted to the repo path. Health check
   correctly reported GRPO quarantined at 1/30 put-credit rows.

## Lesson

Green cron ≠ an entry. Concurrent occupancy is the live broker book, not the
journal. Paper IVR percentile is a stratification label, not a freeze. Test
fixtures must not write production audit files.

## Prevention

- Occupancy uses `_occupies_concurrent_slot` (terminal exit reasons / `exit_filled_at`
  do not fill 2/2). Reconcile and manage-exits still use `_is_live_journal_row` so
  ghosts and `exit_pending` + `profit_target` get closed.
- When `broker_open_structures` is verified, occupancy **is** that count
  (`max(0, int(broker))`), not `min(journal, broker)`. Close-pending live legs
  still fill 2/2 even if the journal already has `exit_reason=profit_target`.
- Broker structure count is `sum(abs(qty)) // 2` on `pcs_inventory_excluded`.
  `len(excluded) // 2` undercounts two spreads that share a short strike.
- `evaluate_entry_limits(..., broker_open_structures=0)` cannot report 2/2.
- `PUT_CREDIT_MIN_IVR=0`; research preferred IVR 30 remains a soft flag.
  Missing IVR at floor 0 is a soft flag, not a freeze; cover `iv_rank_proxy=None`.
- `GRPOUnquarantineGate(persist=False)` by default.
