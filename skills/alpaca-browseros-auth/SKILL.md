---
name: alpaca-browseros-auth
description: "Recover Alpaca paper API access from the authenticated BrowserOS Neo session, store credentials in macOS Keychain without exposing them, and verify broker truth through the trading repo. Use when Alpaca credentials are reported missing, broker inventory is unverified, system_state is stale, or a paper dry-run fails closed."
---

# Alpaca BrowserOS authentication recovery

Use this procedure whenever the trading runtime says Alpaca credentials are missing even though the user is signed into Alpaca in BrowserOS Neo.

## Hard rules

1. Load `skills/trading-ops/SKILL.md` first.
2. Use the authenticated **BrowserOS Neo** profile. Do not ask for credentials and do not use a fresh browser profile.
3. Paper credentials only. Never create, reveal, copy, store, or test live brokerage credentials through this procedure.
4. Never print, OCR, log, screenshot, paste into chat, or write either credential to a repo file.
5. Store each value directly from the clipboard into macOS Keychain, then clear the clipboard.
6. Broker reads are evidence only after an authenticated API request succeeds. A dashboard screenshot is not broker API proof.
7. Never treat a failed refresh as current state. Preserve the last confirmed timestamp and report the refresh as inconclusive.

## Keychain contract

| Value            | Keychain service                  | Account |
| ---------------- | --------------------------------- | ------- |
| Paper API key    | `trading.alpaca.paper.api-key`    | `paper` |
| Paper API secret | `trading.alpaca.paper.api-secret` | `paper` |

The helper scripts never print secret values.

## Recovery workflow

### 1. Confirm the BrowserOS account

In BrowserOS Neo, open Alpaca and confirm all of the following before touching API credentials:

- The banner explicitly says **Paper Trading**.
- Record the paper account identifier and visible equity as non-secret evidence.
- Do not infer that this is the repository's expected account. The API verification below decides that.

### 2. Open Alpaca API keys

Use Alpaca's **API** navigation item. If a paper key already exists, use its reveal/copy controls. Create a new paper key only when the UI proves no reusable paper key exists.

Alpaca may display the secret only once. Store it immediately before navigating away.

### 3. Store values without transcript exposure

For the API key:

1. Click Alpaca's copy button for the paper API key.
2. Run:

```bash
uv run python scripts/store_alpaca_keychain.py api-key --from-clipboard
```

For the secret:

1. Click Alpaca's copy button for the paper API secret.
2. Run:

```bash
uv run python scripts/store_alpaca_keychain.py api-secret --from-clipboard
```

Each command validates a non-empty clipboard, writes the value to Keychain, verifies retrieval by digest, and clears the clipboard. Output contains only service name, length, and a short SHA-256 fingerprint.

### 4. Verify credential presence

```bash
uv run python scripts/run_with_alpaca_keychain.py --check
```

Expected result: both Keychain entries are present. No credential value is displayed.

### 5. Refresh broker truth

Run the canonical read paths with credentials injected only into the child process:

```bash
uv run python scripts/run_with_alpaca_keychain.py -- \
  uv run python scripts/sync_alpaca_state.py
uv run python scripts/run_with_alpaca_keychain.py -- \
  uv run python scripts/sync_closed_positions.py
uv run python scripts/put_credit_cohort_scorecard.py
```

Then verify the actual paper workflow:

```bash
uv run python scripts/run_with_alpaca_keychain.py -- make dry-run
```

A valid completion requires:

- `sync_health.last_successful_sync` advances to the current run.
- The authenticated account identifier matches the intended paper account.
- Inventory was fetched from Alpaca rather than inferred from a local empty list.
- `make dry-run` either produces a valid no-submit plan or fails for a market/risk reason, not `BROKER_INVENTORY_UNVERIFIED`.
- `paper_only=true` and `live_blocked=true` remain unchanged.

## Failure handling

- BrowserOS not connected: start or attach BrowserOS Neo. Do not silently switch profiles.
- Clipboard empty: copy again. Do not create a placeholder.
- Keychain verification mismatch: stop. Do not run the broker client.
- API returns unauthorized: return to the paper API page and rotate only the paper key pair.
- API authenticates to an unexpected account: stop and preserve both account identifiers as non-secret evidence. Do not trade.
- Refresh leaves the prior `last_successful_sync`: report it as failed or inconclusive, never current.

## Why this exists

The Alpaca dashboard can be authenticated while non-browser shells have no exported credentials. This skill bridges that gap without persisting secrets in `.env`, logs, chat, shell history, or Git, and forces a provider-authenticated read before any profitability or readiness claim.
