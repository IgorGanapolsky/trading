# Phil Town's Rule #1 Investing - Complete Knowledge Base

## Source

**Author**: Phil Town
**Books**: "Rule #1" (2006), "Payback Time" (2010)
**Category**: Value Investing + Options Strategy
**Priority**: Critical - Core Strategy Foundation

---

## Core Philosophy

### Rule #1: Don't Lose Money

- Warren Buffett's first rule of investing
- Rule #2: Don't forget Rule #1
- Focus on CERTAINTY over potential returns
- Only invest in "wonderful companies" at "attractive prices"

### The 4 Ms Framework

#### 1. Meaning

- Do you understand the business?
- Would you understand it without looking at the stock price?
- Could you explain it to a 10-year-old?
- Is it within your "Circle of Competence"?

**Key Questions:**

- What does the company do to make money?
- Who are its customers?
- What problem does it solve?
- Would you want to own the whole business?

#### 2. Moat (Competitive Advantage)

Five types of moats:

1. **Brand** - Coca-Cola, Apple, Nike
2. **Secret** - Patents, trade secrets (Pfizer, Google algorithm)
3. **Toll Bridge** - Monopoly/duopoly position (utilities, Visa/Mastercard)
4. **Switching Costs** - Too expensive to leave (Microsoft Office, Oracle)
5. **Price** - Lowest cost producer (Walmart, Costco)

**Moat Durability Test:**

- Has the moat existed for 10+ years?
- Will it exist for 10+ more years?
- Is it widening or narrowing?

#### 3. Management

- CEO should be owner-oriented
- Check insider ownership (>5% is good)
- Read annual letter to shareholders
- Look for candor about mistakes
- Compensation should align with shareholders

**Red Flags:**

- Excessive executive compensation
- Frequent acquisitions that destroy value
- Empire building vs. shareholder returns
- Promotional/hype-focused communication

#### 4. Margin of Safety (MOS)

- Buy at 50% or less of intrinsic value
- Protects against calculation errors
- Provides significant upside potential
- Never pay full price for any stock

---

## The Big Five Numbers

### Must ALL grow at 10%+ over 1, 5, and 10 years:

1. **Return on Invested Capital (ROIC)**
   - Net Income / (Equity + Long-term Debt)
   - Shows management efficiency
   - Should be >10% and consistent

2. **Sales Growth (Revenue)**
   - Top-line growth trajectory
   - Must be sustainable, not one-time

3. **Earnings Per Share (EPS) Growth**
   - Bottom-line growth
   - Quality of earnings matters

4. **Book Value Per Share (BVPS) Growth**
   - Net assets per share
   - Shows retained earnings accumulation

5. **Free Cash Flow (FCF) Growth**
   - Cash left after capital expenditures
   - Most important - cash is truth

### The 10-10-10 Rule

All Big Five must show:

- 10%+ growth over past 10 years
- 10%+ growth over past 5 years
- 10%+ growth over past 1 year

If ANY fails, the company fails Rule #1 screening.

---

## Sticker Price Calculation

### Formula Components:

1. **Current EPS** - Trailing 12-month earnings per share
2. **Growth Rate** - Lower of (historical growth, analyst estimates, ROIC)
3. **Future PE** - 2x Growth Rate (capped at 40)
4. **Minimum Acceptable Return** - 15% (Rule #1 standard)

### Calculation Steps:

```
Step 1: Future EPS (10 years out)
Future EPS = Current EPS × (1 + Growth Rate)^10

Step 2: Future Stock Price
Future Price = Future EPS × Future PE

Step 3: Sticker Price (Present Value)
Sticker Price = Future Price / (1 + 0.15)^10

Step 4: Margin of Safety Price (MOS)
MOS Price = Sticker Price × 0.50
```

### Example:

```
Current EPS: $5.00
Growth Rate: 12%
Future PE: 24 (2 × 12)

Future EPS = $5.00 × (1.12)^10 = $15.53
Future Price = $15.53 × 24 = $372.72
Sticker Price = $372.72 / (1.15)^10 = $92.15
MOS Price = $92.15 × 0.50 = $46.08

→ Only buy at $46.08 or below
```

---

## Options Strategy (From "Payback Time")

### Cash-Secured Put Strategy

**When to Sell Puts:**

- Stock is in your Rule #1 universe
- Current price is ABOVE your MOS price
- You WANT to own the stock at lower price
- You have cash to buy if assigned

**Strike Selection:**

- Sell at or slightly above MOS price
- 21-45 DTE for optimal theta decay
- Collect premium while waiting for entry
- Target delta: 0.15-0.30 (15-30% probability of assignment)
- Conservative sellers use 0.15-0.20 delta for higher win rate

**Example:**

```
MOS Price: $46
Current Price: $55
Sell Put Strike: $47 (0.20 delta)
Premium: $1.50

Outcome A: Stock stays above $47
→ Keep $1.50 premium, repeat

Outcome B: Assigned at $47
→ Effective cost: $47 - $1.50 = $45.50
→ Below MOS! Great entry!
```

### Covered Call Strategy

**When to Sell Calls:**

- You own a Rule #1 stock
- Price is approaching Sticker Price
- You're willing to sell at that price
- Lock in profits while collecting premium

**Strike Selection:**

- Sell at or above Sticker Price
- 21-45 DTE for optimal theta decay
- Accept assignment as profit-taking
- Target delta: 0.15-0.20 (far OTM) for 15-20% chance of assignment
- Allows stock to run while collecting premium

**Example:**

```
Sticker Price: $92
Current Price: $85
Sell Call Strike: $95 (0.18 delta)
Premium: $2.00

Outcome A: Stock stays below $95
→ Keep $2.00 premium, keep stock

Outcome B: Called away at $95
→ Total return: ($95 - $46 cost) + $2 = $51
→ 111% return on original investment
```

### LEAPS Strategy (Poor Man's Covered Call)

**When to Use LEAPS:**

- Want stock-like exposure with less capital
- Bullish long-term but want to collect premium
- Can't afford 100 shares of expensive stock
- Alternative to traditional covered calls

**Long LEAPS Call Selection:**

- Buy deep in-the-money (ITM) call
- Target delta: 0.80+ (acts like stock ownership)
- 12-24 months to expiration (LEAPS timeframe)
- Extrinsic value <1% per month of stock price
- Strike selection: Minimize extrinsic decay

**Short Call Selection (Sell Against LEAPS):**

- Sell shorter-term calls (30-45 DTE)
- Strike above current price
- Weekly options decay faster but need more management
- Monthly options provide balance
- Target: 50-70% of max profit before closing

**Exit Management:**

- Close LEAPS before 45 DTE (theta accelerates)
- Don't hold to expiration (gamma risk)
- Roll short calls if tested
- Take profit at 50-70% of max gain

**Example:**

```
Stock: $100
Buy: $80 strike LEAPS call (18 months out, 0.85 delta)
Cost: $22.00 ($2,200 total)

Sell: $105 strike monthly call (35 DTE, 0.18 delta)
Premium: $1.50 ($150 collected)

Outcome A: Stock stays below $105
→ Keep $150, repeat monthly
→ Reduce cost basis of LEAPS over time

Outcome B: Stock rises above $105
→ LEAPS gains $20+ in value
→ Close entire position for profit
→ Or roll short call higher for more credit
```

---

## Technical Analysis: The Three Tools for Timing

### Overview

Phil Town uses THREE technical indicators to time entries and exits. These tools identify when institutional money is flowing in or out of a stock.

**Philosophy**: "If the three indicators don't say go, I don't go."

### Tool #1: Moving Average (Trend)

**Settings:**
- **30-day Simple Moving Average (SMA)** - Recommended (prevents false signals)
- Alternative: 10-day SMA (more signals, more whipsaws)

**Rule:**
- **BUY**: Price closes ABOVE the 30-day MA
- **SELL**: Price closes BELOW the 30-day MA

**Why It Works**: Shows institutional money flow direction

### Tool #2: MACD (Momentum)

**Settings:**
- **8-17-9** (Phil Town's custom settings)
- Standard MACD uses 12-26-9
- Based on difference between two exponential moving averages

**Rule:**
- **BUY**: MACD histogram ABOVE centerline (> 0)
- **SELL**: MACD histogram BELOW centerline (< 0)

**Why It Works**: Leading indicator of trend reversals

### Tool #3: Stochastic (Overbought/Oversold)

**Settings:**
- **14-5-0** (Slow Stochastic)
- %K line (14-period) = black line = "buy line"
- %D line (5-period) = red line = "sell line"

**Rule:**
- **BUY**: Black line (%K) crosses ABOVE red line (%D)
- **SELL**: Red line (%D) crosses ABOVE black line (%K)

**Why It Works**: Identifies momentum shifts

---

## Entry & Exit Signals (Exact Criteria)

### BUY SIGNAL: "Three Green Arrows"

**ALL THREE must be true:**

1. Price > 30-day Moving Average ✓
2. MACD histogram > 0 ✓
3. Stochastic %K line > %D line ✓

**Phil Town's Rule**: "Buy with three greens. I regret it when I jump the gun with only two."

### SELL SIGNAL: "Two Red Arrows"

**ANY TWO become true:**

1. Stochastic %K line < %D line (red crosses above black) ✗
2. MACD histogram < 0 (falls below centerline) ✗
3. Stock trading sideways (momentum stalls) ✗

**Phil Town's Rule**: "Get out when the stock stops going up and I get two reds."

### Visual Example

```
Date       | Price | 30-MA | MACD | Stoch | Signal
-----------|-------|-------|------|-------|--------
Jan 1      | $45   | $48   | -0.5 | Below | WAIT
Jan 15     | $50   | $48   | +0.2 | Below | WAIT (2 green)
Jan 20     | $52   | $49   | +0.8 | Above | BUY (3 green!)
Feb 1      | $60   | $55   | +1.2 | Above | HOLD
Feb 15     | $58   | $58   | +0.3 | Below | WATCH (1 red)
Feb 20     | $55   | $58   | -0.2 | Below | SELL (2 red!)
```

---

## The Rule #1 Trading Cycle

### Phase 1: Research (Fundamental Analysis)

1. Find company with strong Big Five (all 10%+ growth)
2. Verify 4 Ms (Meaning, Moat, Management, MOS)
3. Calculate Sticker Price and MOS Price
4. Add to watchlist

### Phase 2: Wait for Entry (Technical + Options)

**If price > MOS:**
1. Sell cash-secured puts at MOS strike (0.15-0.20 delta)
2. Collect premium while waiting (21-45 DTE)
3. If assigned: Get stock below MOS = perfect entry
4. If not assigned: Keep premium, repeat

**Wait for "Three Green Arrows":**
- Don't buy until ALL technical tools confirm
- Prevents buying into falling knife
- Confirms institutional buying

### Phase 3: Hold Position

1. Own wonderful company at attractive price
2. Monitor Big Five quarterly (fundamentals)
3. Watch for "Two Red Arrows" (technicals)
4. **Optional**: Sell covered calls near Sticker Price (0.15-0.20 delta, 30-45 DTE)
5. Collect additional income while holding

### Phase 4: Exit

**Exit on ANY of these:**

1. **Technical**: Two Red Arrows appear → Sell immediately
2. **Fundamental**: Big Five deteriorate → Sell regardless of price
3. **Valuation**: Price reaches Sticker Price → Take profit (or let calls assign)
4. **Opportunity**: Better Rule #1 stock found → Rotate capital

**Exit Rules Priority:**
- Technicals = SHORT-TERM timing (days to weeks)
- Fundamentals = LONG-TERM health (quarters to years)
- Use both: Exit fast on red arrows, exit permanently on deteriorating Big Five

---

## The Stockpiling Strategy (Payback Time)

### Core Concept

Buy MORE shares as price falls (dollar-cost averaging into Rule #1 stocks).

**When to Stockpile:**
- Stock meets Big Five criteria
- Price is at or below 50% of Sticker Price (MOS)
- Big Five remain strong (fundamentals intact)
- You have cash reserves to deploy

**Key Rules:**

1. **Qualification**:
   - Current price ≤ 50% of Sticker Price
   - Meets at least 4 of Big Five criteria
   - Payback Time < 10 years
   - Current price ≤ 80% of Sticker Price (conservative)

2. **Execution**:
   - Buy initial position at MOS price
   - If price drops 10-20%: Buy more (averaging down)
   - Continue buying as long as fundamentals hold
   - "Buying $10 bills for under $5"

3. **Cash Management**:
   - Never go all-in at once
   - Reserve cash for stockpiling if price drops
   - Save monthly to deploy when opportunities arise
   - Have patience - Mr. Market will offer sales

**Example:**

```
Sticker Price: $100
MOS Price: $50

Entry 1: Buy 100 shares at $50 (first entry at MOS)
Entry 2: Buy 100 shares at $45 (price drops 10%, fundamentals still strong)
Entry 3: Buy 100 shares at $40 (price drops more, still at discount)

Average cost: ($50 + $45 + $40) / 3 = $45 per share
Total investment: $13,500 in 300 shares
If price returns to Sticker: $30,000 value = 122% gain
```

**Risk Management:**
- ONLY stockpile if Big Five remain strong
- If fundamentals deteriorate: STOP buying, consider selling
- Set maximum % of portfolio per stock (diversification within Rule #1 universe)

---

## Position Sizing & Cash Management

### Phil Town's Position Sizing Rules

**Conservative Approach:**
- Very little diversification (8-10 stocks maximum)
- Concentrated positions in best ideas
- Only invest in stocks you deeply understand

**Cash Reserves:**
- Always keep cash for stockpiling opportunities
- Don't go all-in immediately
- Save monthly to deploy during market corrections
- "The rich have cash to buy when things are on sale"

**Risk Per Position:**
- No specific % mentioned in Rule #1
- Focus: Buy wonderful companies at MOS prices
- Natural risk management: 50% discount provides buffer
- Use stop-loss via "Two Red Arrows" technical exit

**Options Position Sizing:**
- Cash-secured puts: Must have 100% cash to buy stock if assigned
- Covered calls: Must own 100 shares per contract
- LEAPS: Use less capital than buying 100 shares outright

---

## Wonderful Company Universe (Examples)

### Tech with Moat:

- Apple (AAPL) - Brand + Ecosystem
- Microsoft (MSFT) - Switching Costs + Toll Bridge
- Google (GOOGL) - Secret (algorithm) + Toll Bridge

### Consumer with Brand:

- Coca-Cola (KO) - Brand
- Nike (NKE) - Brand
- Costco (COST) - Price

### Financial Toll Bridges:

- Visa (V) - Toll Bridge
- Mastercard (MA) - Toll Bridge
- Moody's (MCO) - Toll Bridge

### Healthcare with Secrets:

- Johnson & Johnson (JNJ) - Brand + Secrets
- UnitedHealth (UNH) - Switching Costs

---

## Key Principles Summary

1. **Never pay full price** - Always demand 50% MOS
2. **Only buy what you understand** - Circle of Competence
3. **Moat is everything** - No moat, no investment
4. **Management matters** - Owner-oriented leaders only
5. **Big Five must pass** - All 5, all timeframes, 10%+
6. **Use options to enhance** - Puts for entry, calls for exit
7. **Be patient** - Wait for the right price
8. **Think like an owner** - You're buying the business

---

## Metrics Quick Reference

| Metric       | Good | Great | Phil Town Minimum        |
| ------------ | ---- | ----- | ------------------------ |
| ROIC         | 10%+ | 15%+  | 10% (must be consistent) |
| Sales Growth | 10%+ | 15%+  | 10% over 1/5/10 years    |
| EPS Growth   | 10%+ | 15%+  | 10% over 1/5/10 years    |
| BVPS Growth  | 10%+ | 15%+  | 10% over 1/5/10 years    |
| FCF Growth   | 10%+ | 15%+  | 10% over 1/5/10 years    |
| MOS          | 30%+ | 50%+  | 50% (non-negotiable)     |

---

## Real Trade Example (Complete Cycle)

### Company: Apple (AAPL)

**Phase 1: Research & Valuation**

```
Company: Apple Inc. (AAPL)
Moat: Brand + Ecosystem (switching costs)
Management: Tim Cook (owner-oriented, 0.02% ownership + options)

Big Five (Historical):
- ROIC: 25%+ (excellent)
- Sales Growth: 12% (10-year avg)
- EPS Growth: 15% (10-year avg)
- BVPS Growth: 11% (10-year avg)
- FCF Growth: 14% (10-year avg)
✓ ALL pass 10%+ requirement

Sticker Price Calculation:
Current EPS: $6.00
Growth Rate: 12% (conservative)
Future PE: 24 (2 × 12)

Future EPS (10yr): $6.00 × (1.12)^10 = $18.63
Future Price: $18.63 × 24 = $447
Sticker Price: $447 / (1.15)^10 = $110
MOS Price (50%): $55

Current Price: $140
→ TOO EXPENSIVE, wait for entry
```

**Phase 2: Wait for Entry (Options Strategy)**

```
Date: Price drops to $75 (above MOS but moving down)

Action: Sell Cash-Secured Put
Strike: $55 (at MOS price, 0.18 delta)
Expiration: 35 DTE
Premium: $1.80 collected

Cash Reserved: $5,500 (ready to buy if assigned)

Outcome 1 (30 days later): Stock at $80, put expires worthless
→ Keep $180 premium
→ Sell another put, repeat

Outcome 2 (alternative): Stock drops to $52, assigned at $55
→ Effective cost: $55 - $1.80 = $53.20
→ Below MOS! Excellent entry!
```

**Phase 3: Technical Entry Confirmation**

```
Date: Stock assigned at $53.20, now monitoring technicals

Technical Check:
- Price vs 30-MA: $53 > $51 ✓ (Green Arrow 1)
- MACD: +0.3 (above zero) ✓ (Green Arrow 2)
- Stochastic: %K above %D ✓ (Green Arrow 3)

THREE GREEN ARROWS = Confirmed entry!

Position: 100 shares at $53.20 cost basis
Investment: $5,320
Target: $110 (Sticker Price)
```

**Phase 4: Hold & Generate Income**

```
Months 1-6: Stock rises to $85

Action: Sell Covered Call
Strike: $110 (at Sticker Price, 0.16 delta)
Expiration: 35 DTE
Premium: $2.50 collected

Monitor:
- Big Five still strong? ✓ Check quarterly
- Technicals green? ✓ Check weekly
- Stock below $110? ✓ Keep stock, keep premium

Monthly Income: $250 per month average
Cost Basis Reduction: $53.20 → $50.70 (after first call premium)
```

**Phase 5: Exit**

```
Scenario A (Technical Exit):
Date: Stock at $95, but MACD turns negative, Stochastic crosses down
TWO RED ARROWS = Sell immediately

Sell: 100 shares at $95
Cost: $53.20
Gain: $95 - $53.20 = $41.80 per share
Total Profit: $4,180 (79% return)
+ Covered call premiums: $750 (3 months × $250)
Total Return: $4,930 (93% return in 8 months)

Scenario B (Valuation Exit):
Date: Stock reaches $110 (Sticker Price)
Covered call at $110 assigned

Sell: 100 shares at $110
Cost: $53.20
Gain: $110 - $53.20 = $56.80 per share
Total Profit: $5,680 (107% return)
+ Covered call premiums: $1,250 (5 months × $250)
Total Return: $6,930 (130% return in 12 months)
```

---

## Common Mistakes to Avoid

### 1. Buying Without Three Green Arrows
**Mistake**: "The stock is at MOS price, I'll buy now even though MACD is negative."
**Consequence**: Catch falling knife, suffer drawdown
**Solution**: WAIT for all three technical confirmations

### 2. Selling Puts Above MOS Price
**Mistake**: "I'll sell puts at $70 because the premium is $3 (stock at $80, MOS is $55)."
**Consequence**: Assignment at $67 effective cost, still overvalued
**Solution**: Only sell puts AT or below MOS price

### 3. Ignoring Two Red Arrows
**Mistake**: "Stock is down 10% but Big Five still strong, I'll hold."
**Consequence**: Miss exit signal, watch gains evaporate
**Solution**: Exit on two red arrows, re-enter on three green arrows later

### 4. Selling Calls Below Sticker Price
**Mistake**: "I'll sell $90 calls for more premium (stock at $85, Sticker at $110)."
**Consequence**: Stock called away before reaching full value
**Solution**: Only sell calls AT or above Sticker Price

### 5. Not Having Cash to Get Assigned
**Mistake**: "I'll sell 5 puts for $500 premium without having $27,500 cash."
**Consequence**: Cannot fulfill assignment, forced to close at loss
**Solution**: Only sell cash-secured puts (100% cash reserved)

### 6. Holding Deteriorating Big Five
**Mistake**: "Stock is down but I believe in the story, I'll hold."
**Consequence**: Value trap, continued losses
**Solution**: Exit immediately if ANY of Big Five break 10% growth rule

### 7. Over-Diversification
**Mistake**: "I'll buy 30 different stocks to be safe."
**Consequence**: Diluted returns, can't track all positions
**Solution**: 8-10 wonderful companies maximum, deeply researched

### 8. Skipping the Research
**Mistake**: "Everyone says this stock is great, I'll buy at MOS price."
**Consequence**: Don't understand business, panic on volatility
**Solution**: Only invest within Circle of Competence

---

## Quick Reference Checklist

### Pre-Trade Checklist

**Fundamental (4 Ms):**
- [ ] Do I understand this business? (Meaning)
- [ ] Does it have a durable moat? (Moat)
- [ ] Is management owner-oriented? (Management)
- [ ] Is price ≤50% of Sticker Price? (Margin of Safety)

**Big Five:**
- [ ] ROIC ≥10% (1, 5, 10 years)?
- [ ] Sales Growth ≥10% (1, 5, 10 years)?
- [ ] EPS Growth ≥10% (1, 5, 10 years)?
- [ ] BVPS Growth ≥10% (1, 5, 10 years)?
- [ ] FCF Growth ≥10% (1, 5, 10 years)?

**Technical (Three Tools):**
- [ ] Price > 30-day Moving Average?
- [ ] MACD histogram > 0?
- [ ] Stochastic %K > %D?

**Options:**
- [ ] Cash-secured put at MOS price (if entering)?
- [ ] Covered call at Sticker Price (if exiting)?
- [ ] Do I have 100% cash if assigned (puts)?
- [ ] Do I own 100 shares per contract (calls)?

### During Trade Checklist

**Weekly Review:**
- [ ] Check Three Tools (looking for Two Red Arrows)
- [ ] Price still below Sticker Price?
- [ ] Any major news affecting moat?

**Quarterly Review:**
- [ ] Big Five still ≥10% growth?
- [ ] Management still owner-oriented?
- [ ] Moat widening or narrowing?
- [ ] Update Sticker Price with new data

### Exit Checklist

**Exit Immediately If:**
- [ ] Two Red Arrows appear (technical)
- [ ] ANY Big Five metric breaks <10% (fundamental)
- [ ] Management scandal or significant change
- [ ] Moat is deteriorating (competition increasing)

**Exit at Target If:**
- [ ] Price reaches Sticker Price (100% valuation)
- [ ] Better Rule #1 opportunity found (opportunity cost)

---

## Additional Resources

### Books
- **Rule #1** (2006) - Phil Town
  - Foundation: 4 Ms, Big Five, Sticker Price calculation
  - Focus: Long-term value investing
- **Payback Time** (2010) - Phil Town
  - Advanced: Stockpiling strategy, options overlay
  - Focus: Generating income during accumulation

### Podcast
- **InvestED: The Rule #1 Investing Podcast**
  - Hosts: Phil Town & Danielle Town
  - ~500 episodes (as of 2024)
  - Topics: Stock analysis, market timing, investor mindset
  - Real-time examples and case studies

### Website
- **RuleOneInvesting.com**
  - Free tools: Stock screener, calculators
  - Blog: Market commentary, education
  - Courses: Rule #1 University (paid)

### Technical Tools
- **Charting Platform** (any platform supporting):
  - 30-day Simple Moving Average
  - MACD with custom 8-17-9 settings
  - Stochastic with 14-5-0 settings
- **Free Options**: TradingView, Thinkorswim, Yahoo Finance

---

## Integration with Igor Trading System

### Alignment with Iron Condor Strategy

**Rule #1 → Iron Condors Translation:**

1. **Certainty (Rule #1)** → **High Probability (Iron Condors)**
   - Phil Town's 50% MOS = Igor's 15-delta (85% win rate)
   - Both prioritize NOT LOSING MONEY

2. **Income Generation (Covered Calls)** → **Premium Collection (Iron Condors)**
   - Phil Town: Sell calls at Sticker Price, collect premium
   - Igor: Sell call spreads 15-20 delta OTM, collect premium
   - Same concept: Get paid for waiting

3. **Downside Protection (Cash-Secured Puts)** → **Put Credit Spreads**
   - Phil Town: Sell puts at MOS, willing to own stock
   - Igor: Sell put spreads 15-20 delta OTM, defined risk
   - Same concept: Collect premium with protection

4. **Technical Timing (Three Tools)** → **Iron Condor Timing**
   - Phil Town: Buy on three greens, sell on two reds
   - Igor: Open iron condors when SPY shows neutral/range-bound technicals
   - Same concept: Use technicals for entry/exit timing

### Key Differences

| Phil Town (Stocks) | Igor (Options) |
|---|---|
| Buy wonderful companies | Trade SPY (diversified index) |
| Long-term hold (months-years) | Short-term trades (30-45 DTE) |
| Unlimited upside | Capped profit (iron condor max) |
| Requires stock research | No individual stock analysis |
| Income from covered calls | Income from both sides (calls + puts) |

### Complementary Use

**Best Practice**: Use BOTH strategies

- **Phil Town Rule #1**: Long-term wealth building (buy AAPL, MSFT at MOS)
- **Igor Iron Condors**: Monthly income generation (SPY iron condors for cash flow)

**Example Portfolio:**
- 70% Rule #1 stocks (AAPL, V, MA at MOS prices)
- 30% Cash for iron condors ($100K account → 2 iron condors at $5K risk each)
- Monthly income from iron condors: $400-800
- Long-term growth from Rule #1 stocks: 10-15% annually
- Total return: 20-30% annually

---

**Created**: December 17, 2025
**Updated**: February 5, 2026
**Purpose**: RAG knowledge base for Rule #1 options strategy
**Integration**: Used by `src/strategies/rule_one_options.py`
**Sources**: Rule #1 (2006), Payback Time (2010), InvestED Podcast, RuleOneInvesting.com, AAII Journal

---

## Sources

- [Rule #1 Investing - Official Website](https://www.ruleoneinvesting.com/)
- [Rule #1 Book - Amazon](https://www.amazon.com/Rule-Strategy-Successful-Investing-Minutes/dp/0307336840)
- [Rule #1 Book Overview - Shortform](https://www.shortform.com/blog/rule-1-book/)
- [Payback Time Book - Apple Books](https://books.apple.com/us/book/payback-time/id419923172)
- [The Stockpiling Approach - AAII Journal](https://www.aaii.com/journal/article/the-stockpiling-approach-to-stock-trading)
- [Trading Rule #1 Stocks - AAII Journal](https://www.aaii.com/journal/article/feature-trading-rule-1-stocks)
- [Phil Town's Technical Indicators Blog](https://philtown.typepad.com/phil_towns_blog/technical_indicators_tools/)
- [Rule #1 Options Trading - Official Blog](https://www.ruleoneinvesting.com/blog/how-to-invest/how-rule-1-options-trading-can-maximize-returns-while-minimizing-risk/)
- [InvestED Podcast - Apple Podcasts](https://podcasts.apple.com/us/podcast/invested-the-rule-1-investing-podcast/id1008452319)
- [LEAPS Options Strategy - Option Alpha](https://optionalpha.com/strategies/leaps)
- [Poor Man's Covered Call Guide - TradingBlock](https://www.tradingblock.com/strategies/poor-mans-covered-call-pmcc)
- [Moving Average Intervals - Rule #1 Blog](https://www.ruleoneinvesting.com/blog/stock-market-basics/moving-average/)
- [Why Stockpile - Rule #1 Blog](https://www.ruleoneinvesting.com/blog/how-to-invest/why-stockpile-instead-of-loading-up-all-at-once/)
