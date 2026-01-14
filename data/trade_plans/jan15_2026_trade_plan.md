# Trade Plan: January 15, 2026

**Generated:** Jan 14, 2026 by CTO Claude
**Market Status:** Markets open 9:30 AM ET (Thursday)
**Trade Window:** 9:35 AM - 3:30 PM ET
**Account:** $4,959.26 (post SOFI closure)

## Lessons Applied from Jan 14 Loss (-$65.58)

| Lesson | Action |
|--------|--------|
| SOFI blackout violation | SPY/IWM ONLY - no individual stocks |
| Naked puts = 96% risk | Credit SPREADS only - defined risk |
| Expiration past earnings | Verify exp < any earnings date |
| $100K account worked with SPY | Focus exclusively on SPY |

## Pre-Market Checklist

- [ ] Check VIX level (target: <20 for credit spreads)
- [ ] Verify SPY not near major support/resistance
- [ ] Confirm account balance: ~$4,959
- [ ] Max position: 1 spread ($500 collateral = 10% risk)

## PRIMARY TRADE: SPY Bull Put Spread

**Why SPY:**
- Best liquidity (tightest bid/ask)
- No individual company earnings risk
- $100K account made +$16,661 on SPY focus
- LL-203 confirms this is the proven approach

**Setup:**
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Underlying | SPY | Best liquidity per $100K lessons |
| Strategy | Bull Put Spread | Defined risk (Phil Town Rule #1) |
| Short strike | 30-delta (~$575-580) | 70% prob of profit |
| Long strike | $5 below short | Max loss capped |
| DTE | 30-45 days (Feb 14-21) | Theta decay sweet spot |
| Premium target | $0.60-0.80 ($60-80) | Realistic for VIX ~15 |
| Collateral | $500 | 10% of account |
| Max loss | $420-440 | Spread width - premium |

**Exit Rules:**
| Condition | Action | Why |
|-----------|--------|-----|
| 50% profit ($30-40) | CLOSE | Bank gains, avoid reversal |
| 200% of premium loss | CLOSE | Cut losses per Rule #1 |
| 7 DTE | CLOSE | Gamma risk increases |
| VIX spikes >25 | CLOSE | Risk environment changed |

## BACKUP: IWM Bull Put Spread

Only if SPY spread is unavailable or has poor pricing.

| Parameter | Value |
|-----------|-------|
| Underlying | IWM |
| Short strike | 30-delta (~$215-220) |
| Long strike | $5 below |
| DTE | 30-45 days |
| Premium target | $0.50-0.70 |

## BLACKLIST (DO NOT TRADE)

| Ticker | Reason | Until |
|--------|--------|-------|
| SOFI | Earnings Jan 30, blackout active | Feb 1 |
| F | Earnings Feb 10, approaching | Feb 11 |
| Any individual stock | Not proven in our $100K testing | N/A |
| Naked options | Undefined risk | Never |

## Order of Operations

1. **9:30 AM** - Market opens, wait 5 min for initial volatility
2. **9:35 AM** - Daily Trading workflow triggers
3. **9:35-10:00 AM** - Analyze SPY option chain for 30-delta strike
4. **10:00 AM** - Place spread order (limit, not market)
5. **All day** - Monitor for 50% profit or stop loss
6. **3:30 PM** - Last decision point if trade not filled

## Risk Management

| Metric | Value | Status |
|--------|-------|--------|
| Max position size | $500 (10% of $4,959) | ENFORCED |
| Max daily loss | $250 (5% of account) | ENFORCED |
| Earnings check | trade_gateway.py | AUTOMATED |
| Phil Town alignment | Defined risk spread | COMPLIANT |

## Expected Outcome

| Scenario | Probability | P/L |
|----------|-------------|-----|
| SPY stays above short strike | 70% | +$60-80 |
| SPY drops, close at 50% loss | 20% | -$30-40 |
| SPY drops hard, max loss | 10% | -$420-440 |

**Expected Value:** (0.70 × $70) + (0.20 × -$35) + (0.10 × -$430) = $49 - $7 - $43 = **-$1**

This is a NEUTRAL expected value trade - we need 70%+ win rate to profit. Focus on:
1. Proper strike selection (30-delta, not ATM)
2. Early profit taking (50% rule)
3. Strict stop loss adherence

## Post-Trade Protocol

- [ ] Record trade in RAG immediately
- [ ] Update performance_log.json
- [ ] If loss: record lesson in LL-206
- [ ] If win: document what worked

---

**Confidence Level:** MEDIUM
**Risk Level:** CONTROLLED (defined risk spread)
**Phil Town Compliance:** YES (Rule #1 margin of safety with 30-delta)
