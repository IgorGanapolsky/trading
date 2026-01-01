# Combined Trading Strategy: Day Trading Options + Rule #1 Investing

**Created**: January 1, 2026
**Goal**: $100/day net profit after-tax
**Timeline**: 90-day R&D experiment

---

## Overview

This document describes our two-pronged approach to achieving consistent trading profits:

1. **Day Trading Options** - Short-term income generation
2. **Phil Town Rule #1 Investing** - Long-term wealth building

These strategies complement each other perfectly:
- Options provide **income now** (cash flow)
- Rule #1 builds **wealth over time** (capital appreciation)

---

## Strategy 1: Day Trading Options

### Objective
Generate $100+/day through disciplined options trading.

### Core Tactics
1. **Cash-Secured Puts (CSPs)** on quality stocks
2. **Covered Calls** when we own shares
3. **Credit Spreads** for defined risk

### Key Parameters
- **Account Size Required**: $25,000+ (PDT rule)
- **Daily Target**: 0.5-1% of account value
- **Win Rate Goal**: 70%+
- **Max Risk Per Trade**: 2%

### Entry Criteria (5-Gate System)
1. **Gate 1 (Momentum)**: Technical indicators confirm direction
2. **Gate 2 (RL Model)**: AI confidence > 35%
3. **Gate 3 (Sentiment)**: Market sentiment neutral/positive
4. **Gate 4 (Risk)**: Position sizing within limits
5. **Gate 5 (Execution)**: Liquidity and spread acceptable

### Implementation
```bash
# Run daily options scanner
python3 scripts/morning_trade_finder.py
```

---

## Strategy 2: Phil Town Rule #1 Investing

### Objective
Build long-term wealth by owning "wonderful companies at attractive prices."

### The Four Ms
1. **Meaning**: Understand the business
2. **Moat**: Durable competitive advantage
3. **Management**: Honest, owner-oriented leadership
4. **Margin of Safety**: Buy at 50% of intrinsic value

### The Big Five Numbers (All must be ≥10% for 10 years)
1. Return on Invested Capital (ROIC)
2. Sales Growth
3. EPS Growth
4. Equity (Book Value) Growth
5. Free Cash Flow Growth

### Valuation Formula

**Sticker Price** (Fair Value):
```
Future EPS = Current EPS × (1 + Growth Rate)^10
Future P/E = min(2 × Growth Rate × 100, 50)
Future Price = Future EPS × Future P/E
Sticker Price = Future Price / (1.15)^10
```

**MOS Price** (Buy Price):
```
MOS Price = Sticker Price × 0.50
```

### Rule #1 Options Integration

When a Rule #1 stock is **above** MOS price:
- **Sell puts at MOS strike** ("Getting Paid to Wait")
- If assigned, you own at your target price minus premium
- If not assigned, keep premium as profit

When you **own** Rule #1 shares:
- **Sell covered calls at Sticker Price** ("Getting Paid to Sell")
- If called away, sell at fair value plus premium
- If not called, keep premium and shares

### Implementation
```bash
# Run Rule #1 analysis
python3 scripts/rule_one_trader.py
```

---

## Combined Strategy Execution

### Daily Workflow

**Pre-Market (8:00 AM ET)**
1. Check overnight news/sentiment
2. Run `rule_one_trader.py` for value opportunities
3. Run `morning_trade_finder.py` for options trades
4. Review ML signals report

**Market Hours (9:30 AM - 4:00 PM ET)**
1. Execute Rule #1 put opportunities first (lower risk)
2. Execute day trade options second
3. Monitor positions via Alpaca dashboard
4. Set stop-losses and take-profit targets

**Post-Market (4:00 PM ET)**
1. Review executed trades
2. Update performance log
3. Run `system_health_check.py`
4. Log lessons learned

### Capital Allocation

| Strategy | Allocation | Risk Level | Expected Return |
|----------|------------|------------|-----------------|
| Rule #1 Puts | 40% | Low | 12-20% annually |
| Day Trading | 40% | Medium | 50-100% annually |
| Cash Reserve | 20% | None | 5% (sweep) |

### Risk Management

**Never Violate These Rules:**
1. **Losing money is unacceptable** - protect capital at all costs
2. Max 2% risk per trade
3. Max 5 open positions
4. Stop trading after 3 consecutive losses
5. Never chase losses

---

## Path to $100/Day Goal

### Phase 1: Capital Building (Current - $10/day deposits)
- Accumulate via automated daily deposits
- Paper trade to refine strategy
- Build track record

### Phase 2: Small Real Money ($25,000 account)
- Begin real trading when capital reaches PDT threshold
- Target $50/day (0.2% daily)
- Focus on Rule #1 puts (safest)

### Phase 3: Scale Up ($50,000+ account)
- Increase position sizes
- Target $100/day (0.2% daily)
- Add day trading options

### Phase 4: Optimize ($75,000+ account)
- Lower daily return requirement (0.13%)
- More consistent profits
- Reinvest excess for compound growth

---

## Tax Strategy

### Section 475 Mark-to-Market Election
- **File by**: April 15, 2026 (for 2026 tax year)
- **Benefits**:
  - Wash sale rule eliminated
  - Unlimited loss deductions
  - Losses offset all income types

### Tax-Loss Harvesting
- Realize losses before Dec 31 each year
- Wait 31 days before repurchasing
- Carry forward excess losses

### Record Keeping
- Log every trade in `data/audit_trail/`
- Keep screenshots of all executions
- Export monthly statements from Alpaca

---

## Key Files

| Purpose | File |
|---------|------|
| Rule #1 Strategy | `src/strategies/rule_one_options.py` |
| Rule #1 Runner | `scripts/rule_one_trader.py` |
| Options Scanner | `scripts/morning_trade_finder.py` |
| ML Report Generator | `src/orchestrator/ml_report_generator.py` |
| RAG Search | `src/rag/lessons_search.py` |
| System Health | `scripts/system_health_check.py` |

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Daily Profit | $100 | TBD |
| Win Rate | 70% | 80% |
| Max Drawdown | <10% | TBD |
| Sharpe Ratio | >1.5 | 0.0 |
| Days Profitable | 80%+ | TBD |

---

## Next Steps

1. ✅ Research Phil Town Rule #1 (Complete)
2. ✅ Implement Rule #1 options strategy (Complete)
3. ✅ Create ML report generator (Complete)
4. 🔄 Fix RAG vectorization (In Progress)
5. ⏳ Begin real money trading when capital ready

---

*"Rule #1: Don't lose money. Rule #2: Don't forget Rule #1."* - Warren Buffett
