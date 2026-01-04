# Live Trading Setup Guide

## Overview

This system supports both **paper trading** (simulation) and **live trading** (real money).

**CRITICAL**: Paper and live trading use DIFFERENT API keys and endpoints!

## API Keys (Verified from Alpaca Documentation)

| Mode | Endpoint | API Keys |
|------|----------|----------|
| Paper | `paper-api.alpaca.markets` | Paper-specific keys |
| Live | `api.alpaca.markets` | Live-specific keys |

## How to Generate Live API Keys

1. Log into [Alpaca Dashboard](https://app.alpaca.markets)
2. Click the dropdown in the **top-left corner**
3. Select **"Live Trading"** account (not Paper)
4. Click **"Generate New Keys"**
5. Save both the API Key and Secret Key securely

## How to Enable Live Trading

### Option 1: GitHub Secrets (Recommended for production)

1. Go to your repository: Settings → Secrets → Actions
2. Update these secrets with your **LIVE** keys:
   - `ALPACA_API_KEY` - Your live API key
   - `ALPACA_SECRET_KEY` - Your live secret key
3. Add a new secret:
   - `PAPER_TRADING` = `false`

### Option 2: Manual Workflow Dispatch

1. Go to Actions → Daily Trading Execution
2. Click "Run workflow"
3. Select `trading_mode: live`
4. This will use live mode for that single run only

## Safety Checks

The system includes multiple safety checks:

- Pre-trade smoke tests verify account connectivity
- P/L sanity checks detect zombie mode
- All trades are logged and can be audited

## Switching Back to Paper Trading

To return to paper trading:
1. Update `PAPER_TRADING` secret to `true` (or delete it - defaults to paper)
2. Update `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` with paper keys

## Troubleshooting

### Error: 401 Unauthorized
- You're using paper keys with live endpoint (or vice versa)
- Solution: Ensure keys match the trading mode

### Error: 403 Access Denied
- API keys may have been revoked or are invalid
- Solution: Generate new keys from Alpaca dashboard

## References

- [Alpaca Paper Trading Docs](https://docs.alpaca.markets/docs/paper-trading)
- [Alpaca API Key Guide](https://alpaca.markets/learn/connect-to-alpaca-api)
