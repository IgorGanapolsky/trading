# LL-669 — Put-credit journal and protocol must stamp the live profile

**Date:** 2026-09-19
**Severity:** 4
**Issue:** AGENT-669
**Evidence:** After AGENT-664/665/667 operator-copy heals, `scripts/spy_put_credit.py` still hardcoded `profile_name: spy-put-credit` on `_record_entry` and reconstructed fills. Kill switch `active_profile` is `spy-put-credit-buffett`. `trade_evidence._put_credit_protocol_reasons` rejected any other name as `wrong_profile` and required 30–45 DTE, so a correctly stamped Buffett close (45–70 DTE) would never enter kill-gate n.

## Mistake

Updating operator copy and scorecard `RISK_FRAMEWORK` while leaving the durable journal writer and protocol validator pinned to the killed lab profile. Buffett n stays 0 even after future paired closes.

## Fix

Stamp `_load_profile().name` on new journal writes. Protocol-validate against `PUT_CREDIT_PROFILE_REGISTRY` for the row's stamp: legacy `spy-put-credit` keeps 30–45 DTE / 0.10–0.22 Δ; `spy-put-credit-buffett` uses 45–70 DTE / 0.10–0.20 Δ.

Do **not** rewrite historical `data/put_credit_entries.json` notes. Open `PCS_261023` stays `spy-put-credit` until it closes; it is not Buffett-cohort.

## Verify

`pytest tests/test_trade_evidence.py tests/test_active_strategy.py::test_put_credit_journal_uses_unique_order_identity tests/test_active_strategy.py::test_reconcile_put_credit_entries_recovers_exact_filled_structure`
