# LL-309: Iron Condor Optimal Control Research

**Date**: 2026-01-25
**Category**: Research / Strategy Optimization
**Source**: arXiv:2501.12397 - "Stochastic Optimal Control of Iron Condor Portfolios"

## Key Findings

### 1. Asymmetric Left-Biased Structure is Optimal
- **Finding**: "Asymmetric, left-biased Iron Condor portfolios with τ = T are optimal in SPX markets"
- **Meaning**: Put spread should be closer to current price than call spread
- **Why**: Markets have negative skew (crashes more likely than rallies)

### 2. Optimal Exit Timing
- **Left-biased portfolios**: Hold to expiration (τ = T) is optimal
- **Non-left-biased portfolios**: Exit at 50-75% of duration
- **Our current rule**: Exit at 50% profit OR 7 DTE aligns with research

### 3. Deep OTM Risk Profile
- **Pro**: Higher profitability and success rates
- **Con**: Extreme loss potential in tail events
- **Mitigation**: Optimal stopping strategies reduce catastrophic losses

### 4. Asymmetric Strike Spacing
- Use different widths for put vs call spreads
- Not recommended: Symmetric iron condors in SPX markets

## Application to Our Strategy

### Current Setup (CLAUDE.md)
- 15-20 delta on both sides (symmetric)
- $5-wide wings
- 30-45 DTE, exit at 50% or 7 DTE

### Research-Backed Optimization
1. **Consider left-bias**: Put spread at 18-20 delta, Call spread at 12-15 delta
2. **Maintain 50% profit exit**: Research validates this for non-left-biased
3. **7 DTE exit**: Good for gamma risk avoidance (aligns with LL-268)

## Risk Metrics from Paper
- Optimal stopping strategies effectively reduce extreme losses
- Left-bias provides natural hedge against market crashes
- SPX/XSP inherently suited for this strategy

## Action Items
- [ ] Evaluate left-biased iron condors in paper trading
- [ ] Track performance difference: symmetric vs asymmetric
- [ ] Consider implementing after 90-day validation phase

## Prevention
1. Don't blindly follow symmetric delta rules
2. Consider market skew when positioning
3. Research-backed adjustments can improve risk-adjusted returns

## Sources
- [arXiv Paper](https://arxiv.org/abs/2501.12397)
- [Option Alpha Iron Condor Guide](https://optionalpha.com/strategies/iron-condor)
- [QuantStrategy Iron Condor Adjustments](https://quantstrategy.io/blog/how-to-build-and-adjust-the-iron-condor-strategy-for/)
