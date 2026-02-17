# Alpaca Live Account - Options Level 2 Upgrade Instructions

**Current Status:** Options Level 1 (basic - can't trade spreads)
**Target:** Options Level 3 (enables credit spreads and iron condors)
**Expected Approval Time:** 1-3 business days

## Alpaca Options Levels

Per [Alpaca's official documentation](https://alpaca.markets/support/what-option-levels-or-tiers-do-you-provide):

**Level 1:**
- ✅ Covered calls (requires owning 100 shares)
- ✅ Cash-secured puts (requires full cash collateral)

**Level 2:**
- Level 1 + Long calls, Long puts (buying options only)

**Level 3:**
- ✅ **Credit spreads** ($100-200 capital per trade)
- ✅ **Iron condors** ($400-1,000 capital per trade)
- ✅ Debit spreads, Straddles, Strangles
- ✅ All multi-leg strategies

**You need Level 3 for SPY credit spreads and iron condors.**

## Upgrade Steps

### 1. Log in to Alpaca
https://alpaca.markets

### 2. Navigate to Options Trading Settings
Dashboard → Account Settings → Options Trading

### 3. Request Level 3 Approval

**CRITICAL:** The "Account > Configure" path mentioned in Alpaca docs may not be visible in current dashboard.

**Recommended approach:**
1. Click **"Account"** in left sidebar
2. Look for **"Options Trading"** or **"Configure"** submenu
3. If not found, use **Support chat** (bottom right of dashboard)
4. Request: "Apply for Options Trading Level 3"

**What to expect in questionnaire:**
- Trading experience: Intermediate or higher
- Years trading options: 1+ years
- Options strategies known: Credit spreads, Iron condors, Vertical spreads
- Financial profile: Complete "Investable/Liquid Assets" in Profile Settings

**IMPORTANT:** You get 2 initial applications. If denied, must wait 60 days to reapply.

### 4. Wait for Approval (1-3 business days)
Alpaca will review and typically approves within 1-3 business days.

### 5. Verify Approval
Once approved, verify via:
```bash
python3 -c "
from alpaca.trading.client import TradingClient
client = TradingClient(
    'AKCUSYBUFOBF6CHHP6MEDN343C',
    'Ez8mqM9Ke56wmiAY2Th2cVRpnNiw4J6iGHWmd9SgtQst',
    paper=False
)
account = client.get_account()
print(f'Options Level: {account.options_trading_level}')
print(f'Approved Level: {account.options_approved_level}')
"
```

Expected output after approval:
```
Options Level: 3
Approved Level: 3
```

## What Happens After Approval

### Capital Reality Check

**Current:** $208 equity, $40 cash
**Problem:** $1-wide SPY spread requires ~$70-100 collateral after premium

**Options:**
1. **Add $100-200 to live account** → Can trade 1-2 spreads
2. **Wait for VOO gains** → Reinvest into options when cash > $100
3. **Focus on paper account** → Validate strategy first, fund live later

### Strategy: $1-wide SPY Credit Spreads (AFTER funding to $300+)
- **Capital per trade**: $100 collateral
- **Expected credit**: $10-30
- **Net collateral**: $70-90 (after credit received)
- **ROI**: 10-30% per trade
- **Frequency**: 1 per week
- **Monthly target**: 4-8 trades = $40-240 profit

### Example Trade
```
Sell SPY $675 put / Buy SPY $674 put (30 DTE)
Credit received: $25
Max risk: $75 ($100 - $25)
ROI if expires worthless: 33%
```

## Live Account Credentials

**Already configured in trading system:**
- API Key: `AKCUSYBUFOBF6CHHP6MEDN343C`
- API Secret: `Ez8mqM9Ke56wmiAY2Th2cVRpnNiw4J6iGHWmd9SgtQst`
- Account Equity: $208.09
- Cash Available: $40.00

## Next Steps After Approval

1. **Execute first $1-wide credit spread**
   ```bash
   python3 scripts/execute_live_credit_spread.py --ticker SPY --width 1 --delta 0.16
   ```

2. **Weekly trading cadence**
   - Monday: Scan for new opportunity
   - Tuesday/Wednesday: Execute if conditions met
   - Thursday/Friday: Monitor existing position

3. **Scale gradually**
   - $208 → $500: 1 spread/week
   - $500 → $1K: 2 spreads/week
   - $1K → $5K: Add iron condors

---

**Created:** 2026-02-17
**Status:** PENDING - Requires manual login to Alpaca dashboard
