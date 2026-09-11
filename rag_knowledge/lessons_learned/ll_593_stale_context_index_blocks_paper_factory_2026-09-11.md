# LL-593: Stale context_engine_index froze paper put-credit factory

**Date**: 2026-09-11
**Severity**: HIGH (4)
**Category**: Validation cadence / evidence honesty

## What Happened

Weekday `put-credit-validation.yml` was green while `--execute-paper` found a
structure and then died on `MANDATORY GATE BLOCKED: Trade blocked by stale
context: Stale context indexes detected: context_engine_index`. The entry step
swallows non-zero exit (`|| true`), so GitHub stayed success and n→30 did not
grow.

Evidence:

- Run 34614102162 (2026-09-11T15:06Z): `PUT_CREDIT_MIN_IVR=0`, `DRY_RUN=false`,
  regime only a soft flag (`IVR 24.1 < research preferred 30`), then stale
  `context_engine_index` veto. `submitted: 0`.
- Run 34493454144 (2026-09-10T15:07Z): same error.

The 24h context-index SLO is a RAG freshness check, not a risk control. Policy
expectancy is already skipped for controlled one-lot paper validation; context
freshness was not.

## Lesson

Green cron ≠ an entry. A stale `context_engine_index` must not freeze
`spy_put_credit` paper openings. Live and non-validation openings stay
fail-closed on that SLO.

## Prevention

- `validate_trade_mandatory` skips the context-freshness hard-block when
  `_is_controlled_paper_validation_context` is true **and** strategy is
  `spy_put_credit`.
- Tests: `test_stale_context_skips_for_controlled_paper_put_credit` and
  `test_stale_context_still_blocks_non_validation_put_credit`.
- Cadence alarm (`scripts/check_entry_cadence.py`) still owns silent stall.
