# Live Trading Setup Guide

## Overview

This system supports both **paper trading** (simulation) and **live trading** (real money).

**CRITICAL**: Paper and live trading use DIFFERENT API keys and endpoints!

## API Keys (Verified from Alpaca Documentation)

| Mode | Endpoint | API Keys |
|------|----------|----------|
| Paper | `paper-api.alpaca.markets` | Paper-specific keys |
| Live | `api.alpaca.markets` | Live-specific keys |

## Required GitHub Secrets

The system uses **separate secrets** for paper and live trading:

| Secret Name | Description |
|-------------|-------------|
| `ALPACA_PAPER_TRADING_API_KEY` | Paper trading API key |
| `ALPACA_PAPER_TRADING_API_SECRET` | Paper trading secret |
| `ALPACA_BROKERAGE_TRADING_API_KEY` | Live brokerage API key |
| `ALPACA_BROKERAGE_TRADING_API_SECRET` | Live brokerage secret |

## How to Generate API Keys

### Paper Trading Keys
1. Log into [Alpaca Dashboard](https://app.alpaca.markets)
2. Click the dropdown in the **top-left corner**
3. Select **"Paper Trading"** account
4. Click **"Generate New Keys"**
5. Add to GitHub secrets as `ALPACA_PAPER_TRADING_API_KEY` and `ALPACA_PAPER_TRADING_API_SECRET`

### Live Trading Keys
1. Log into [Alpaca Dashboard](https://app.alpaca.markets)
2. Click the dropdown in the **top-left corner**
3. Select **"Live Trading"** account
4. Click **"Generate New Keys"**
5. Add to GitHub secrets as `ALPACA_BROKERAGE_TRADING_API_KEY` and `ALPACA_BROKERAGE_TRADING_API_SECRET`

## How to Enable Live Trading

### Option 1: Workflow Dispatch (Recommended for first test)

1. Go to Actions → Daily Trading Execution
2. Click "Run workflow"
3. Select `trading_mode: live`
4. This will use live mode for that single run only

### Option 2: Scheduled Live Trading

To make the scheduled workflow use live trading:
1. Add secret: `PAPER_TRADING` = `false`

## How Trading Mode Selection Works

The workflow automatically selects the correct API keys:

```yaml
# If trading_mode=live → Uses ALPACA_BROKERAGE_TRADING_API_KEY
# If trading_mode=paper (default) → Uses ALPACA_PAPER_TRADING_API_KEY
```

## Safety Checks

The system includes multiple safety checks:

- Pre-trade smoke tests verify account connectivity
- P/L sanity checks detect zombie mode
- All trades are logged and can be audited
- Live mode displays: "LIVE TRADING MODE - Real money at risk!"

## Switching Back to Paper Trading

To return to paper trading:
1. Delete `PAPER_TRADING` secret (or set to `true`)
2. Run workflow manually with `trading_mode: paper`

## Troubleshooting

### Error: 401 Unauthorized
- You're using paper keys with live endpoint (or vice versa)
- Solution: Ensure keys match the trading mode

### Error: 403 Access Denied
- API keys may have been revoked or are invalid
- Solution: Generate new keys from Alpaca dashboard

### Credentials Missing Error
- One or more required secrets is not set
- Solution: Verify all 4 Alpaca secrets are configured in GitHub

## References

- [Alpaca Paper Trading Docs](https://docs.alpaca.markets/docs/paper-trading)
- [Alpaca API Key Guide](https://alpaca.markets/learn/connect-to-alpaca-api)
