# Alpaca Authentication Diagnostic - January 9, 2026

## Problem

Paper trading has been broken for 4 days. Pre-market health check fails with:
```
❌ Alpaca API: FAILED - Initialization failed: "message": "unauthorized."
```

## What We KNOW (Verified with Evidence)

✅ **GitHub Secrets Exist**
- `ALPACA_PAPER_TRADING_5K_API_KEY` - exists, updated "yesterday"
- `ALPACA_PAPER_TRADING_5K_API_SECRET` - exists, updated "yesterday"
- Verified via screenshots from GitHub Secrets page

✅ **Workflow Configuration is Correct**
- `.github/workflows/daily-trading.yml` line 621-622 correctly maps:
  - `secrets.ALPACA_PAPER_TRADING_5K_API_KEY` → `ALPACA_API_KEY`
  - `secrets.ALPACA_PAPER_TRADING_5K_API_SECRET` → `ALPACA_SECRET_KEY`
- No old secret references found

✅ **Health Check Code is Correct**
- `scripts/pre_market_health_check.py` line 71: Defaults to paper trading
- `src/core/alpaca_trader.py` line 168: Creates TradingClient with `paper=True`
- Environment variables are read correctly

✅ **Alpaca API Returns "unauthorized"**
- This is Alpaca's direct API response, not a code error
- Error occurs at line 174 of alpaca_trader.py: `account = self.trading_client.get_account()`

## What We NEED TO VERIFY (CEO Action Required)

❓ **Are the credentials actually valid?**

The secrets exist in GitHub, but Alpaca API rejects them. Possible causes:

1. **Keys are for LIVE account instead of PAPER**
   - Paper trading requires paper-specific keys
   - Live keys will return "unauthorized" when used with `paper=True`

2. **Keys were regenerated after adding to GitHub**
   - If you regenerated keys in Alpaca dashboard after adding to GitHub
   - Old keys become invalid immediately

3. **Typo when copying to GitHub Secrets**
   - Extra space at beginning/end
   - Missing character
   - Wrong key copied to wrong secret name

## How to Verify Credentials (Testing Steps)

### Option 1: Test Locally (Recommended)

```bash
# 1. Get your paper trading keys from Alpaca dashboard
#    Go to: https://app.alpaca.markets/paper/dashboard/overview
#    Click: "View API Keys" or "Regenerate"

# 2. Set environment variables with your keys
export ALPACA_API_KEY="your_paper_api_key_here"
export ALPACA_SECRET_KEY="your_paper_secret_key_here"

# 3. Run the test script
python3 scripts/test_alpaca_credentials_local.py
```

**Expected results:**
- ✅ SUCCESS: Keys are valid → Update GitHub Secrets with same keys
- ❌ FAILED: Keys are invalid → Regenerate new keys from Alpaca

### Option 2: Manual Workflow Trigger with Logging

```bash
# Trigger workflow manually to see detailed logs
# Go to: https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml
# Click: "Run workflow"
# Set:
#   - Branch: main
#   - Trading mode: paper
#   - Force trade: true
# Monitor: Check logs at "Pre-market health check" step
```

### Option 3: Regenerate Keys Fresh

If testing shows "unauthorized," regenerate fresh credentials:

```
1. Go to Alpaca Paper Trading Dashboard:
   https://app.alpaca.markets/paper/dashboard/overview

2. Click "Regenerate API Keys" (or create new)

3. Copy BOTH keys immediately:
   - API Key ID (starts with "PK...")
   - Secret Key (longer, starts with random chars)

4. Update GitHub Secrets:
   https://github.com/IgorGanapolsky/trading/settings/secrets/actions

   Update:
   - ALPACA_PAPER_TRADING_5K_API_KEY = API Key ID
   - ALPACA_PAPER_TRADING_5K_API_SECRET = Secret Key

5. Test immediately with manual workflow trigger
```

## Why This Matters

- **4 trading days lost** (Jan 5, 7, 8, 9)
- **5.6% of R&D period wasted**
- Paper account stuck at $5,000 (no activity)
- Cannot validate Phil Town strategy

## What I Will NOT Claim

❌ I will NOT claim the credentials are "invalid" without proof
❌ I will NOT claim there's a "typo" without seeing the actual values
❌ I will NOT claim keys are "for live account" without testing

**I can only report what Alpaca API says: "unauthorized."**

The next step requires YOU to verify the actual credentials work outside of GitHub Actions.

## Next Steps

1. **CEO**: Test credentials locally using `scripts/test_alpaca_credentials_local.py`
2. **CEO**: If test fails, regenerate keys from Alpaca dashboard
3. **CEO**: Update GitHub Secrets with verified working keys
4. **CEO**: Trigger manual workflow run to confirm fix
5. **CTO**: Once credentials work, implement monitoring to detect this earlier

## Status

- **Diagnostic**: ✅ Complete (authentication flow mapped)
- **Root Cause**: ⚠️ Alpaca API rejects credentials (reason unknown without testing)
- **Fix**: ⏳ Pending CEO credential verification
- **Monitoring**: ❌ Not implemented
