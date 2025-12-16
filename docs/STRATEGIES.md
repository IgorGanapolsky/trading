

# Trading Strategies Documentation

**Last Updated**: November 5, 2025
**Current Phase**: R&D Phase - Month 1 (Days 1-30)

## Overview

This document describes the trading strategies implemented in the autonomous trading system. The system uses a tiered approach with different risk profiles and investment allocations.

---

## Tier 1: Core ETF Strategy (60% Allocation)

**Daily Investment**: $6.00 (60% of $10/day)
**Risk Level**: LOW
**Target Return**: 8-12% annually

### Strategy Description
Conservative index ETF investing focused on broad market exposure through momentum-based selection among top ETFs. Includes equity ETFs (SPY, QQQ, VOO), bond ETF (BND), and REIT ETF (VNQ) for diversification per Benjamin Graham's Intelligent Investor principles, providing portfolio stability, risk reduction, and income generation.

### Universe
- **SPY**: S&P 500 ETF (equity)
- **QQQ**: Nasdaq-100 ETF (equity)
- **VOO**: Vanguard S&P 500 ETF (equity)
- **BND**: Vanguard Total Bond Market ETF (bonds) - Added November 25, 2025
- **VNQ**: Vanguard Real Estate Index Fund ETF (REITs) - Added November 27, 2025

### Selection Logic
1. Calculate momentum score for each ETF (equity, bond, and REIT)
2. Select ETF with highest momentum (may be equity, bond, or REIT based on market conditions)
3. Execute $6 buy order daily
4. Bond and REIT selection provides natural diversification when they outperform equities
5. REITs offer income generation through high dividend yields (~4-5%)

### Exit Rules
- Hold positions long-term (buy-and-hold)
- No stop-loss or take-profit targets
- Rebalancing only if momentum shifts dramatically

---

## Tier 2: Disruptive Innovation Strategy (20% Allocation)

**Daily Investment**: $2.00 (20% of $10/day)
**Risk Level**: MEDIUM
**Target Return**: 15-25% annually
**Last Updated**: November 5, 2025 - AMZN added to rotation

### Strategy Description
Growth stock picking focused on disruptive technology leaders with proven track records. Uses momentum-based rotation to select the strongest performer daily.

### Universe (3-Way Rotation)

| Symbol | Disruptive Theme | Catalyst |
|--------|------------------|----------|
| **NVDA** | AI Infrastructure | Leading AI chip manufacturer, dominant market position |
| **GOOGL** | Autonomous Vehicles + AI | Waymo leadership, AI integration across products |
| **AMZN** | OpenAI Deal + Cloud AI | $38B OpenAI partnership, AWS AI dominance, $295 fair value target |

### Selection Logic
1. Calculate momentum score for NVDA, GOOGL, and AMZN
2. Select stock with highest momentum score
3. Execute $2 buy order for selected stock

### Momentum Calculation
- Uses latest trade price from Alpaca
- Compares current price to historical average (simplified)
- Higher score = stronger momentum

### Exit Rules
- Hold positions for 2-4 weeks minimum
- 3% stop-loss (automatic exit if position drops 3%)
- 10% take-profit target (automatic exit if position gains 10%)
- Weekly review for technical deterioration

### AMZN Addition Rationale (Nov 5, 2025)
**Source**: YouTube analysis by Parkev Tatevosian, CFA
**Catalyst**: OpenAI $38B infrastructure deal announcement
**Fair Value**: $295 (15% upside from current $256)
**Risk/Reward**: Strong fundamentals + major catalyst = asymmetric upside

**Integration Date**: November 6, 2025 (tomorrow's execution)
**Impact**: Expands Tier 2 from 2-stock to 3-stock rotation, increasing diversification while maintaining $2/day allocation.

---

## Tier 3: IPO Strategy (10% Allocation)

**Daily Deposit**: $1.00 (10% of $10/day)
**Risk Level**: MEDIUM-HIGH
**Target Return**: 10-20% per IPO
**Status**: Manual tracking (reserve accumulation)

### Strategy Description
Accumulates $1/day in reserve for IPO opportunities via SoFi platform. Manual execution when compelling IPOs are available.

### Process
1. System tracks $1/day deposit to IPO reserve
2. Reserve accumulates until opportunity identified
3. CEO manually executes trades via SoFi when ready
4. System logs manual investments for performance tracking

### Current Reserve
Tracked in `data/manual_investments.json`

---

## Tier 4: Crowdfunding Strategy (10% Allocation)

**Daily Deposit**: $1.00 (10% of $10/day)
**Risk Level**: HIGH
**Target Return**: 100-1000% on winners (67% failure rate expected)
**Status**: Manual tracking (reserve accumulation)

### Strategy Description
Accumulates $1/day in reserve for equity crowdfunding opportunities on platforms like Wefunder, Republic, and StartEngine.

### Process
1. System tracks $1/day deposit to crowdfunding reserve
2. Reserve accumulates until opportunity identified
3. CEO manually evaluates and invests via crowdfunding platforms
4. System logs manual investments for performance tracking

### Current Reserve
Tracked in `data/manual_investments.json`

---

## Position Sizing & Risk Management

### Daily Investment Calculation
```python
DAILY_INVESTMENT = $10.00  # Fixed amount (Fibonacci strategy)

Tier 1 (Core):          $6.00 (60%)
Tier 2 (Growth):        $2.00 (20%)
Tier 3 (IPO Reserve):   $1.00 (10%)
Tier 4 (Crowd Reserve): $1.00 (10%)
```

### Risk Parameters
- **Minimum Position Size**: $50 (ensures profit after 0.18% trading fees)
- **Maximum Position Size**: 5% of portfolio
- **Stop-Loss (Tier 2)**: 3% below entry
- **Take-Profit (Tier 2)**: 10% above entry

### Circuit Breakers
- Daily loss limit: 2% of account value
- Maximum drawdown: 10%
- Consecutive losses: 3 (then halt trading)

---

## Performance Tracking

### Key Metrics
- **Total P/L**: Tracked in system_state.json
- **Win Rate**: % of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline

### Data Collection
System automatically collects historical data for:
- SPY, QQQ, VOO (Tier 1 universe)
- NVDA, GOOGL, AMZN (Tier 2 universe)
- 30-day lookback for momentum analysis

---

## Execution Schedule

**Market Hours**: 9:30 AM - 4:00 PM ET
**Daily Execution**: 9:35 AM ET (5 minutes after open)

### Automation Status
- **Script**: `scripts/autonomous_trader.py`
- **Scheduler**: GitHub Actions (Daily Trading Execution workflow)
- **Logs**: `data/trades_YYYY-MM-DD.json`
- **Performance**: `data/performance_log.json`

---

## Future Enhancements

### Planned Improvements
1. **MACD + RSI Integration**: Add technical indicators for better entry/exit timing
2. **Volume Confirmation**: Require above-average volume for Tier 2 selections
3. **Multi-LLM Analysis**: Enable OpenRouter AI consensus when profitable (Month 4+)
4. **Dynamic Position Sizing**: Adjust allocation based on volatility
5. **RL Agent Integration**: Reinforcement learning for strategy optimization

### Research Phase Goals (Days 1-90)
- **Month 1**: Infrastructure + data collection (current)
- **Month 2**: Build trading edge (MACD + RSI + Volume)
- **Month 3**: Validate & optimize (RL agent + news sentiment)

---

## Code Implementation

### Main Execution Script
`scripts/autonomous_trader.py`

Key functions:
- `execute_tier1()`: Core ETF selection and execution
- `execute_tier2()`: Growth stock rotation and execution
- `track_daily_deposit()`: Reserve accumulation for Tier 3/4
- `get_momentum_score()`: Momentum calculation for stock selection

### Strategy Modules
- `src/strategies/core_strategy.py`: Tier 1 implementation (ETF logic)
- `src/strategies/growth_strategy.py`: Tier 2 implementation (stock picking logic)
- `src/strategies/ipo_strategy.py`: Tier 3 analysis tools

---

## Historical Changes

### November 27, 2025
- **VNQ (REIT ETF) Added to Tier 1**: Expanded universe to include real estate investment trusts for diversification and income
- **Rationale**: REITs provide portfolio diversification (real estate behaves differently from stocks/bonds), high dividend yields (~4-5%), inflation hedge, and historical competitive returns (10.73% annualized 1994-2020). Follows Graham's diversification principles by adding another asset class.
- **Impact**: Natural diversification through momentum-based selection. System will automatically allocate to REITs when they outperform other asset classes. REITs provide income generation through required 90% dividend distribution.
- **REIT ETF**: VNQ (Vanguard Real Estate Index Fund ETF) - largest and most liquid REIT ETF, broad exposure to U.S. real estate
- **Execution Start**: November 27, 2025

### November 25, 2025
- **BND (Bond ETF) Added to Tier 1**: Expanded universe to include bonds for diversification
- **Rationale**: Follows Benjamin Graham's Intelligent Investor principles for defensive investors. Bonds provide portfolio stability, reduce volatility, and often move inversely to stocks. Current market conditions (Fed rate cuts expected) support bond allocation.
- **Impact**: Natural diversification through momentum-based selection. System will automatically allocate to bonds when they outperform equities, typically 10-15% of Tier 1 allocation.
- **Bond ETF**: BND (Vanguard Total Bond Market ETF) - broad exposure to U.S. investment-grade bonds
- **Execution Start**: November 25, 2025

### November 5, 2025
- **AMZN Added to Tier 2**: Expanded from 2-stock (NVDA, GOOGL) to 3-stock rotation
- **Rationale**: YouTube analysis identified OpenAI $38B deal catalyst
- **Impact**: Increased diversification, unchanged $2/day allocation
- **Execution Start**: November 6, 2025

### October 30, 2025
- **Tier 2 Simplified**: Reduced from full S&P 500 screening to NVDA + GOOGL focus
- **Rationale**: Conservative approach, proven disruptors, reliable momentum

### October 29, 2025
- **System Launch**: Initial deployment with 4-tier strategy
- **Starting Balance**: $100,000 paper trading account
- **Challenge Start**: Day 1 of 90-day R&D phase

---

## References

- [System State](../data/system_state.json) - Current system status and configuration
- [YouTube Analysis](youtube_analysis/CEO_SUMMARY_AMZN.md) - AMZN addition research
- [CLAUDE.md](../.claude/CLAUDE.md) - Project instructions and strategy documentation
- [README.md](../README.md) - Project overview and quickstart
