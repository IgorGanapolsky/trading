# Options Live Simulation

## Overview

The Options Live Simulation system evaluates and executes theta harvest opportunities in paper trading mode, accelerating progress toward the $100/day net profit goal.

## Key Features

- **Equity Gates**: Unlocks strategies based on account equity:
  - **$5k+**: Poor man's covered calls (long ITM leap + short 20-delta weekly)
  - **$10k+**: Iron condors on broad indices (QQQ, SPY) in calm regime
  - **$25k+**: Full options suite including undefined-risk strategies

- **IV Percentile Filter**: Only sells premium when IV percentile > 50% (ensures we're getting paid for volatility)

- **Regime-Aware**: Adapts strategy selection based on market regime:
  - **Calm**: Iron condors enabled
  - **Trending**: Poor man's covered calls preferred
  - **Volatile/Spike**: Reduced or paused options activity

- **Daily Premium Target**: Targets $10/day premium (configurable via `THETA_TARGET_DAILY`)

## Usage

### Standalone Execution

```bash
# Paper trading mode (default)
python scripts/options_live_sim.py

# Live trading mode (requires explicit flag)
python scripts/options_live_sim.py --live

# Custom symbols
python scripts/options_live_sim.py --symbols SPY QQQ IWM TLT

# Skip system_state.json update
python scripts/options_live_sim.py --skip-update
```

### Integrated Execution

The script is automatically called after daily equity trading execution via `autonomous_trader.py`. Enable/disable via environment variable:

```bash
# Enable (default)
ENABLE_OPTIONS_SIM=true

# Disable
ENABLE_OPTIONS_SIM=false
```

## Output

### Console Output

```
================================================================================
OPTIONS LIVE SIMULATION
Mode: PAPER
================================================================================
Account Equity: $100,005.50
Market Regime: calm
Equity Gate Status: {'theta_enabled': True, 'enabled_strategies': {...}}
Target Daily Premium: $10.00
Total Estimated Premium: $8.50/day
Premium Gap: $1.50
Opportunities Found: 2
  🎯 SPY - poor_mans_covered_call x1 ($35.00 premium, IV: 65.2%)
  🎯 QQQ - iron_condor x1 ($50.00 premium, IV: 58.1%)
✅ Theta harvest plan saved to data/options_signals/theta_harvest_2025-12-02T09-35-00Z.json
```

### JSON Output

Plans are saved to `data/options_signals/theta_harvest_*.json`:

```json
{
  "generated_at": "2025-12-02T09:35:00Z",
  "account_equity": 100005.50,
  "equity_gate": {
    "account_equity": 100005.50,
    "enabled_strategies": {
      "poor_mans_covered_call": true,
      "iron_condor": true,
      "full_suite": false
    },
    "next_tier": "full_suite",
    "gap_to_next_tier": 14994.50,
    "theta_enabled": true
  },
  "regime": "calm",
  "target_daily_premium": 10.0,
  "opportunities": [
    {
      "symbol": "SPY",
      "strategy": "poor_mans_covered_call",
      "contracts": 1,
      "estimated_premium": 35.0,
      "executed": false,
      "reason": "Signal ready for poor_mans_covered_call",
      "iv_percentile": 65.2
    }
  ],
  "total_estimated_premium": 8.50,
  "premium_gap": 1.50,
  "on_track": false,
  "summary": "Found 2 theta opportunities. Est. daily premium: $8.50 (gap: $1.50)"
}
```

### System State Integration

Options metrics are automatically added to `data/system_state.json`:

```json
{
  "options": {
    "last_theta_harvest": "2025-12-02T09:35:00Z",
    "account_equity": 100005.50,
    "equity_gate": {...},
    "target_daily_premium": 10.0,
    "total_estimated_premium": 8.50,
    "premium_gap": 1.50,
    "opportunities_count": 2,
    "on_track": false
  }
}
```

## Strategy Details

### Poor Man's Covered Call ($5k+)

- **Setup**: Long ITM leap (6-12 months) + short 20-delta weekly call
- **Premium**: ~$35/week per contract
- **Daily Equivalent**: ~$5/day per contract
- **Risk**: Defined (max loss = leap cost - premium received)
- **Best For**: Bullish signals in calm/trending regimes

### Iron Condor ($10k+)

- **Setup**: Sell OTM put spread + sell OTM call spread
- **Premium**: ~$50/month per contract (5-wide)
- **Daily Equivalent**: ~$1.67/day per contract
- **Risk**: Defined (max loss = spread width - premium)
- **Best For**: Calm regimes with neutral outlook

## Configuration

### Environment Variables

```bash
# Equity thresholds
THETA_STAGE_1_EQUITY=5000      # Poor man's covered calls
THETA_STAGE_2_EQUITY=10000      # Iron condors
THETA_STAGE_3_EQUITY=25000      # Full suite

# IV filter
IV_PERCENTILE_THRESHOLD=50     # Minimum IV percentile to sell

# Daily premium target
THETA_TARGET_DAILY=10.0        # Target daily premium ($/day)

# Enable/disable
ENABLE_OPTIONS_SIM=true        # Enable options simulation
```

## Integration with Daily Trading

The script runs automatically after equity execution:

1. **Equity Trading** → Executes stock/ETF positions
2. **Options Simulation** → Evaluates theta opportunities
3. **Plan Generation** → Creates actionable plan with opportunities
4. **State Update** → Updates `system_state.json` with metrics
5. **Dashboard** → Progress Dashboard shows options metrics

## Monitoring

### Progress Dashboard

The wiki Progress Dashboard automatically includes options metrics:
- Current equity vs gates
- Enabled strategies
- Daily premium run-rate vs target
- Premium gap to target
- Opportunities found

### Logs

Options simulation logs are written to:
- Console output (via `setup_logging()`)
- `logs/trading.log` (if configured)
- GitHub Actions artifacts (when run via CI)

## Roadmap

### Month 4+ (Current)

- ✅ Equity gate evaluation
- ✅ IV percentile filtering
- ✅ Regime-aware strategy selection
- ✅ Plan generation and persistence
- ✅ System state integration

### Future Enhancements

- [ ] Actual order execution (currently simulation only)
- [ ] Position management (rolls, exits)
- [ ] Multi-leg strategy builder
- [ ] Greeks monitoring (delta, gamma, theta, vega)
- [ ] Portfolio-level risk limits
- [ ] Backtesting framework for options strategies

## Troubleshooting

### "Theta strategies disabled"

**Cause**: Account equity below $5k threshold

**Solution**:
- Continue building equity via daily $10/day input
- Options unlock automatically at $5k equity
- Check `equity_gate.gap_to_next_tier` in plan output

### "No qualifying theta opportunities found"

**Causes**:
1. IV percentile < 50% (not enough volatility premium)
2. Regime not suitable (e.g., spike regime pauses trading)
3. No bullish signals for covered calls

**Solution**:
- Wait for IV to rise (check VIX levels)
- Review regime detection (`RegimeDetector`)
- Check signal generation (`RuleOneOptionsStrategy`)

### "IV percentile calculation failed"

**Cause**: Insufficient historical data or API error

**Solution**:
- Script falls back gracefully (continues without IV filter)
- Check yfinance API connectivity
- Verify symbol has sufficient trading history

## References

- [Options Profit Planner](../src/analytics/options_profit_planner.py)
- [Rule #1 Options Strategy](../src/strategies/rule_one_options.py)
- [Regime Detector](../src/utils/regime_detector.py)
- [Options Profit Roadmap](./options-profit-roadmap.md)
