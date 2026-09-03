# LL-567: Mercury trading-readonly token unused 38 days

**Date**: 2026-09-03
**Severity**: HIGH (4)
**Category**: Investing cash-truth / credential hygiene

## What Happened

Mercury emailed 2026-09-02 that Max Smith KDP LLC API token nickname
`trading-readonly` will be deleted in 7 days after 38 days with no API
activity. `~/.resume_secrets/mercury.json` was missing. The trading GitHub
repo had no `MERCURY_API_TOKEN` secret. No scheduled GET heartbeat existed.
`autonomous-money-cycle.yml` runs a paper Mercury income _simulation_ and
never calls the real bank API.

Official keep-alive is GET `https://api.mercury.com/api/v1/accounts`.
Dashboard login for minting/copying the token is passkey + Android TOTP
(SM-S931U1). The token value is not retrievable after creation.

## Lesson

Read-only Mercury is the LLC investing cash ledger. Alpaca paper equity is a
different account. A token that is never GET-called is deleted. Live ACH
must stay behind `MERCURY_LIVE_TRANSFERS_ENABLED=1`. Do not treat Mercury
cash as Alpaca buying power.

## Prevention

- `scripts/mercury_cli.py heartbeat` issues GET `/accounts` and writes a
  masked receipt that asserts `not_alpaca_buying_power`.
- `.github/workflows/mercury-readonly-heartbeat.yml` every 3 days (fail-closed
  if `secrets.MERCURY_API_TOKEN` is empty).
- Token resolution: env, then Keychain `hermes-fleet`/`MERCURY_API_TOKEN`,
  then the chmod 600 vault file.
- Tests freeze the official `api.mercury.com` host and GET-only workflow.
