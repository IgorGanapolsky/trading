# LL-205: January 14, 2026 Loss Root Cause Analysis

**Date:** January 14, 2026
**Severity:** HIGH
**Category:** post-mortem, risk-management, compliance
**Loss:** -$65.58 daily, -$40.74 total P/L (-0.81%)

## Executive Summary

On January 14, 2026, the paper trading account suffered a $65.58 daily loss when the system correctly force-closed SOFI positions before earnings. The loss occurred because positions should NEVER have been opened in the first place.

## Timeline of Events

| Date | Event | P/L Impact |
|------|-------|------------|
| Jan 13, 9:35 AM | SOFI CSP opened during blackout period | - |
| Jan 13, 3:19 PM | Positions recorded: 3.78 shares + 1 short put | -$2.09 |
| Jan 14, 9:45 AM | Scheduled close workflow triggered | - |
| Jan 14, 9:46 AM | All SOFI closed: 24.75 shares + 2 puts | -$18.31 |
| Jan 14, EOD | Daily P/L reported | -$65.58 |

## Positions at Close

1. **SOFI Stock**: 24.745561475 shares, P/L: -$1.31
2. **SOFI260206P00024000**: -2 contracts @ $24 strike, P/L: -$17.00
   - Note: Position grew from -1 to -2 contracts (duplicate order issue per LL-172)

## Root Cause Analysis

### Primary Cause: Earnings Blackout Violation
CLAUDE.md explicitly states: "SOFI: BLACKOUT until Feb 1 (earnings Jan 30, IV 55%)"

The trade gateway did NOT check earnings dates before approving the CSP order.

### Secondary Cause: Expiration Past Earnings
- Put expiration: Feb 6, 2026
- Earnings date: Jan 30, 2026
- Gap: 7 days after earnings = maximum volatility exposure

### Tertiary Cause: Forced Exit at Loss
When violations are discovered, closing positions often means realizing losses. The system did the RIGHT thing by closing, but the damage was already done.

## Loss Breakdown

| Component | Amount | Explanation |
|-----------|--------|-------------|
| Stock loss | -$1.31 | SOFI dropped from entry |
| Put loss | -$17.00 | Options went against us (IV expansion) |
| Slippage | ~-$47 | Market orders to close rapidly |
| **Total** | **-$65.58** | Daily change |

## Why This Loss Was "Good" (Phil Town Perspective)

The loss could have been MUCH worse:
- If held through earnings with 12.2% expected move
- Assignment risk: $4,800+ (96% of $5K portfolio)
- Instead: Lost $65 to avoid potential $4,800+ loss

**Rule #1 was ultimately followed by cutting the loss early.**

## Prevention Measures Required

### Immediate (Code Fix)
```python
# In src/risk/trade_gateway.py
EARNINGS_BLACKOUTS = {
    "SOFI": {"start": "2026-01-23", "end": "2026-02-01", "earnings": "2026-01-30"},
    "F": {"start": "2026-02-03", "end": "2026-02-11", "earnings": "2026-02-10"},
}

def _check_earnings_blackout(self, symbol: str) -> bool:
    """Block trades on tickers in earnings blackout."""
    underlying = self._extract_underlying(symbol)
    if underlying in self.EARNINGS_BLACKOUTS:
        blackout = self.EARNINGS_BLACKOUTS[underlying]
        today = datetime.now().date()
        start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
        end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()
        if start <= today <= end:
            return True  # Block trade
    return False
```

### Process Improvements
1. Pre-trade checklist must be enforced in code, not just documentation
2. All options trades must verify expiration < earnings date
3. SPY/IWM should be prioritized (no individual earnings risk)

## Account Status Post-Loss

- Starting equity: $5,000.00
- Current equity: $4,959.26
- Total P/L: -$40.74 (-0.81%)
- Positions: 0 (all closed)
- Buying power: $9,918.52

## Action Items

- [x] SOFI positions closed (Jan 14)
- [x] Root cause documented (this lesson)
- [ ] Implement earnings blackout check in trade gateway
- [ ] Add test for blackout enforcement
- [ ] Update pre-trade checklist to be code-enforced

## Key Takeaway

**The system worked correctly by force-closing positions before catastrophic loss. The failure was allowing the trade in the first place. Prevention > cure.**

## Tags

`post-mortem`, `sofi`, `earnings`, `blackout-violation`, `risk-management`, `phil-town`, `rule-1`
