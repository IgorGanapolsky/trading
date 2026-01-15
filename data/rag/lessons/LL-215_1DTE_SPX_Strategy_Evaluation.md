# LL-215: 1DTE SPX Credit Spread Strategy Evaluation

## Date: January 15, 2026
## Source: YouTube - "Make $260/Day Using ONLY $1,000!! Master Trading 1DTE SPX Credit Spread Options!"
## Verdict: FLUFF / NOT SUITABLE

## What Was Evaluated
- 1DTE (1 Day to Expiration) SPX Call Credit Spreads
- $1,000 collateral for 2 spreads → $260 profit (26%)
- Max loss: $740 (74% of collateral)
- Break-even win rate: 74%

## Why We Rejected It

### 1. Position Size Violation
- $1,000 collateral = 20% of our $5K account
- CLAUDE.md mandates: "NEVER more than 5% on single trade"
- $740 max loss = 15% account risk (3x our limit)

### 2. System Incompatibility
- Our system only allows SPY/IWM (hard-coded whitelist)
- SPX support unknown in Alpaca API
- Requires intraday monitoring (not automatable)

### 3. Strategy Conflicts
- 1DTE vs our 30-45 DTE approach
- No time to roll or adjust if wrong
- Higher gamma risk = large P/L swings

### 4. Red Flags
- Cherry-picked winning example
- No documented win rate over 30+ trades
- Clickbait title ("$260/Day" implies consistency)
- Requires discretionary chart analysis

## Math Comparison

| Metric | Our 30-45 DTE | 1DTE SPX |
|--------|---------------|----------|
| Break-even WR | 88% | 74% |
| Adjustability | Can roll | None |
| Automation | Possible | Requires human |
| Max Loss/Trade | $440 | $740 |

## Key Insight
Lower break-even (74%) sounds better, but:
- Achieving 74%+ on 1DTE is harder than 80%+ on 30-45 DTE
- No adjustment window means binary outcomes
- Our 50% early exit rule effectively lowers our break-even to ~75%

## Conclusion
1DTE strategies are gambling dressed up as trading. Our longer-dated approach allows mistakes to be fixed. Stick with 30-45 DTE SPY/IWM credit spreads.

## Tags
#options #credit-spreads #SPX #1DTE #evaluation #rejected
