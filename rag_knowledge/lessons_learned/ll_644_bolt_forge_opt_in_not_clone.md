# LL-644 — Bolt Forge FORMAT: opt-in export, never train-by-default

Sources: [Bolt Forge support](https://support.bolt.new/account-and-subscription/bolt-forge) and [TNS training-data catch](https://thenewstack.io/bolt-forge-training-data/) (2026-09-15)

## Steal (FORMAT)

1. **Explicit per-session opt-in** before any share. Not buried in a ToS.
2. **Strip secrets and test against seeded data** before a dump leaves the box.
3. **Operator vs research pools.** Production (Standard/Max analog: spy_put_credit) is not the training pool.
4. **Leaving stops NEW collection.** Already-exported rows are not auto-deleted — say so.

## Do not

- Clone Bolt Forge, Lite $9, or 50x compute bait.
- Send traces to Arcee or any trainer.
- Treat their 91% Bolt Build Index as our metric.
- Export operator/live sessions by default.

## Ship

`scripts/session_export_gate.py` export|status. Default DENY. Local file only.

## Cash

Ops/eval only. Commercial fee-yes remains separate.
