# Profit Optimization Strategies

This document outlines the three key strategies for maximizing profitability and efficiency in the AI Trading System.

---

## Dynamic Budget & Tax Enhancements (Dec 2025)

### Auto-Scaling Daily Input

- `scripts/autonomous_trader.py` now inspects `data/system_state.json` (or `SIMULATED_EQUITY`) before the orchestrator spins up.
- The new `calc_daily_input()` helper maps equity into a $10–$50/day deployment, adding extra basis points at the $2k / $5k / $10k gates while preserving the risk cap.
- The resulting number is exported via `DAILY_INVESTMENT`, so every downstream component (tier budgets, risk manager, trade gateway) automatically receives the right daily budget without editing `.env`.

### Tax Sweep Guidance

- `scripts/generate_telemetry_report.py` now prints the latest equity/P&L plus a recommended tax sweep (default 28%) when cumulative profit is positive.
- Use `--tax-rate` to align with your local marginal bracket; the recommendation is stored in the JSON output for dashboards/Slack pings.
- This keeps the HYSA/tax bucket honest and enforces the “sweep 28% of realized gains quarterly” directive automatically.

---

## 1. Alpaca High-Yield Cash (3.56% APY)

**Discovered**: October 30, 2025 (Alpaca rate update email)

### Key Features

- **APY**: 3.56% (nearly 10x national average of 0.40%)
- **FDIC Insurance**: Up to $1M
- **Liquidity**: Full - can use as buying power anytime
- **Cost**: $0 - automatically earns on idle cash

### How This Boosts Fibonacci Strategy

1. **Profit Buffer Growth**: When we make $1 profit in Phase 1, that $1 earns 3.56% APY while we wait to accumulate enough to scale to $2/day
2. **Passive Income Layer**: Even uninvested cash generates returns
3. **Compounding Multiplier**: Every dollar waiting to be deployed is earning interest

### Example Math

```
Phase 1: Make $60 profit → Move to $2/day Phase
While waiting (30 days): $60 × 3.56% APY = ~$0.18 extra
Phase 2: Make $90 profit → Move to $3/day Phase
While waiting (30 days): $150 × 3.56% APY = ~$0.44 extra
...continues exponentially
```

### When We Can Use This

- ❌ NOT available during paper trading (current phase)
- ✅ Only available with LIVE account + real money
- ✅ Must meet balance or income requirements
- ✅ Cannot be a Pattern Day Trader

### Timeline

- **Now (Days 1-30)**: Paper trading - High-Yield Cash NOT available
- **Month 2+**: Switch to live $1/day Fibonacci strategy → THEN enroll in High-Yield Cash
- **Benefit Starts**: When we have real cash accumulating between Fibonacci phases

### Action Items (Future - After Going Live)

- [ ] Switch from paper to live account (Month 2)
- [ ] Enroll in Alpaca High-Yield Cash program
- [ ] Track High-Yield Cash earnings in daily reports
- [ ] Include passive interest in profit calculations

### Margin Rate Warning ⚠️

- Alpaca margin costs 6.5% (base rate + 2.5%)
- High-Yield Cash earns 3.56%
- **Negative spread** = NEVER use margin
- **Strategy**: Only trade with cash we have

---

## 2. OpenRouter Multi-LLM Strategy (Cost-Benefit Analysis)

**Current Status**: October 30, 2025 - Security incident resolved

### Security Incident

- ❌ Old API key exposed in git history (commit d3fa92d)
- ✅ OpenRouter automatically disabled exposed key
- ✅ New API key created and secured in .env
- ✅ .env verified in .gitignore (will NOT be committed)
- ⚠️ Old key still in git history but disabled by OpenRouter

### Integration Status

- ✅ MultiLLMAnalyzer fully built and integrated into CoreStrategy
- ✅ Configured with 3 models: Claude 3.5 Sonnet, GPT-4o, Gemini 2 Flash
- ✅ Code supports `use_sentiment=True` flag
- ❌ Currently NOT calling AI during trades (making simple buy orders)

### Cost Analysis

| Model | Cost per 1M tokens | Input | Output |
|-------|-------------------|--------|---------|
| Claude 3.5 Sonnet | $3/$15 | In/Out | Deep analysis |
| GPT-4o | $2.50/$10 | In/Out | Reasoning |
| Gemini 2 Flash | $0.075/$0.30 | In/Out | Fast sentiment |

### Estimated Costs If Enabled

- Daily: 3 models × 2 calls × ~1000 tokens = $0.50-2/day
- Monthly: $15-60 for AI analysis
- Annually: $180-720

### Decision: When to Enable OpenRouter

#### Phase 1 (Now - Days 1-30): ❌ DISABLED

- Current: Paper trading with simple buy orders ($10/day)
- Profit: $0.02/day (essentially break-even)
- Analysis: NOT worth spending $15-60/month for $0.02/day profit
- Purpose: Testing infrastructure, not making real money yet

#### Phase 2 (Month 2-3): ❌ STILL DISABLED

- Live $1/day Fibonacci strategy with RL system
- Projected: $1-3/day profit
- Analysis: NOT worth spending $2/day AI cost when making $1-3/day
- Purpose: Validate RL system profitability first

#### Phase 3 (Month 4+): ✅ ENABLE WHEN PROFITABLE

- Scaled to $5-13/day Fibonacci phases
- Projected: $10-50/day profit
- Analysis: **Worth enabling** - $2/day AI cost becomes negligible
- Purpose: Multi-LLM consensus improves market regime detection
- ROI: If AI improves returns by 10-20%, pays for itself immediately

### Enable OpenRouter When

```python
# Conditions to enable:
if (
    daily_profit > 10  # Making $10+/day consistently
    and fibonacci_phase >= 5  # At $5/day investment phase or higher
    and rl_sharpe_ratio > 1.0  # RL system validated
):
    use_sentiment = True  # Enable multi-LLM analysis
```

### What OpenRouter Will Do (When Enabled)

- Market sentiment analysis (3-model consensus)
- Risk-off detection (market crashes, volatility spikes)
- Sector rotation signals (which sectors to weight)
- Entry/exit timing optimization
- News sentiment integration

### Action Items

- [ ] Keep OpenRouter integrated but disabled (current)
- [ ] Monitor profit levels in Month 4+
- [ ] Enable when making $10+/day consistently
- [ ] Track ROI: Does AI improve returns enough to justify cost?

---

## 3. Claude Batching Strategy (Prevent Token Exhaustion)

**Problem**: Running out of Claude tokens daily, interrupting progress

**Solution**: Agent parallelization via Claude Agents SDK

### Key Strategies

Based on [Agent Swarm Best Practices](https://adrianco.medium.com/vibe-coding-is-so-last-month-my-first-agent-swarm-experience-with-claude-flow-414b0bd6f2f2):

1. **Batch Agent Swarms**: Spawn multiple agents in parallel using Task tool
   - Example: "Spawn 5 agents in parallel to work through remaining tasks"
   - Reduces total time and maximizes output per token

2. **Work Incrementally**: Break work into smaller focused batches
   - One batch for planning
   - One batch for implementation
   - One batch for testing

3. **Upgrade Plan If Needed**:
   - Pro: $20/mo
   - Elite: $200/mo (20x more than Pro)
   - Monitor usage and adjust

4. **Pause When Credits Exhausted**:
   - Review output
   - Document progress
   - Clean up code
   - Resume when credits refresh

### Implementation Guidelines

- ALWAYS use parallel Task tool calls when possible
- Launch 3-5 agents simultaneously for research
- Use specialized agent types (general-purpose, Explore, Plan)
- Work in focused batches rather than trying to complete everything at once

### Claude Batching Skill (Future)

- Could create a skill to manage agent spawning
- Track token usage across tasks
- Optimize batch sizes for efficiency
- Auto-pause before exhaustion

---

---

## 4. Auto-Input Scaling (Compounding Accelerator)

**Added**: December 2, 2025 (theta-scale branch)

### Overview

Dynamic daily input scaling based on account equity to accelerate compounding:

```python
def calc_daily_input(equity: float) -> float:
    base = 10.0  # Minimum daily input
    if equity >= 10000:
        base += 4.0 * ((equity - 10000) / 1000)  # +$4 per $1k above $10k
        base += 4.0 + 0.4  # Tier bonuses
    elif equity >= 5000:
        base += 0.3 * ((equity - 5000) / 1000) * 10
        base += 0.4
    elif equity >= 2000:
        base += 0.2 * ((equity - 2000) / 1000) * 10
    return min(base, 50.0)  # Cap at $50/day
```

### Scaling Tiers

| Equity Level | Daily Input | Monthly Total | Time Saved |
|-------------|-------------|---------------|------------|
| $0-$2k | $10 | $300 | Baseline |
| $2k-$5k | $12-$14 | $360-$420 | 1 month |
| $5k-$10k | $16-$20 | $480-$600 | 2 months |
| $10k+ | $24-$50 | $720-$1500 | 3+ months |

### Enabling Auto-Scale

```bash
# Via environment variable
export ENABLE_AUTO_SCALE_INPUT=true

# Via CLI flag
python scripts/autonomous_trader.py --auto-scale
```

---

## 5. Theta Harvest Execution (Options Premium)

**Added**: December 2, 2025 (theta-scale branch)

### Overview

Automatic theta (time decay) harvesting through options premium selling when equity gates are met.

### Equity Gates

| Equity | Strategy | Target Premium | Risk Level |
|--------|----------|----------------|------------|
| $5k+ | Poor Man's Covered Calls | $5-7/day | Defined |
| $10k+ | Iron Condors (calm regime) | $10-15/day | Defined |
| $25k+ | Full Options Suite | $20-30/day | Mixed |

### IV Percentile Filter

Only sells premium when IV percentile > 50% (ensures we're selling expensive options).

### Integration

The `ThetaHarvestExecutor` in `options_profit_planner.py` now connects directly to Alpaca execution:

```python
# Automatically executed in orchestrator's Gate 7
from src.analytics.options_profit_planner import ThetaHarvestExecutor

executor = ThetaHarvestExecutor(paper=True)
result = executor.evaluate_theta_opportunity(
    symbol='SPY',
    account_equity=5000,
    regime_label='calm',
)
if result.strategy != 'none':
    executor.execute_theta_order(result, alpaca_client)
```

---

## 6. VIX-Triggered Trade Auditor

**Added**: December 2, 2025 (theta-scale branch)

### Overview

Adaptive audit frequency based on market volatility (VIX) for continuous system improvement.

### Audit Frequency Rules

| VIX Level | Frequency | Rationale |
|-----------|-----------|-----------|
| < 25 | Weekly | Normal conditions, standard review |
| 25-35 | Daily | Elevated vol, catch issues faster |
| > 35 | Twice Daily | Crisis mode, maximize protection |

### Features

- Analyzes closed trades for win rate, profit factor, patterns
- Queries RAG for McMillan theta loss patterns
- Generates actionable recommendations
- Logs to telemetry for continuous improvement

### Usage

```python
from src.agent_framework.auditor import TradeAuditor

auditor = TradeAuditor()
result = auditor.run_audit(force=True)

print(f"Win Rate: {result.win_rate}%")
print(f"Recommendations: {result.recommendations}")
```

---

## 7. Quarterly Profit Sweep (Tax Reserve)

**Added**: December 2, 2025 (theta-scale branch)

### Overview

Automatic quarterly profit sweep to reserve funds for estimated tax payments.

### Configuration

```bash
export TAX_RESERVE_PCT=28.0  # Short-term capital gains rate
export QUARTERLY_SWEEP_ENABLED=true
```

### Quarter-End Dates

- March 31 (Q1)
- June 30 (Q2)
- September 30 (Q3)
- December 31 (Q4)

### Calculation

```python
taxable_profit = end_equity - start_equity - deposits + withdrawals
tax_reserve = taxable_profit * 0.28  # 28% to HYSA
```

### Integration

Runs automatically as Gate 9 in the orchestrator on quarter-end dates:

```python
from src.orchestrator.telemetry import run_quarterly_sweep

result = run_quarterly_sweep(
    start_equity=100000,
    end_equity=105000,
    deposits=900,  # $10/day * 90 days
    force=False,
    dry_run=True,  # Set False for live execution
)
# Result: ~$1,148 to tax reserve (28% of $4,100 profit)
```

---

## Summary

These seven strategies work together to maximize system profitability:

1. **Alpaca High-Yield Cash**: Idle cash earns 3.56% APY passively
2. **OpenRouter Multi-LLM**: Enable AI analysis when profit justifies cost (Month 4+)
3. **Claude Batching**: Maximize development velocity through parallel agent execution
4. **Auto-Input Scaling**: Accelerate compounding as equity grows (+2-3 months saved)
5. **Theta Harvest**: Premium selling when equity gates met (+$5-30/day at scale)
6. **VIX-Triggered Audit**: Adaptive critique frequency for continuous improvement
7. **Quarterly Tax Sweep**: Automated 28% reserve for tax obligations

**Key Principle**: Every optimization should pay for itself. Don't add costs until revenue justifies them.
