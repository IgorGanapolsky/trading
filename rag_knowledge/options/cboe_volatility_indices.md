# CBOE Volatility Indices - Comprehensive Guide

## Table of Contents
1. VIX Calculation Methodology
2. VIX9D (9-Day VIX)
3. VIX3M (3-Month VIX)
4. SKEW Index
5. Correlation Indices
6. Sector Volatility Indices

---

## 1. VIX Calculation Methodology

### Overview
The CBOE Volatility Index (VIX) represents the market's expectation of 30-day forward-looking volatility, derived from S&P 500 index options.

### Historical Evolution

#### Original VIX (1993-2003)
- **Methodology**: Black-Scholes implied volatility
- **Options Used**: Eight near-the-money S&P 100 (OEX) options
- **Limitation**: Limited strike range, less accurate

#### New VIX (2003-Present)
- **Methodology**: Model-free implied volatility
- **Options Used**: All out-of-the-money SPX options
- **Improvement**: More accurate, broader market representation

### Detailed Calculation Process

#### Step 1: Select Option Series
- **Near-Term**: First expiration with ≥8 days to maturity
- **Next-Term**: Second expiration immediately following near-term
- **Result**: Two option series spanning ~23-37 days

#### Example
```
Today: February 15
Near-Term: February 23 (8 days)
Next-Term: March 15 (28 days)

If February 23 has <8 days:
  Near-Term: March 15
  Next-Term: April 19
```

#### Step 2: Select Strike Prices
For each expiration, select strikes based on these rules:
1. **Find ATM Forward**: Calculate forward index level
2. **Select K₀**: First strike immediately below forward level
3. **Out-of-Money Puts**: All strikes below K₀ with bid > 0
4. **Out-of-Money Calls**: All strikes above K₀ with bid > 0
5. **Stop Rule**: Stop when two consecutive zero bids

#### Example Strike Selection
```
Forward Level (F): 4,500
K₀: 4,500 (ATM forward)

Selected Strikes:
Puts: 4,400, 4,410, 4,420, ..., 4,490, 4,500
Calls: 4,500, 4,510, 4,520, ..., 4,600, 4,610
(Assume bids exist for all these strikes)
```

#### Step 3: Calculate Variance for Each Term
The variance formula for each term:

```
σ² = (2/T) × Σ[(ΔKᵢ/Kᵢ²) × e^(RT) × Q(Kᵢ)] - (1/T) × [F/K₀ - 1]²

Where:
T = Time to expiration (in years)
Kᵢ = Strike price of ith option
ΔKᵢ = Interval between strike prices
    = (Kᵢ₊₁ - Kᵢ₋₁) / 2 for middle strikes
    = K₂ - K₁ for lowest strike
    = Kₙ - Kₙ₋₁ for highest strike
R = Risk-free interest rate
Q(Kᵢ) = Midpoint of bid-ask spread for option at strike Kᵢ
F = Forward index level
K₀ = First strike below the forward index level
```

#### Step 4: Interpolate to 30 Days
Since we have two expirations (near-term and next-term), we interpolate to get exactly 30 days:

```
σ²₃₀ = T₁σ₁² × [(NT₂ - N₃₀)/(NT₂ - NT₁)] + T₂σ₂² × [(N₃₀ - NT₁)/(NT₂ - NT₁)] × (N₃₀/N₃₀)

Where:
NT₁ = Minutes to near-term expiration
NT₂ = Minutes to next-term expiration
N₃₀ = Minutes in 30 days = 43,200
N₃₆₅ = Minutes in 365 days = 525,600
```

#### Step 5: Calculate VIX
```
VIX = 100 × √σ²₃₀
```

### Practical Example

#### Inputs
```
Near-Term (8 days to expiration):
- σ₁² = 0.0256 (16% annualized vol)
- NT₁ = 11,520 minutes (8 days × 24 hours × 60 min)

Next-Term (36 days to expiration):
- σ₂² = 0.0400 (20% annualized vol)
- NT₂ = 51,840 minutes (36 days × 24 hours × 60 min)

Target: 30 days
- N₃₀ = 43,200 minutes
```

#### Interpolation
```
Weight for near-term: (51,840 - 43,200)/(51,840 - 11,520) = 0.214
Weight for next-term: (43,200 - 11,520)/(51,840 - 11,520) = 0.786

σ²₃₀ = (8/365) × 0.0256 × 0.214 + (36/365) × 0.0400 × 0.786
     = 0.00012 + 0.00311
     = 0.00323

VIX = 100 × √0.00323 = 18.0%
```

### Key Insights from Methodology

#### 1. Model-Free
- **Advantage**: No assumptions about options pricing model
- **Result**: Represents true market expectations
- **Comparison**: Unlike Black-Scholes which assumes log-normal returns

#### 2. Forward-Looking
- **Nature**: Expected volatility, not historical
- **Timeframe**: Next 30 calendar days
- **Implication**: Can diverge significantly from realized volatility

#### 3. Variance Swap Replication
- **Theory**: VIX replicates variance swap rate
- **Practice**: Close approximation to fair value of volatility
- **Trading**: Can arbitrage VIX vs variance swaps

#### 4. Out-of-the-Money Options
- **Focus**: Uses OTM options (lower strike puts, higher strike calls)
- **Reason**: Cheaper, more liquid, capture tail risk
- **Skew**: Naturally incorporates volatility skew

### VIX Properties

#### Statistical Characteristics
- **Mean**: Long-term average ~19-20
- **Median**: Typically ~15-17 (skewed distribution)
- **Standard Deviation**: ~8-10 points
- **Range**: Historically 9-89, typically 10-40

#### Mean Reversion
- **Half-Life**: ~30-50 days (time to return halfway to mean)
- **Speed**: Fast spikes (1-3 days), slow declines (weeks to months)
- **Implication**: VIX above 30 usually temporary

#### Negative Correlation with S&P 500
- **Typical Correlation**: -0.70 to -0.80
- **Crisis Correlation**: Can reach -0.90 or higher
- **Implication**: VIX calls are effective portfolio hedge

#### Volatility of VIX (VVIX)
- **Definition**: Expected volatility of VIX itself
- **Typical Range**: 60-120
- **Calculation**: Same methodology, applied to VIX options
- **Use**: Gauge uncertainty about uncertainty

---

## 2. VIX9D (9-Day VIX)

### Overview
The CBOE 9-Day Volatility Index (VIX9D) represents the market's expectation of 9-day forward-looking volatility.

### Calculation Methodology
- **Similar to VIX**: Uses same model-free approach
- **Timeframe**: Interpolated to exactly 9 days
- **Options Used**: Near-term SPX options
- **Purpose**: Capture very short-term volatility expectations

### Why 9 Days?

#### Historical Context
- **Original CBOE**: Initially calculated 10-day VIX variant
- **Refinement**: 9 days found to be more stable
- **Practical**: Corresponds to ~2 trading weeks

#### Use Cases
1. **Short-Term Trading**: Day traders and swing traders
2. **Event Risk**: Measure volatility around specific events
3. **Term Structure**: Compare to VIX for short-term expectations
4. **Options Trading**: Price weekly options

### VIX9D vs VIX Comparison

| Metric | VIX9D | VIX |
|--------|-------|-----|
| **Timeframe** | 9 days | 30 days |
| **Volatility** | More volatile | Less volatile |
| **Mean Reversion** | Faster | Slower |
| **Correlation with Market** | Higher | High |
| **Typical Level** | Similar to VIX | Baseline |

### VIX9D Trading Signals

#### 1. VIX9D > VIX (Short-Term Fear)
- **Interpretation**: Near-term volatility expected to be higher
- **Cause**: Upcoming event (earnings, FOMC, geopolitical)
- **Trade**: Sell volatility after event (mean reversion)
- **Example**: VIX9D = 22, VIX = 18 (upcoming Fed meeting)

#### 2. VIX9D < VIX (Calm Near-Term)
- **Interpretation**: Near-term volatility expected to be lower
- **Cause**: Recent event resolved, calm expected
- **Trade**: Term structure plays (calendar spreads)
- **Example**: VIX9D = 15, VIX = 19 (post-earnings)

#### 3. VIX9D Spike > 10 Points
- **Interpretation**: Extreme short-term fear
- **Historical**: Often marks short-term bottoms
- **Trade**: Contrarian long equity or sell VIX calls
- **Risk**: Can spike further before reversal

### Practical Applications

#### Event Trading
```
Scenario: Apple earnings in 2 days
VIX9D: 16 → 20 (spike in short-term vol)
VIX: 15 → 16 (modest increase)

Trade: Sell AAPL weekly options (front-month)
Thesis: Volatility crush after earnings
Management: Close immediately after earnings
```

#### Term Structure Arbitrage
```
Normal Market:
VIX9D: 14
VIX: 16
Interpretation: Short-term calm, longer-term uncertain

Inverted (Stress):
VIX9D: 25
VIX: 20
Interpretation: Immediate event risk, then calm expected

Trade: Sell VIX9D (or short-dated SPX options), buy VIX protection
```

### Limitations

#### 1. Less History
- **Inception**: Launched September 2014
- **Data**: Less historical data than VIX (since 1990)
- **Backtesting**: Limited for long-term strategies

#### 2. No Tradeable Products
- **Limitation**: No VIX9D futures or options
- **Workaround**: Use weekly SPX options or VIX futures as proxy
- **Impact**: Harder to trade directly

#### 3. Higher Noise
- **Issue**: More volatile, more false signals
- **Solution**: Use in conjunction with VIX, not alone
- **Filtering**: Apply smoothing or confirmation filters

---

## 3. VIX3M (3-Month VIX)

### Overview
The CBOE 3-Month Volatility Index (VIX3M) measures market expectations of 93-day (approximately 3-month) volatility.

### Calculation Methodology
- **Same Model-Free Approach**: As VIX
- **Timeframe**: Interpolated to exactly 93 days
- **Options Used**: 3-4 month SPX options
- **Purpose**: Capture medium-term volatility expectations

### Why 3 Months?

#### Strategic Importance
1. **Quarterly Timeframe**: Aligns with earnings seasons
2. **Institutional Horizon**: Common hedging timeframe
3. **Economic Data**: Covers multiple Fed meetings, jobs reports
4. **Options Availability**: Corresponds to quarterly options expiration

### VIX3M vs VIX Comparison

| Metric | VIX3M | VIX |
|--------|-------|-----|
| **Timeframe** | 93 days (~3 months) | 30 days |
| **Volatility** | Less volatile | More volatile |
| **Mean Level** | Usually higher | Baseline |
| **Mean Reversion** | Slower | Faster |
| **Spikes** | Smaller, slower | Larger, faster |

### Term Structure Indicator

#### VIX/VIX3M Ratio
This ratio reveals market expectations for volatility trajectory:

```
Ratio = VIX / VIX3M

> 1.0: Inverted term structure (backwardation)
      Near-term volatility higher than longer-term
      Market stress, fear of immediate event

0.9-1.0: Flat term structure
        Uncertainty about volatility path
        Transitional market regime

< 0.9: Normal term structure (contango)
      Longer-term volatility higher than near-term
      Calm market, normal conditions
```

#### Historical Examples
```
COVID-19 Crash (March 2020):
VIX: 82.69
VIX3M: 61.43
Ratio: 1.35 (extreme backwardation)

Normal Market (Q1 2025):
VIX: 14.20
VIX3M: 16.80
Ratio: 0.85 (normal contango)
```

### Trading VIX3M Signals

#### 1. Steep Contango (VIX << VIX3M)
- **Signal**: Market expects volatility to increase over time
- **Interpretation**: Currently calm, but uncertainty ahead
- **Trade**: Buy longer-dated volatility (VIX calls, 3-month options)
- **Risk**: Volatility can stay low longer than expected

#### 2. Backwardation (VIX > VIX3M)
- **Signal**: Market expects volatility to decline
- **Interpretation**: Current stress expected to resolve
- **Trade**: Sell near-term volatility, buy long-term protection
- **Risk**: Stress can persist or worsen

#### 3. VIX3M Spike (>25)
- **Signal**: Longer-term uncertainty elevated
- **Interpretation**: Market sees sustained risk ahead
- **Trade**: Reduce equity exposure, buy long-dated puts
- **Historical**: Often precedes extended volatility periods

### VIX-VIX3M Spread

#### Calculation
```
Spread = VIX3M - VIX

Positive (Normal): VIX3M > VIX (contango)
Zero (Flat): VIX3M = VIX (transition)
Negative (Inverted): VIX3M < VIX (backwardation)
```

#### Typical Ranges
- **Calm Market**: Spread = +2 to +5 points
- **Normal Market**: Spread = 0 to +2 points
- **Stress Market**: Spread = -5 to 0 points
- **Crisis**: Spread < -10 points

#### Trading Strategies

##### Strategy 1: Mean Reversion
```
Entry: VIX-VIX3M spread < -5 (extreme backwardation)
Trade: Long VIX3M, Short VIX (via futures or options)
Thesis: Spread will normalize as fear subsides
Exit: Spread > 0 (normalized)
Risk: Crisis can worsen, spread can stay inverted
```

##### Strategy 2: Contango Capture
```
Entry: VIX-VIX3M spread > +5 (steep contango)
Trade: Short VIX3M (via selling long-dated SPX options)
Thesis: Volatility will not rise as expected
Exit: Spread < +2 (flattening)
Risk: Volatility can spike unexpectedly
```

### Institutional Applications

#### 1. Long-Term Hedging
- **Users**: Pension funds, endowments, insurance
- **Horizon**: 3-12 months
- **Instrument**: VIX3M-based collar strategies
- **Benefit**: More stable, less roll yield loss

#### 2. Risk Parity Strategies
- **Goal**: Balance risk across asset classes
- **Method**: Use VIX3M to adjust equity allocations
- **Rule**: Reduce equities when VIX3M > 20
- **Benefit**: Avoid major drawdowns

#### 3. Volatility Targeting
- **Strategy**: Maintain constant portfolio volatility
- **Indicator**: VIX3M as forward-looking volatility
- **Adjustment**: Scale position size inversely to VIX3M
- **Result**: Smoother equity curve

---

## 4. SKEW Index

### Overview
The CBOE SKEW Index measures the perceived tail risk of S&P 500 returns. It quantifies the probability of extreme negative moves.

### What is "Skew"?

#### Volatility Skew (Smirk)
- **Definition**: OTM puts trade at higher implied volatility than ATM options
- **Cause**: Demand for downside protection exceeds supply
- **Visual**: IV smile is asymmetric (skewed to put side)
- **Result**: Put options relatively expensive vs calls

### SKEW Index Calculation

#### Methodology
The SKEW Index is calculated from S&P 500 option prices, measuring the slope of the implied volatility curve.

```
SKEW = 100 - 10 × (Skewness of implied distribution)

Where:
Skewness = Measure of asymmetry in return distribution
Positive Skew = Fat right tail (unlikely large gains)
Negative Skew = Fat left tail (tail risk of large losses)
```

#### Interpretation
- **SKEW = 100**: Normal distribution (no skew)
- **SKEW = 115-120**: Typical range (moderate tail risk)
- **SKEW = 130-150**: High tail risk (crash probability elevated)
- **SKEW > 150**: Extreme tail risk (rare)

### SKEW vs VIX

| Metric | SKEW | VIX |
|--------|------|-----|
| **Measures** | Tail risk (fat tails) | Overall volatility |
| **Focus** | Extreme moves | All moves |
| **Correlation with Market** | Can be positive | Negative |
| **Typical Range** | 115-150 | 10-40 |
| **Spike Timing** | Before crashes | During crashes |

#### Key Difference
- **VIX**: "How much will the market move?"
- **SKEW**: "What's the probability of an extreme move?"

### SKEW Trading Signals

#### 1. High SKEW (>135)
- **Interpretation**: Market pricing in significant tail risk
- **Sentiment**: Complacency with a hint of fear
- **Historical**: Can persist for months
- **Trade**: Buy OTM puts (expensive but market agrees), sell ATM premium
- **Contrarian**: High SKEW can mean over-hedging, potential for rally

#### 2. Low SKEW (<120)
- **Interpretation**: Market complacent, not pricing tail risk
- **Sentiment**: Peak complacency
- **Historical**: Often precedes volatility events
- **Trade**: Buy cheap OTM puts as insurance
- **Risk**: Can stay low during long bull markets

#### 3. Rising SKEW
- **Interpretation**: Growing concern about tail events
- **Pattern**: Often rises before VIX (leading indicator)
- **Trade**: Reduce risk exposure, add hedges
- **Timing**: Can rise months before actual event

#### 4. Falling SKEW
- **Interpretation**: Tail risk concerns fading
- **Pattern**: Market confidence returning
- **Trade**: Can add risk exposure
- **Caution**: Ensure falling for right reasons (not complacency)

### SKEW and Market Crashes

#### Historical Patterns

##### 1987 Black Monday
- **Before**: SKEW data not available (index created later)
- **After**: Led to permanent shift in options pricing
- **Result**: Put skew became permanent feature

##### 2008 Financial Crisis
- **Lead-Up**: SKEW elevated (130-140) for months
- **Crisis**: VIX spiked, SKEW stayed elevated
- **Post-Crisis**: SKEW remained high (130+) for years

##### 2015 Flash Crash
- **Before**: SKEW at 140+
- **During**: Market dropped 10%, SKEW stayed high
- **After**: SKEW declined as volatility subsided

##### 2020 COVID Crash
- **Before**: SKEW elevated (135+) in January
- **During**: VIX spiked to 82, SKEW remained elevated
- **After**: SKEW slowly declined through 2020-2021

### Practical Applications

#### 1. Tail Risk Hedging
```
Strategy: Black Swan Protection
Entry: SKEW < 125 (tail risk cheap)
Trade: Buy far OTM SPX puts (10-15% OTM, 3-6 months)
Size: 1-2% of portfolio
Thesis: Cheap insurance against crash
Management: Roll forward quarterly, accept losses during calm
```

#### 2. Volatility Strategy Selection
```
High SKEW (>135):
  - Favor: Call spreads, put spreads (defined risk)
  - Avoid: Selling naked puts (tail risk high)
  - Rationale: Tail risk priced in, don't sell it

Low SKEW (<125):
  - Favor: Butterflies, iron condors (range-bound)
  - Avoid: Buying OTM puts (expensive relative to risk)
  - Rationale: Market calm, sell premium
```

#### 3. Market Regime Detection
```
Regime 1: Low VIX (<15), High SKEW (>135)
  Market: Calm with hidden tail risk
  Trade: Cautious, buy cheap OTM puts

Regime 2: High VIX (>25), High SKEW (>135)
  Market: Active volatility and tail risk
  Trade: Wait for mean reversion

Regime 3: Low VIX (<15), Low SKEW (<125)
  Market: Peak complacency
  Trade: Add hedges, reduce exposure

Regime 4: High VIX (>25), Low SKEW (<125)
  Market: Volatility without tail risk (unusual)
  Trade: Volatility likely to decline
```

### Limitations

#### 1. Not Tradeable
- **Issue**: No SKEW futures, options, or ETPs
- **Workaround**: Use as signal for options strategy selection
- **Alternative**: Trade VIX or SPX options based on SKEW

#### 2. Can Stay Elevated
- **Issue**: High SKEW can persist for years
- **Example**: Post-2008, SKEW averaged 130+
- **Implication**: High SKEW ≠ immediate crash

#### 3. Complex Calculation
- **Issue**: Opaque methodology, hard to independently verify
- **Impact**: Must trust CBOE calculation
- **Alternative**: Calculate own skew from option chain

---

## 5. Correlation Indices

### Overview
CBOE correlation indices measure the expected correlation between S&P 500 components.

### ICJ (Implied Correlation Index)

#### What It Measures
The expected correlation between S&P 500 constituent stocks over the next 3 months.

#### Calculation
```
ICJ = Weighted average correlation implied by:
  1. SPX index options (volatility of index)
  2. Individual stock options (volatility of components)

High ICJ: Stocks moving together (high correlation)
Low ICJ: Stocks moving independently (low correlation)

Formula (simplified):
ICJ ∝ σ²(SPX) / Σσ²(individual stocks)
```

#### Typical Range
- **Low**: 40-50 (stocks moving independently)
- **Normal**: 50-70 (moderate correlation)
- **High**: 70-90 (stocks moving together)
- **Extreme**: 90+ (crisis mode, everything correlated)

### Trading Correlation

#### High Correlation Regime (ICJ > 70)
- **Market State**: Crisis or transition
- **Stock Picking**: Less effective (everything moves together)
- **Diversification**: Reduced benefit
- **Volatility**: Likely elevated
- **Strategy**: Focus on index trades, not individual stocks

#### Low Correlation Regime (ICJ < 50)
- **Market State**: Calm, normal market
- **Stock Picking**: More effective (dispersion)
- **Diversification**: Greater benefit
- **Volatility**: Likely low
- **Strategy**: Stock-specific trades, sector rotation

### Dispersion Trading

#### What is Dispersion?
Trading the difference between index volatility and average stock volatility.

#### Dispersion = Individual Stock Vol - Index Vol

##### Long Dispersion
- **Trade**: Buy individual stock options, sell index options
- **Thesis**: Stocks will move independently (low correlation)
- **Profit**: When correlation falls (stocks diverge)
- **Example**: Buy AAPL/MSFT/GOOGL options, sell SPX options

##### Short Dispersion
- **Trade**: Sell individual stock options, buy index options
- **Thesis**: Stocks will move together (high correlation)
- **Profit**: When correlation rises (stocks converge)
- **Example**: Sell stock options, buy SPX options for hedge

### Correlation and Market Regimes

#### Rising Correlation
- **Indicator**: Market stress increasing
- **Timing**: Often precedes volatility spikes
- **Action**: Reduce single-stock exposure, add index hedges
- **Duration**: Can persist during entire crisis

#### Falling Correlation
- **Indicator**: Market normalizing
- **Timing**: Occurs during recovery
- **Action**: Increase stock-picking, reduce index hedges
- **Duration**: Gradual decline over months

### Practical Applications

#### 1. Portfolio Construction
```
High ICJ (>70):
  - Reduce stock count (correlation = redundancy)
  - Use index products (SPY, QQQ)
  - Focus on asset class diversification

Low ICJ (<50):
  - Increase stock count (diversification works)
  - Focus on stock selection
  - Sector diversification effective
```

#### 2. Options Strategy Selection
```
High Correlation:
  - Use index options (SPX, SPY)
  - Avoid stock-specific strategies
  - Reason: Stocks moving as unit

Low Correlation:
  - Use single-stock options
  - Stock-specific strategies effective
  - Reason: Dispersion creates opportunities
```

---

## 6. Sector Volatility Indices

### Overview
CBOE offers volatility indices for various market sectors, providing granular volatility insights.

### Major Sector Volatility Indices

#### GVZ (Gold Volatility Index)
- **Underlying**: Gold (GLD ETF options)
- **Use**: Gold market volatility expectations
- **Typical Range**: 12-25
- **Interpretation**: GVZ > 20 = high gold volatility expected

#### OVX (Oil Volatility Index)
- **Underlying**: Crude Oil (USO ETF options)
- **Use**: Oil market volatility expectations
- **Typical Range**: 20-50
- **Interpretation**: OVX > 40 = high oil volatility expected

#### VXAZN (Amazon Volatility Index)
- **Underlying**: Amazon (AMZN options)
- **Use**: AMZN-specific volatility
- **Range**: 25-60
- **Interpretation**: Single-stock volatility gauge

#### VXAPL (Apple Volatility Index)
- **Underlying**: Apple (AAPL options)
- **Use**: AAPL-specific volatility
- **Range**: 20-50
- **Interpretation**: Tech bellwether volatility

#### VXGOG (Google Volatility Index)
- **Underlying**: Alphabet (GOOGL options)
- **Use**: GOOGL-specific volatility
- **Range**: 25-55
- **Interpretation**: Tech giant volatility

### Using Sector Volatility

#### 1. Relative Value Analysis
Compare sector volatility to VIX:

```
Example:
VIX: 15 (S&P 500 volatility)
OVX: 35 (Oil volatility)

OVX/VIX Ratio: 2.33

Interpretation: Oil sector 2.3x more volatile than broad market
Trade Implication: Use narrower strikes for oil options
```

#### 2. Sector Rotation
```
High Sector Vol (relative to VIX):
  - Avoid or reduce exposure
  - Use smaller position sizes
  - Wider stops

Low Sector Vol (relative to VIX):
  - Potential opportunity
  - Larger position sizes
  - Tighter stops
```

#### 3. Earnings Volatility
```
Pre-Earnings:
VXAPL: 28
Post-Earnings:
VXAPL: 22

Volatility Crush: 21%
Trade: Sell options before earnings (collect elevated premium)
Risk: Large move exceeds premium collected
```

### Gold Volatility (GVZ)

#### GVZ Characteristics
- **Mean**: ~16-18
- **Range**: 10-35
- **Correlation with VIX**: Positive during crises (safe haven)
- **Drivers**: USD strength, real rates, geopolitical risk

#### GVZ Trading Signals

##### GVZ > VIX (Gold More Volatile)
- **Interpretation**: Gold uncertainty exceeding equity uncertainty
- **Drivers**: Currency crisis, inflation fears
- **Trade**: Gold volatility expensive, consider shorting
- **Alternative**: Buy gold directly, avoid options

##### GVZ < VIX (Gold Less Volatile)
- **Interpretation**: Gold calmer than equities
- **Drivers**: Stable macro environment
- **Trade**: Gold volatility cheap, consider buying
- **Alternative**: Use gold options for hedging

#### GVZ/VIX Ratio
```
Ratio > 1.0: Gold more volatile than equities (unusual)
Ratio 0.8-1.0: Balanced volatility
Ratio < 0.8: Gold less volatile (typical)

Extremes:
Ratio > 1.3: Gold crisis (2013 taper tantrum: GVZ spiked to 30)
Ratio < 0.6: Peak gold complacency
```

### Oil Volatility (OVX)

#### OVX Characteristics
- **Mean**: ~30-35
- **Range**: 18-80+
- **Correlation with VIX**: Low to moderate
- **Drivers**: Supply shocks, geopolitics, demand shifts

#### OVX Trading Signals

##### OVX > 40 (High Oil Volatility)
- **Interpretation**: Significant uncertainty in oil markets
- **Drivers**: Geopolitical events, supply disruptions
- **Trade**: Sell oil options premium (volatility mean reversion)
- **Risk**: Can spike further (2020: OVX hit 350+ during COVID)

##### OVX < 25 (Low Oil Volatility)
- **Interpretation**: Stable oil market
- **Drivers**: Balanced supply/demand
- **Trade**: Buy oil options as cheap hedges
- **Opportunity**: Position for next volatility spike

#### Historical OVX Spikes
```
2008 Financial Crisis: OVX → 80+
2014 Oil Crash: OVX → 60
2020 COVID & Negative Oil: OVX → 350+ (historic spike)
2022 Ukraine War: OVX → 70
```

### Single-Stock Volatility Indices

#### Why Trade Single-Stock Vol?
1. **Earnings Plays**: Sell premium before earnings
2. **Event Risk**: Price in mergers, FDA approvals
3. **Dispersion**: Trade individual vs index volatility
4. **Pair Trading**: Long one stock vol, short another

#### Stock Vol vs Index Vol

##### Stock Vol Typically Higher
```
VXAPL: 25
VIX: 15
Ratio: 1.67

Reason: Individual stocks more volatile than diversified index
Implication: Need wider profit ranges for single-stock strategies
```

##### Exceptions (Stock Vol < Index Vol)
- **Defensive Stocks**: Utilities, consumer staples
- **Post-Earnings**: Volatility crush after event
- **Mega-Caps**: AAPL, MSFT during calm periods

### Practical Trading Strategies

#### Strategy 1: Sector Rotation via Volatility
```
Step 1: Calculate vol ratios
  OVX/VIX, GVZ/VIX, VXAPL/VIX, etc.

Step 2: Rank sectors by relative volatility
  Lowest: Most stable, potential buy
  Highest: Most volatile, potential avoid

Step 3: Allocate
  Overweight low-vol sectors
  Underweight high-vol sectors

Step 4: Rebalance monthly
```

#### Strategy 2: Volatility Pairs Trade
```
Example: Tech Pair
Long: VXAPL (selling AAPL options)
Short: VXGOG (buying GOOGL options)

Thesis: AAPL volatility will decline relative to GOOGL
Entry: VXAPL/VXGOG > 1.1 (AAPL vol expensive)
Exit: VXAPL/VXGOG < 0.9 (reversion)
Risk: Both stocks move independently from expectations
```

#### Strategy 3: Pre-Earnings Vol Selling
```
Step 1: Identify earnings calendar (AAPL, AMZN, GOOGL)
Step 2: Check vol index (VXAPL, VXAZN, VXGOG)
Step 3: If Vol Index > 30-day average × 1.2:
  → Sell near-term options (iron condor, straddle)
Step 4: Close immediately after earnings (vol crush)
```

---

## Conclusion

CBOE volatility indices provide a comprehensive framework for understanding market expectations:

1. **VIX**: The cornerstone - 30-day S&P 500 volatility
2. **VIX9D**: Short-term volatility for event trading
3. **VIX3M**: Medium-term volatility for strategic positioning
4. **SKEW**: Tail risk gauge for crash protection
5. **Correlation Indices**: Measure of market cohesion
6. **Sector Vol Indices**: Granular volatility insights

### Key Trading Applications

#### Regime Detection
- **Calm**: VIX < 15, SKEW > 130, Low Correlation
  - Strategy: Sell premium, neutral strategies

- **Stress**: VIX > 25, SKEW > 135, High Correlation
  - Strategy: Buy protection, defined risk only

- **Crisis**: VIX > 40, SKEW > 140, Very High Correlation
  - Strategy: Cash, wait for mean reversion

#### Term Structure Trading
- **VIX9D vs VIX**: Short-term event risk
- **VIX vs VIX3M**: Medium-term volatility path
- **Backwardation**: Sell volatility (mean reversion)
- **Contango**: Buy long-term protection (cheap)

#### Sector Relative Value
- **Compare Sector Vol to VIX**: Find cheap/expensive volatility
- **Sector Rotation**: Favor low-vol sectors
- **Pairs Trading**: Long stable sector, short volatile sector

### Advanced Research Topics
- **Volatility Surface Dynamics**: How skew changes with vol
- **VIX Futures Curve**: Trading the term structure
- **Realized vs Implied Vol**: Volatility risk premium
- **Cross-Asset Volatility**: Correlations across asset classes

### Resources
- **CBOE.com**: Real-time indices, methodology white papers
- **VIX White Paper**: Full calculation methodology
- **CBOE Margin Calculator**: For complex options strategies
- **Options Industry Council**: Free education on volatility products

**Next Steps**: Apply these indices to develop systematic volatility trading strategies, backtest against historical data, and integrate into your options trading framework.
