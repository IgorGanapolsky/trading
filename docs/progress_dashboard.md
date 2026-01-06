# Trading System Progress Dashboard

**Generated**: {{ "now" | date: "%Y-%m-%d %H:%M:%S" }} UTC
**Status**: LIVE

---

## Portfolio Overview

### Live Account (Real Money)

| Metric | Value |
|--------|-------|
| **Started** | Jan 3, 2026 |
| **Cash** | $30.00 |
| **Positions** | 0 |
| **Total P/L** | $0.00 |
| **Daily Deposit** | $10/day |

### Paper Account (R&D)

| Metric | Value |
|--------|-------|
| **Equity** | $101,167.20 |
| **Cash** | $86,629.93 |
| **Positions Value** | $14,537.27 |
| **Total P/L** | +$1,167.20 (+1.17%) |
| **Win Rate** | 80% |

---

## Current Positions

### Live Account

| Symbol | Type | Strike | Expiry | Entry | Current | P/L |
|--------|------|--------|--------|-------|---------|-----|
| *No positions yet* | - | - | - | - | - | - |

> Starting fresh with $20. First options trade coming when we reach minimum capital for defined-risk spreads.

### Paper Account (5 positions)

| Symbol | Type | Entry | Current | P/L |
|--------|------|-------|---------|-----|
| SPY | Long 21.62 shares | ~$682 | $685.03 | +$74.60 |
| INTC 01/09 $35P | Short Put | $0.82 | $0.06 | +$151.00 |
| SOFI 01/23 $24P | Short Put | $0.79 | $0.23 | +$56.00 |
| AMD 01/16 $200P | Short Put | $5.90 | $1.33 | +$457.00 |
| SPY 01/23 $660P | Short Put | $6.38 | $1.89 | +$449.00 |

**Total Unrealized P/L: +$1,187.60**

---

## Recent Trades

### Last 7 Days

| Date | Action | Symbol | Qty | Price | Notes |
|------|--------|--------|-----|-------|-------|
| 2025-12-23 | BUY | SPY | 0.73 | ~$590 | Paper account |
| 2025-12-23 | BUY | SPY | 0.73 | ~$590 | Paper account |
| 2025-12-23 | BUY | SPY | 0.73 | ~$590 | Paper account |

---

## Options Strategy Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Win Rate** | 80% | 75%+ |
| **Avg Days in Trade** | TBD | <30 |
| **Max Position Size** | TBD | 5% portfolio |
| **Daily Theta Target** | TBD | $10/day |

---

## 90-Day Challenge Progress

| Metric | Value |
|--------|-------|
| **Day** | 69 / 90 |
| **Phase** | R&D Phase - Month 3 (Days 61-90) |
| **Days Remaining** | 21 |
| **Target** | $100/day profit |

---

## Risk Status

| Check | Status |
|-------|--------|
| **Max Drawdown** | 0% (no positions) |
| **Position Limits** | OK |
| **Buying Power** | $30.00 |
| **Circuit Breakers** | Armed |

---

## What's Working

- **Options Theta**: 80% win rate on paper
- **Phil Town Rules**: Concentration over diversification
- **RAG System**: 709 documents, learning from failures

## What's Not Working

- ~~Bonds/Treasuries~~ - Removed Dec 29
- ~~Crypto~~ - Removed Dec 15
- ~~Complex ML~~ - Over-engineered

---

*Dashboard syncs from `data/system_state.json`*
*For full transparency, see [GitHub repo](https://github.com/IgorGanapolsky/trading)*
