# LL-190: SOFI CSP Opened During Earnings Blackout

**Date:** January 13, 2026
**Severity:** HIGH
**Category:** risk-management, compliance

## The Violation

A SOFI $24 CSP expiring Feb 6 was opened on or around Jan 13, 2026.

**Problem**: Per LL-188 and CLAUDE.md, SOFI has an earnings blackout Jan 23-30 (earnings Jan 30, IV at 55%).

**Position details**:
- Symbol: SOFI260206P00024000
- Strike: $24
- Expiration: Feb 6, 2026
- Max loss if assigned: $2,400 (48% of portfolio!)

## Why This Is Risky

1. **IV Crush**: After earnings, IV typically drops 30-50%. Our short put will lose value, but if SOFI drops we're still at risk.
2. **Gap Risk**: Earnings can cause 10-20% gaps. A gap down to $22 means assignment at $24.
3. **Position Size**: $2,400 max loss is 48% of $5K portfolio - violates Rule #1.

## Immediate Action Required

**Convert to credit spread at market open Jan 14:**
- BUY 1x SOFI Feb 6 $19 put (~$0.15-0.20)
- This creates a $24/$19 bull put spread
- Max loss reduced: $2,400 → $500 (10% of portfolio)
- Collateral freed: $1,900

## Root Cause

The TradeGateway did NOT check earnings blackout dates before approving the trade.

## Prevention (MANDATORY CODE FIX)

Add to `src/risk/trade_gateway.py`:

```python
# Earnings blackout calendar
EARNINGS_BLACKOUTS = {
    "SOFI": {"start": "2026-01-23", "end": "2026-02-01", "earnings": "2026-01-30"},
    "F": {"start": "2026-02-03", "end": "2026-02-11", "earnings": "2026-02-10"},
}

def _check_earnings_blackout(self, symbol: str) -> tuple[bool, str]:
    """Check if symbol is in earnings blackout period."""
    today = datetime.now().date()
    underlying = self._get_underlying(symbol)

    if underlying in self.EARNINGS_BLACKOUTS:
        blackout = self.EARNINGS_BLACKOUTS[underlying]
        start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
        end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()

        if start <= today <= end:
            return True, f"{underlying} in earnings blackout {start} - {end}"

    return False, ""
```

## Tags

`risk-violation`, `earnings`, `position-sizing`, `sofi`, `blackout`
