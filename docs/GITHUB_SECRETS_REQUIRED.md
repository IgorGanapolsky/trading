# GitHub Secrets Required

## ✅ Already Configured (Daily Trading)

These secrets are already in use by your daily trading workflow:

| Secret Name | Purpose | Status |
|------------|---------|--------|
| `ALPACA_API_KEY` | Alpaca trading API key | ✅ Required |
| `ALPACA_SECRET_KEY` | Alpaca trading API secret | ✅ Required |
| `POLYGON_API_KEY` | Market data (primary source) | ⚠️ Recommended |
| `FINNHUB_API_KEY` | Economic calendar & earnings | ⚠️ Recommended |
| `ALPHA_VANTAGE_API_KEY` | Fallback market data | ❌ Optional |
| `OPENROUTER_API_KEY` | Multi-LLM sentiment analysis | ⚠️ Recommended |
| `GOOGLE_API_KEY` | ADK orchestrator (if enabled) | ❌ Optional |
| `DAILY_INVESTMENT` | Daily investment amount | ❌ Optional (defaults to 10.0) |

---

## 🆕 Required for IPO Monitor (New Feature)

These secrets are needed for the IPO scraper workflow:

| Secret Name | Purpose | Required? | How to Get |
|------------|---------|-----------|------------|
| `GOOGLE_SHEETS_IPO_SPREADSHEET_ID` | Google Sheets spreadsheet ID with IPO targets | ✅ **YES** | Copy from Google Sheets URL |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` | Path to OAuth2 credentials JSON | ✅ **YES** | Create credentials.json (see below) |
| `GOOGLE_SHEETS_TOKEN_PATH` | Path to store OAuth token | ❌ Optional | Defaults to `data/google_sheets_token.json` |
| `GOOGLE_SHEETS_IPO_RANGE` | Sheet range to read | ❌ Optional | Defaults to `Target IPOs!A2:E100` |
| `SLACK_BOT_TOKEN` | Slack bot token for alerts | ❌ **OPTIONAL** | IPO monitor works without Slack |
| `SLACK_IPO_CHANNEL` | Slack channel for alerts | ❌ Optional | Defaults to `#trading-alerts` |

**Note**: IPO Monitor works without Slack - it will just print alerts to logs instead of sending Slack messages.

---

## 🔧 Required for Dialogflow Webhook (Cloud Run)

| Secret Name | Purpose | Required? | How to Get |
|------------|---------|-----------|------------|
| `GCP_SA_KEY` | Service account JSON for Cloud Run deploy | ✅ **YES** | See below |

**Setup GCP_SA_KEY:**
1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=igor-trading
2. Create service account: `github-actions-deployer`
3. Grant roles: `Cloud Run Admin`, `Storage Admin`, `Service Account User`
4. Create JSON key and add entire contents as `GCP_SA_KEY` secret

---

## 🔧 Optional: MCP Integrations

These secrets enable full MCP functionality (Gmail, Slack, Google Sheets):

| Secret Name | Purpose | Required? | How to Get |
|------------|---------|-----------|------------|
| `GMAIL_CREDENTIALS_PATH` | Gmail OAuth2 credentials | ❌ Optional | Google Cloud Console |
| `GMAIL_TOKEN_PATH` | Gmail token storage path | ❌ Optional | Defaults to `data/gmail_token.json` |
| `SLACK_BOT_TOKEN` | Slack Web API token | ⚠️ If using Slack | Create Slack app |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` | Google Sheets OAuth2 credentials | ⚠️ If using IPO Monitor | Google Cloud Console |
| `GOOGLE_SHEETS_TOKEN_PATH` | Google Sheets token path | ❌ Optional | Defaults to `data/google_sheets_token.json` |

---

## 📋 Quick Setup Guide

### For IPO Monitor (Minimum Required - NO SLACK NEEDED)

1. **Create credentials.json**:
   ```bash
   # Run the setup script:
   ./scripts/setup_google_sheets_credentials.sh

   # Or create manually: data/google_sheets_credentials.json
   {
     "installed": {
       "client_id": "your-client-id.apps.googleusercontent.com",
       "client_secret": "your-client-secret",
       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
       "token_uri": "https://oauth2.googleapis.com/token",
       "redirect_uris": ["http://localhost:8080/"]
     }
   }
   ```

2. **Get Client ID and Secret from Google Cloud Console**:
   ```bash
   # 1. Go to: https://console.cloud.google.com/
   # 2. Create project or select existing
   # 3. Enable "Google Sheets API" and "Google Drive API"
   # 4. Go to: APIs & Services → Credentials
   # 5. Create OAuth 2.0 Client ID (Desktop app type)
   # 6. Copy Client ID and Client Secret
   ```

3. **Create Google Sheet**:
   ```bash
   # 1. Create a Google Sheet with "Target IPOs" tab
   # 2. Add columns: Ticker (A), Company Name (B), Expected Date (C), Status (D), Notes (E)
   # 3. Get spreadsheet ID from URL: https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
   ```

4. **Add to GitHub Secrets**:
   ```bash
   # Go to: https://github.com/IgorGanapolsky/trading/settings/secrets/actions
   # Add these 2 secrets (Slack is OPTIONAL):
   GOOGLE_SHEETS_IPO_SPREADSHEET_ID=<your_spreadsheet_id>
   GOOGLE_SHEETS_CREDENTIALS_PATH=data/google_sheets_credentials.json

   # Optional (for Slack alerts):
   # SLACK_BOT_TOKEN=xoxb-your-token-here
   ```

---

## 🎯 Priority Order

### Must Have (System Won't Work Without)
- ✅ `ALPACA_API_KEY`
- ✅ `ALPACA_SECRET_KEY`

### Should Have (Daily Trading Works Better)
- ⚠️ `POLYGON_API_KEY` (reliable market data)
- ⚠️ `FINNHUB_API_KEY` (economic calendar)
- ⚠️ `OPENROUTER_API_KEY` (sentiment analysis)

### Nice to Have (New Features)
- 📈 IPO Monitor: `GOOGLE_SHEETS_IPO_SPREADSHEET_ID`, `GOOGLE_SHEETS_CREDENTIALS_PATH` (Slack optional)
- 📧 Gmail Integration: `GMAIL_CREDENTIALS_PATH` (not needed)
- 💬 Slack Integration: `SLACK_BOT_TOKEN` (optional - IPO monitor works without it)

---

## 🔍 How to Check What You Have

Run this in your repository:

```bash
# Check which secrets are configured (requires gh CLI)
gh secret list
```

Or check manually:
1. Go to: `https://github.com/IgorGanapolsky/trading/settings/secrets/actions`
2. View all configured secrets

---

## ⚠️ Important Notes

1. **IPO Monitor is Optional**: Daily trading will work fine without IPO monitor secrets
2. **MCP Integrations are Optional**: All MCP features gracefully degrade if secrets missing
3. **Secrets Never Expire**: Once set, they persist until you delete them
4. **Security**: Never commit secrets to code - always use GitHub Secrets

---

## 🚀 Quick Start (Minimum)

If you just want to get started quickly:

**Required** (already have):
- ✅ `ALPACA_API_KEY`
- ✅ `ALPACA_SECRET_KEY`

**For IPO Monitor** (add these 2 - NO SLACK NEEDED):
- `GOOGLE_SHEETS_IPO_SPREADSHEET_ID` (from Google Sheets URL)
- `GOOGLE_SHEETS_CREDENTIALS_PATH` (create credentials.json file)

**Slack is OPTIONAL** - IPO monitor will work fine without it (just prints to logs).

Everything else is optional and can be added later!
