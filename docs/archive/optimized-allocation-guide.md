# Optimized $10/Day Allocation Guide

## Overview

This guide explains the new optimized allocation strategy designed to maximize compound growth for the $10/day investment budget.

## New Allocation Breakdown

| Asset Class | Allocation | Daily Amount | Purpose |
|------------|-----------|--------------|----------|
| **Core ETFs** | 40% | $4.00 | Momentum-selected SPY/QQQ for stable growth |
| **Bonds + Treasuries** | 15% | $1.50 | Risk mitigation via BND + SHY/IEF/TLT ladder |
| **REITs** | 15% | $1.50 | Dividend income via VNQ (real estate exposure) |
| **Crypto** | 10% | $1.00 | Weekend BTC/ETH volatility capture |
| **Growth Stocks** | 15% | $1.50 | High-conviction NVDA/GOOGL/AMZN |
| **Options Reserve** | 5% | $0.50 | Premium accumulation for covered calls |

**Total: 100% = $10.00/day**

## Key Benefits

### 1. Risk-Adjusted Portfolio (30% defensive)
- Bonds + REITs provide stability during market downturns
- Treasury ladder (SHY/IEF/TLT) hedges against recession
- Reduces overall portfolio volatility

### 2. Income-Focused Strategy
- REITs generate dividend income
- Future options strategy generates premium income
- Multiple income streams = faster compounding

### 3. 7-Day Trading Capability
- Crypto trades on weekends when equity markets are closed
- Captures volatility in 24/7 markets
- Maximizes capital efficiency

### 4. Compound-Ready Architecture
- Options reserve accumulates for covered call strategy
- Once 50+ shares accumulated, can sell weekly calls
- Example: 50 NVDA shares @ $0.50/week = $26/month passive income

## Comparison to Legacy Allocation

### Legacy (OLD):
- Tier 1 (60%): Core ETFs → $6.00/day
- Tier 2 (20%): Growth stocks → $2.00/day
- Tier 3 (10%): IPOs (manual) → $1.00/day
- Tier 4 (10%): Crowdfunding (manual) → $1.00/day

### Optimized (NEW):
- Core ETFs (40%): → $4.00/day
- Bonds + Treasuries (15%): → $1.50/day ✨ NEW
- REITs (15%): → $1.50/day ✨ NEW
- Crypto (10%): → $1.00/day ✨ NEW
- Growth Stocks (15%): → $1.50/day
- Options Reserve (5%): → $0.50/day ✨ NEW

**Key Changes:**
- ✅ Reduced core ETF allocation from 60% → 40% (less concentration risk)
- ✅ Added bonds/treasuries for stability
- ✅ Added REITs for dividend income
- ✅ Added crypto for weekend trading
- ✅ Added options reserve for yield generation
- ✅ Removed manual IPO/crowdfunding (not automated)

## How to Enable

### Option 1: Environment Variable (Recommended)

Add to your `.env` file:
```bash
USE_OPTIMIZED_ALLOCATION=true
```

### Option 2: Programmatic

```python
from src.core.config import load_config

config = load_config()
config.USE_OPTIMIZED_ALLOCATION = True

# Get tier allocations
allocations = config.get_tier_allocations()
print(allocations)
# Output:
# {
#   'core_etfs': 4.0,
#   'bonds_treasuries': 1.5,
#   'reits': 1.5,
#   'crypto': 1.0,
#   'growth_stocks': 1.5,
#   'options_reserve': 0.5
# }
```

### Option 3: Dynamic Scaling

The allocation scales automatically with `DAILY_INVESTMENT`:

```python
from src.core.config import load_config

config = load_config()
config.USE_OPTIMIZED_ALLOCATION = True
config.DAILY_INVESTMENT = 20.0  # 2x scale

allocations = config.get_tier_allocations()
print(allocations)
# Output:
# {
#   'core_etfs': 8.0,        # 40% of $20 = $8
#   'bonds_treasuries': 3.0,  # 15% of $20 = $3
#   'reits': 3.0,            # 15% of $20 = $3
#   'crypto': 2.0,           # 10% of $20 = $2
#   'growth_stocks': 3.0,    # 15% of $20 = $3
#   'options_reserve': 1.0   # 5% of $20 = $1
# }
```

## Implementation Status

### ✅ Completed
- Configuration structure in `src/core/config.py`
- Allocation constants and validation
- Helper method `get_tier_allocations()`
- Documentation

### 🔨 In Progress
- Integration with orchestrator
- Strategy implementations for new asset classes:
  - Bonds/Treasury ladder strategy
  - REIT strategy (VNQ)
  - Options accumulation strategy (already exists)

### 📋 TODO
- Update `scripts/autonomous_trader.py` to use optimized allocation
- Create bond strategy (`src/strategies/bond_strategy.py`)
- Create REIT strategy (`src/strategies/reit_strategy.py`)
- Update daily execution logic
- Backtest optimized allocation

## Asset Selection Rationale

### Bonds + Treasuries (BND, SHY, IEF, TLT)
- **BND** (Vanguard Total Bond Market ETF): Broad bond exposure
- **SHY** (1-3 Year Treasury): Short-term, low volatility
- **IEF** (7-10 Year Treasury): Medium-term, moderate yield
- **TLT** (20+ Year Treasury): Long-term, recession hedge

### REITs (VNQ)
- **VNQ** (Vanguard Real Estate ETF):
  - Dividend yield: ~3-4%
  - Broad real estate exposure
  - Inflation hedge
  - Low correlation with stocks

### Crypto (BTC/USD, ETH/USD)
- Weekend trading capability
- High volatility = opportunity for gains
- 24/7 market access
- Diversification beyond traditional assets

### Options Reserve
- Accumulates capital for covered call strategy
- Target: Build to 50+ shares of high-premium stocks
- Example ROI: 50 NVDA shares selling weekly calls = $100-200/month

## Expected Performance

### Conservative Estimate
- Core ETFs (40%): 10% annual return → +$0.40/year per $1 invested
- Bonds (15%): 4% annual return → +$0.60/year per $1 invested
- REITs (15%): 8% annual return (4% dividend + 4% growth) → +$1.20/year per $1 invested
- Crypto (10%): 15% annual return → +$1.50/year per $1 invested
- Growth (15%): 20% annual return → +$3.00/year per $1 invested
- Options (5%): 50% annual return (premium income) → +$25/year per $1 invested

**Blended Annual Return: ~12-15%**

### With Compounding
- Month 1: $10/day × 22 days = $220 → $220 equity
- Month 2: $10/day × 22 days = $220 → $441 equity (+1% monthly growth)
- Month 3: $10/day × 22 days = $220 → $665 equity
- Month 6: ~$1,500 equity
- Month 12: ~$3,200 equity (includes 12-15% annual return)

## Risk Considerations

### Downside Protection
- 30% in defensive assets (bonds + REITs)
- Diversification across 6 asset classes
- Reduced concentration risk vs legacy allocation

### Volatility Management
- Bonds offset equity volatility
- REITs provide steady dividend income
- Treasury ladder provides liquidity at different maturities

### Recession Hedge
- Long-term treasuries (TLT) perform well in recessions
- REITs provide real asset exposure
- Diversification reduces systemic risk

## Migration Path

### Phase 1: Testing (Weeks 1-2)
- Enable optimized allocation in paper trading
- Monitor performance vs legacy allocation
- Validate strategy implementations

### Phase 2: Pilot (Weeks 3-4)
- Deploy with 50% of capital using optimized allocation
- 50% continues with legacy allocation
- Compare results

### Phase 3: Full Deployment (Week 5+)
- Switch 100% to optimized allocation if outperforming
- Document lessons learned
- Iterate on asset selection

## Monitoring Metrics

Track these metrics to validate optimization:
- Sharpe Ratio (target: >1.5)
- Max Drawdown (target: <10%)
- Win Rate (target: >60%)
- Income Generated (dividends + premiums)
- Volatility (target: lower than legacy)

## Questions?

See also:
- `docs/profit-optimization.md` - Cost-benefit analysis
- `docs/r-and-d-phase.md` - R&D phase strategy
- `.claude/CLAUDE.md` - Overall project context

---

**Last Updated:** 2025-12-02
**Status:** Configuration complete, strategy implementation pending
