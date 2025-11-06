# RL Trading System: Quick Start Guide
**90-Day Implementation Roadmap**

---

## TL;DR - Start Here

**Best Algorithm:** PPO (Proximal Policy Optimization)
- Most stable, easiest to tune
- Expected Sharpe: 1.0-2.0 after 90 days

**Best Framework:** Stable-Baselines3 + Custom Environment
- Full control, easy integration with existing Alpaca code
- Setup time: 1 week

**Critical Success Factor:** Reward function design
- Use multi-objective: returns - costs - drawdown penalty
- NOT simple profit (causes overfitting)

**Timeline to First Results:** 2-3 weeks
- Week 1: Build environment
- Week 2: Train baseline agent
- Week 3: First backtest results

---

## Week-by-Week Action Plan

### Week 1: Setup (Days 1-7)

**Monday-Tuesday:**
```bash
# Install dependencies
pip install stable-baselines3 gym pandas numpy ta yfinance

# Create directory structure
mkdir -p src/rl/{envs,agents,utils}
mkdir -p data/rl/{train,test}
mkdir -p models/rl
```

**Wednesday-Friday:**
- Build TradingEnv (custom gym environment)
- State: OHLCV + 10 technical indicators + portfolio state
- Action: Position size [-1, 1]
- Reward: Sharpe ratio (simple, start here)

**Code Template:** See Section 7.1 in full report

**Weekend:**
- Test environment with manual trades
- Fix bugs

### Week 2: Data & Training (Days 8-14)

**Monday-Wednesday:**
- Download 3 years SPY data (2021-2024)
- Add technical indicators: SMA, EMA, RSI, MACD, ATR, Bollinger
- Normalize features
- Train/test split

**Thursday-Friday:**
- Train PPO agent (500k steps, ~4-8 hours)
- Monitor with TensorBoard

**Code:**
```python
from stable_baselines3 import PPO

model = PPO('MlpPolicy', env, learning_rate=3e-4, verbose=1)
model.learn(total_timesteps=500_000)
model.save('ppo_baseline')
```

### Week 3: Backtest & Evaluate (Days 15-21)

**Monday-Wednesday:**
- Backtest on 2024 test data
- Calculate metrics: Sharpe, max drawdown, win rate

**Thursday-Friday:**
- Compare to buy-and-hold baseline
- Document results

**Expected Results:**
- Sharpe: 0.5-1.0 (baseline)
- Win rate: 50-55%
- If negative Sharpe: debug reward function

### Week 4+: Iterate & Improve

**If Sharpe > 0.5:** Continue to Month 2 enhancements
**If Sharpe < 0.5:** Debug (likely reward function issue)

---

## Critical Configuration Settings

### PPO Hyperparameters (Copy-Paste Ready)

```python
from stable_baselines3 import PPO

model = PPO(
    'MlpPolicy',
    env,
    learning_rate=3e-4,      # CRITICAL: Test 1e-4, 3e-4, 1e-3
    n_steps=2048,             # Steps per update
    batch_size=64,            # Mini-batch size
    n_epochs=10,              # Epochs per update
    gamma=0.99,               # Discount factor
    gae_lambda=0.95,          # GAE parameter
    clip_range=0.2,           # PPO clip range
    verbose=1,
    tensorboard_log='./tensorboard/'
)
```

### State Features (Minimum Viable)

```python
state_features = [
    # Price (5)
    'close', 'returns', 'log_returns', 'volume', 'volume_ratio',

    # Technical (10)
    'SMA_20', 'EMA_12', 'RSI_14', 'MACD', 'MACD_signal',
    'ATR_14', 'Bollinger_upper', 'Bollinger_lower', 'BB_width',
    'OBV',

    # Portfolio (3)
    'cash_balance', 'position_size', 'unrealized_pnl',
]
# Total: 18 features
```

### Reward Function (Month 1)

```python
def calculate_reward(self):
    """Simple Sharpe ratio for baseline"""
    if self.current_step < 20:
        return 0.0

    returns = self.get_returns(window=20)
    sharpe = returns.mean() / (returns.std() + 1e-6)
    return sharpe
```

### Reward Function (Month 2+)

```python
def calculate_reward(self):
    """Multi-objective reward (production)"""
    returns = self.get_returns(window=1)
    costs = self.get_transaction_costs()
    drawdown = self.get_current_drawdown()

    reward = (
        1.0 * returns.sum() -           # Return component
        0.5 * costs.sum() -              # Cost penalty
        2.0 * (np.exp(drawdown) - 1)    # Drawdown penalty (exponential)
    )
    return reward
```

---

## Common Issues & Fixes

### Issue 1: Agent Won't Trade (Always Holds)

**Symptom:** Agent learns to do nothing (0 trades in backtest)

**Cause:** Reward function penalizes trading too much

**Fix:**
```python
# Add exploration bonus
reward = base_reward + 0.1 * (num_trades > 0)

# Or reduce transaction cost penalty
cost_penalty = 0.1 * costs  # Was 0.5
```

### Issue 2: Agent Over-Trades (100+ trades/day)

**Symptom:** Excessive trading, high costs

**Fix:**
```python
# Add trading penalty
trading_penalty = 0.01 * num_trades
reward = returns - trading_penalty
```

### Issue 3: Training Unstable (Reward Spikes)

**Symptom:** Reward goes to inf or NaN

**Fix:**
```python
# Clip reward
reward = np.clip(reward, -10, 10)

# Or normalize reward
reward = (reward - reward_mean) / (reward_std + 1e-6)
```

### Issue 4: Overfitting (Great on train, poor on test)

**Symptom:** Train Sharpe 2.0, test Sharpe 0.2

**Fix:**
- Use walk-forward validation
- Add dropout to network
- Simplify reward function
- Train on more diverse data (2020 crash + 2021 bull + 2022 bear)

---

## Monitoring During Training

**TensorBoard Command:**
```bash
tensorboard --logdir ./tensorboard/
# Open http://localhost:6006
```

**What to Watch:**
- **Reward:** Should increase steadily (if flat or decreasing, stop)
- **Policy Loss:** Should decrease
- **Win Rate:** Should be >45% (if <40%, agent is broken)

**Stop Training If:**
- Reward = NaN or inf
- Win rate < 30% after 100k steps
- Max drawdown > 50%

---

## Month 2 Enhancements (Days 31-60)

**Add These ONLY After Month 1 Baseline Works:**

1. **Multi-Objective Reward** (Week 5)
   - Returns - costs - drawdown penalty
   - Expected improvement: +20-30% Sharpe

2. **Market Regime Detection** (Week 6)
   - HMM with 3 states (bear, neutral, bull)
   - Add regime as state feature
   - Expected improvement: +10-15% Sharpe

3. **Second Agent (Ensemble)** (Week 7)
   - Train SAC for mean-reversion
   - Ensemble with PPO
   - Expected improvement: +15-20% Sharpe

4. **Hyperparameter Optimization** (Week 8)
   - Use Optuna to tune learning rate, batch size, etc.
   - Expected improvement: +5-10% Sharpe

---

## Month 3 Enhancements (Days 61-90)

**Production-Ready Features:**

1. **Online Learning** (Week 9)
   - Pre-train on 3 years historical
   - Fine-tune on recent 30 days
   - Update daily with new data

2. **Sentiment Integration** (Week 10)
   - Alpha Vantage news API
   - Add sentiment score to state
   - Expected improvement: +5-10% Sharpe

3. **Robustness Testing** (Week 11)
   - Walk-forward validation
   - Stress test on 2020 crash, 2022 bear
   - Monte Carlo (1000 random periods)

4. **Go-Live Decision** (Week 12)
   - Final metrics calculation
   - Risk assessment
   - Deploy if Sharpe > 1.5, win rate > 60%, max DD < 10%

---

## Go-Live Criteria (Day 90)

```python
go_live_checklist = {
    'sharpe_ratio': '>1.5',
    'win_rate': '>60%',
    'max_drawdown': '<10%',
    'profitable_30_days': 'Yes',
    'no_critical_bugs': 'Yes',
    'circuit_breakers_tested': 'Yes',
}

if all(criteria_met):
    print("APPROVED: Start $1/day Fibonacci live trading")
else:
    print("EXTEND R&D: Need 30 more days")
```

---

## Resources

**Code Examples:**
- Full report: `/home/user/trading/docs/RL_State_of_Art_2025_Technical_Report.md`
- Section 7: Complete implementation with code

**Best Open-Source Frameworks:**
1. **Stable-Baselines3:** https://github.com/DLR-RM/stable-baselines3 (easiest)
2. **FinRL:** https://github.com/AI4Finance-Foundation/FinRL (finance-specific)
3. **TradeMaster:** https://github.com/TradeMaster-NTU/TradeMaster (cutting-edge)

**Must-Read Papers:**
1. "Reinforcement Learning for Quantitative Trading" (ACM TIST 2023)
2. "FinRL Contests 2025" (ArXiv 2504.02281v3)

**Communities:**
- r/algotrading (Reddit)
- FinRL Discord (via GitHub)

---

## Expected Timeline & Results

| Phase | Duration | Sharpe Target | Max DD | Win Rate | Status |
|-------|----------|---------------|--------|----------|--------|
| Week 1 | 7 days | N/A | N/A | N/A | Setup |
| Week 2-3 | 14 days | 0.5-1.0 | <15% | 50-55% | Baseline |
| Week 4-8 | 35 days | 1.0-1.5 | <10% | 55-60% | Enhanced |
| Week 9-12 | 28 days | 1.5-2.0 | <8% | 60-65% | Production |

**Probability of Success:**
- 90% chance: Sharpe > 0 (break-even)
- 70% chance: Sharpe > 1.0 (profitable)
- 50% chance: Sharpe > 1.5 (go-live ready)
- 25% chance: Sharpe > 2.0 (exceptional)

---

## Final Checklist

**Before Starting (Day 0):**
- [ ] Read this guide completely
- [ ] Read Section 7 of full report (implementation roadmap)
- [ ] Install dependencies
- [ ] Download historical data (SPY 2021-2024)

**Week 1 Complete:**
- [ ] TradingEnv built and tested
- [ ] Can execute manual trades
- [ ] No errors in environment

**Week 3 Complete:**
- [ ] PPO agent trained (500k steps)
- [ ] Backtest on 2024 data
- [ ] Sharpe ratio calculated
- [ ] Results documented

**Day 30 Go/No-Go:**
- [ ] Sharpe > 0.5 → Continue to Month 2
- [ ] Sharpe 0-0.5 → Debug reward function
- [ ] Sharpe < 0 → Revisit fundamentals

**Day 90 Go-Live:**
- [ ] Sharpe > 1.5
- [ ] Win rate > 60%
- [ ] Max drawdown < 10%
- [ ] Profitable for 30 consecutive days
- [ ] Circuit breakers tested
- [ ] Deploy to live $1/day Fibonacci

---

**Next Step:** Start Week 1 setup (install dependencies, build TradingEnv)

**Questions?** Refer to full technical report for detailed explanations.

**Good luck! 🚀**
