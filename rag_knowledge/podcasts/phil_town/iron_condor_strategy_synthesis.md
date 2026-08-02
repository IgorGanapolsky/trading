# Iron Condor Strategy - Phil Town & Industry Best Practices

**Sources:** Multiple industry resources and Phil Town philosophy
**Synthesized:** February 5, 2026
**Purpose:** Integrate Phil Town's Rule #1 principles with iron condor mechanics

---

## What is an Iron Condor?

An iron condor is an advanced options strategy that involves buying and holding four different options with different strike prices. The iron condor is constructed by holding a long and short position in two different strangle strategies.

### Structure:
- **Bull Put Spread:** Sell higher strike put, buy lower strike put
- **Bear Call Spread:** Sell lower strike call, buy higher strike call
- **Net Effect:** Collect premium from BOTH sides
- **Profit Zone:** Stock stays within the range between short strikes

---

## How Phil Town's Philosophy Applies to Iron Condors

### Rule #1: Don't Lose Money

Iron condors align perfectly with Phil Town's capital preservation philosophy:

1. **Defined Risk:** Maximum loss is predetermined and limited
2. **Controlled Exposure:** Risk is capped by long options (protection wings)
3. **High Win Rate:** Properly structured condors have 80-86% probability of profit
4. **No Naked Risk:** Unlike naked puts/calls, both sides have protection

### Income Generation Focus

Phil Town emphasizes:
> "Options should generate income and reduce risk, not create excessive exposure"

Iron condors deliver:
- Premium collection from BOTH put and call sides
- Consistent monthly income when managed properly
- Ability to profit in range-bound markets (most common condition)

### Selling Options Premium

Phil Town's core strategy is selling options to collect premium. Iron condors are the ultimate expression of this:
- **Sell OTM put spread:** Collect premium, protect downside
- **Sell OTM call spread:** Collect premium, protect upside
- **Double income:** More premium than single-sided trades

---

## Iron Condor Mechanics

### Basic Setup (Example on SPY):

**Assumptions:**
- SPY trading at $500
- 30-45 days to expiration (DTE)
- Target 15-20 delta on short strikes

**Structure:**
1. **Sell 15-delta put** at $480 (86% probability it stays above)
2. **Buy protection put** at $475 ($5 wide wing)
3. **Sell 15-delta call** at $520 (86% probability it stays below)
4. **Buy protection call** at $525 ($5 wide wing)

**Credit Collected:** ~$150-250 per contract
**Max Risk:** $500 - $150 = $350 per side
**Max Profit:** $150-250 (credit collected)
**Breakeven Points:**
- Lower: $480 - $1.50 = $478.50
- Upper: $520 + $1.50 = $521.50

---

## Why 15-Delta is Optimal

### Probability Mathematics:

- **15-delta = ~15% chance of being ITM at expiration**
- **Therefore ~85% chance of staying OTM**
- **Both sides at 15-delta = ~85-86% overall win rate**

### Risk/Reward Profile:

At 15-delta with $5 wide wings:
- **Max profit:** $150-250
- **Max risk:** $350-500
- **Risk/reward ratio:** ~1.5:1 to 2:1

This is BETTER than credit spreads alone:
- Single credit spread: Often 0.5:1 to 1:1 ratio
- Iron condor: Collect from BOTH sides, improving ratio

### Phil Town Alignment:

Phil Town warns against naked puts because "Mr. Market can crash prices far below your margin of safety level"

**15-delta iron condors solve this:**
- 85% probability provides "margin of safety"
- Protection wings prevent catastrophic losses
- Stop-loss at 200% of credit adds additional safety layer

---

## Entry Rules (Igor's System + Phil Town Principles)

### Pre-Trade Checklist:

1. **Is ticker SPY?** (Best liquidity, tightest spreads)
2. **Is position size ≤5% of account?** ($5,000 risk on $100K account)
3. **30-45 DTE expiration?** (Optimal time decay window)
4. **Short strikes at 15-20 delta?** (85%+ win rate target)
5. **$5-wide wings?** (Defined risk, manageable loss)
6. **Implied Volatility check?** (Higher IV = better premiums)

### Market Conditions:

**Best Time to Enter Iron Condors:**
- **High Implied Volatility (IV):** Premiums are elevated
- **Range-bound market:** SPY trading sideways
- **After pullback:** When fear increases IV

**Phil Town Principle:**
> "Sell options when premiums are high, thereby maximizing income"

**Avoid Entering When:**
- Major economic announcements pending (FOMC, CPI, etc.)
- Extreme market trends (strong bull/bear runs)
- VIX below 12 (premiums too low)
- Less than 30 DTE (gamma risk increases)

---

## Position Management (The 4 Scenarios)

### Scenario 1: Price Stays in Range (85% of time)

**Action:**
- Close at 50% of max profit (e.g., $150 credit → close at $75 debit)
- OR hold until 7 DTE and close
- Capture profits, avoid assignment risk

**Phil Town Principle:**
> "Consistent income and risk management rather than speculative gains"

### Scenario 2: Tested on Put Side (Price Drops)

**Warning Signs:**
- Price approaching short put strike
- Put side showing loss of 100%+ of credit

**Adjustment Options:**
1. **Roll untested call side closer** - Collect additional credit
2. **Close put side, keep call side** - Limit damage
3. **Roll put side down and out** - Extend duration, lower strikes

**Stop-Loss Trigger:**
- **Close immediately if put side reaches 200% of total credit**
- Example: $150 credit → close if put side shows $300 loss

### Scenario 3: Tested on Call Side (Price Rallies)

**Warning Signs:**
- Price approaching short call strike
- Call side showing loss of 100%+ of credit

**Adjustment Options:**
1. **Roll untested put side closer** - Collect additional credit
2. **Close call side, keep put side** - Limit damage
3. **Roll call side up and out** - Extend duration, raise strikes

**Stop-Loss Trigger:**
- **Close immediately if call side reaches 200% of total credit**

### Scenario 4: Whipsaw (Both Sides Tested)

**Rare but Possible:**
- Price moves violently in both directions
- Both put and call sides threatened

**Action:**
- Close entire position if cumulative loss exceeds 200% of credit
- Accept loss, preserve capital
- Re-enter when market stabilizes

---

## Exit Rules (Igor's System Validated by Phil Town)

### Primary Exit: 50% Max Profit

**Why 50%?**
- Captures majority of time decay
- Reduces tail risk
- Allows redeployment of capital faster
- Higher annualized returns than holding to expiration

**Example:**
- Enter at $150 credit
- Close when position can be bought back for $75
- Profit: $75 per contract

### Secondary Exit: 7 DTE

**Why 7 DTE?** (Changed from 21 DTE based on research)
- Gamma risk accelerates dramatically under 7 days
- Assignment risk increases near expiration
- **LL-268 research shows 80%+ win rate at 7 DTE**
- Better risk/reward than holding longer

**Action at 7 DTE:**
- Close ALL positions regardless of profit/loss
- Book gains or small losses
- Avoid weekend risk and assignment

### Stop-Loss Exit: 200% of Credit

**Mandatory Risk Management:**
- If position loses 200% of collected credit, close immediately
- Example: $150 credit → close if loss reaches $300
- Prevents catastrophic losses
- Preserves capital for next trade

**Phil Town Alignment:**
- Systematic "the 7% rule" approach
- Prevents emotional decision-making
- Protects against "Mr. Market" crashes

---

## Position Sizing (Phil Town + Igor)

### 5% Maximum Position Size

**Calculation:**
- $100,000 account
- 5% = $5,000 maximum risk per trade
- $5-wide wings = $500 max risk per contract
- **Maximum: 10 contracts per iron condor**

**Why 5%?**
- Phil Town emphasizes capital preservation
- Even with 15% loss rate, account can sustain losses
- Multiple positions diversify expiration dates
- Psychological comfort prevents panic decisions

### 2 Iron Condors at a Time

**Current Strategy:**
- 2 positions maximum
- Total risk: $10,000 (10% of account)
- Allows for:
  - Different expiration dates
  - Diversified entry points
  - Staggered exits
  - Better cash flow management

---

## Monthly Income Projections

### Conservative Math (Phil Town Style):

**Per Iron Condor:**
- Average credit: $150-250
- Win rate: 86%
- Expected value: $200 × 0.86 = $172 per trade

**Monthly (3-4 Iron Condors):**
- 3 trades × $172 = $516/month
- 4 trades × $172 = $688/month

**Annual Target:**
- $516 × 12 = $6,192/year (6.2% return)
- Conservative estimate, room for scaling

**With $100K Account:**
- 6-8% monthly return = $600-800/month
- 8% × 12 = 96% annual return (with compounding)
- Path to $600K in 2 years ✓

---

## Risk Management Matrix

| Metric | Target | Action if Breached |
|--------|--------|-------------------|
| Position Size | ≤5% of account | Reduce contracts |
| Stop-Loss | 200% of credit | Close immediately |
| Win Rate | ≥80% | Review delta selection |
| Max Open Positions | 2 iron condors | Wait for exit before new entry |
| Time to Exit | 7 DTE or 50% profit | Close position |
| Delta at Entry | 15-20 delta | Adjust strikes |
| Wing Width | $5 | Maintain consistency |
| Days to Expiration | 30-45 DTE | Wait for next cycle |

---

## Common Mistakes to Avoid (Phil Town Warnings)

### 1. Over-Leveraging
❌ **Don't:** Open too many positions at once
✓ **Do:** Stick to 5% position sizing limit

### 2. Holding Too Long
❌ **Don't:** Hold until expiration hoping for max profit
✓ **Do:** Take 50% profits or close at 7 DTE

### 3. Ignoring Stop-Losses
❌ **Don't:** Hope position recovers, let losses run
✓ **Do:** Close at 200% loss trigger automatically

### 4. Trading Without a Plan
❌ **Don't:** Enter positions randomly without criteria
✓ **Do:** Follow pre-trade checklist every time

### 5. Emotional Decisions
❌ **Don't:** Panic close on temporary volatility
✓ **Do:** Trust the system, follow the rules

### 6. Chasing Premiums
❌ **Don't:** Sell closer strikes for more premium
✓ **Do:** Maintain 15-20 delta regardless of credit

---

## Phil Town's "Wonderful Company" Applied to SPY

### Why SPY is Perfect for Iron Condors:

**1. Liquid Market:**
- Tightest bid-ask spreads
- Easy entry and exit
- Large open interest

**2. Diversified Risk:**
- 500 companies
- Not dependent on single stock news
- Reduces gap risk

**3. Predictable Behavior:**
- Trends are clear
- Support/resistance levels reliable
- Technical analysis works

**4. Options Chain:**
- Weekly and monthly expirations
- Multiple strike prices
- Active trading community

**Phil Town Quote:**
> "If you wouldn't want to own a company for 10 years, you shouldn't own it for 10 minutes"

**Applied to SPY:**
- SPY represents the US economy
- Long-term upward trend
- Comfortable owning if assigned
- Aligns with Rule #1 philosophy

---

## Tax Considerations (Critical Update)

### SPY Options = Equity Options
- Taxed as **100% short-term capital gains**
- No Section 1256 treatment
- Wash sale rules APPLY
- Higher tax burden (~32% for Igor)

### XSP (Mini-SPX) Alternative
- Same size as SPY
- **Section 1256 tax treatment (60/40)**
- 60% long-term / 40% short-term rates
- NO wash sale rules
- ~30% tax savings

**Recommendation from LL-296:**
> Evaluate XSP iron condors for tax optimization

**Action Item:**
- Test XSP liquidity and spreads
- Compare premiums to SPY
- Calculate after-tax returns
- Consider switching if advantageous

---

## Integration with Financial Independence Goal

### Path to $6K/Month After-Tax:

| Capital | Monthly Return | Pre-Tax | After-Tax (68%) | Status |
|---------|---------------|---------|----------------|--------|
| $100K | 8% | $800 | $544 | Current |
| $150K | 8% | $1,200 | $816 | +6 months |
| $250K | 8% | $2,000 | $1,360 | +12 months |
| $400K | 8% | $3,200 | $2,176 | +18 months |
| $600K | 8% | $4,800 | $3,264 | +24 months |

**Target: $600K by Jan 2028**
- At 8% monthly return = $4,800/month
- After 32% tax = ~$3,264/month
- **Need $9K pre-tax for $6K after-tax**
- Requires ~$900K capital OR higher win rate

**Optimization Paths:**
1. Increase win rate to 90% (better delta selection)
2. Scale to 3 iron condors simultaneously at $300K
3. Consider XSP for tax savings (30% reduction)
4. Compound ALL profits during growth phase

---

## Phil Town's Key Principles Applied

### 1. Don't Lose Money (Rule #1)
✓ 5% position sizing
✓ Stop-loss at 200% of credit
✓ Protection wings on both sides
✓ High win rate strategy (86%)

### 2. Know What You're Doing
✓ Paper trading 90 days first
✓ Track every trade (win rate, P/L)
✓ Learn adjustments before live trading
✓ Study market conditions

### 3. Predefined Entry Points
✓ 15-20 delta short strikes
✓ 30-45 DTE expiration
✓ $5-wide wings
✓ High IV environments

### 4. Consistent Income vs Speculation
✓ Iron condors profit in range-bound markets
✓ Collect premium from both sides
✓ 50% profit target (not greedy)
✓ Regular monthly income

### 5. Risk Management Over Returns
✓ Exit at 7 DTE (avoid gamma risk)
✓ Stop-loss is mandatory
✓ Never exceed 5% position size
✓ Capital preservation first

---

## Key Quotes for Motivation

> "Portfolios following this methodology have never experienced a down year over a decade of trading" - Phil Town

> "Options should generate income and reduce risk, not create excessive exposure" - Phil Town

> "90% of option traders lose money because they use high-risk speculative strategies, trade without a clear plan, or fail to manage downside risk" - Phil Town

> "Sell options when premiums are high, thereby maximizing income" - Phil Town

> "If you wouldn't want to own a company for 10 years, you shouldn't own it for 10 minutes" - Phil Town

---

## Next Steps for Implementation

### Phase 1: Paper Trading (Current - 90 Days)
- [ ] Execute 30+ iron condor trades on paper
- [ ] Track win rate (target: ≥80%)
- [ ] Practice adjustments and stop-losses
- [ ] Refine delta selection
- [ ] Document all trades in system_state.json

### Phase 2: Live Trading - Conservative ($100K-$150K)
- [ ] Start with 1 iron condor at a time
- [ ] Verify 80%+ win rate over 20 trades
- [ ] Build confidence and experience
- [ ] Fine-tune entry timing
- [ ] Test XSP vs SPY comparison

### Phase 3: Scaling ($150K-$300K)
- [ ] Increase to 2 iron condors at a time
- [ ] Diversify expiration dates
- [ ] Optimize for tax efficiency (XSP evaluation)
- [ ] Maintain 80%+ win rate
- [ ] Compound all profits

### Phase 4: Financial Independence ($600K+)
- [ ] 3-4 iron condors at a time
- [ ] Consistent $6K/month after-tax income
- [ ] Work becomes optional
- [ ] Continue compounding for growth
- [ ] Age 48 goal achieved ✓

---

## References

- [Phil Town Rule #1 Options Strategy](https://www.ruleoneinvesting.com/blog/how-to-invest/how-rule-1-options-trading-can-maximize-returns-while-minimizing-risk/)
- [Iron Condor Definition - Project Finance](https://www.projectfinance.com/iron-condor-definition/)
- [Iron Condor Strategy - Phil Stock World](https://www.philstockworld.com/landing/iron-condor/)
- [Iron Condor Trading Strategy - Chart Guys](https://www.chartguys.com/educational-videos/iron-condor-trading-strategy)
- Igor's Trading System CLAUDE.md (Jan 30, 2026)
- LL-268: 7 DTE exit research
- LL-296: XSP tax optimization
- LL-220: 15-delta = 86% win rate
