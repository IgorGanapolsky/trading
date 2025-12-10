# DiscoRL Integration Analysis for Trading System

**Date**: December 8, 2025
**Author**: Claude (CTO)
**Status**: R&D Phase - Day 9/90

## Executive Summary

Google DeepMind's DiscoRL paper (Nature 2025) demonstrates that RL update rules can be **automatically discovered** via meta-learning, outperforming hand-designed algorithms like PPO, A2C, and DQN. This analysis evaluates its applicability to our trading system.

**Verdict**: High potential, but requires adaptation work. Worth integrating as Month 2 enhancement.

---

## 1. What is DiscoRL?

### Core Innovation
Instead of manually designing loss functions with equations, DiscoRL uses a **meta-network (LSTM)** to learn the optimal update rule from experience.

```
Traditional RL:    loss = f(advantage, policy, value)  <- Human-designed equation
DiscoRL:           loss = MetaNet(observations, rewards, actions, ...)  <- Learned neural network
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Disco103** | Pre-trained meta-network weights (600 prediction dimensions, 256 hidden) |
| **Meta-LSTM** | Processes trajectories and learns update rules over agent lifetime |
| **Value Network** | Categorical Q-value distribution (601 bins, max 300) |
| **Input Transforms** | 17+ transformations (softmax, sign_log, TD-pairs, etc.) |

### Architecture (from `disco_rl/update_rules/disco.py`)

```python
class DiscoUpdateRule:
    prediction_size = 600      # Auxiliary prediction dimensions
    hidden_size = 256          # Meta-network hidden size
    num_bins = 601             # Categorical value distribution
    max_abs_value = 300.0      # Max representable value
    moving_average_decay = 0.99
```

---

## 2. Our Current RL Architecture

### Existing Components

| Component | Location | Framework |
|-----------|----------|-----------|
| **DQN Agent** | `src/ml/dqn_agent.py` | PyTorch |
| **RL Filter** | `src/agents/rl_agent.py` | NumPy/Heuristics |
| **Transformer Policy** | `src/agents/rl_transformer.py` | PyTorch |
| **Dueling/Double DQN** | `src/ml/dqn_networks.py` | PyTorch |
| **Prioritized Replay** | `src/ml/prioritized_replay.py` | NumPy |

### Key Differences

| Aspect | Our System | DiscoRL |
|--------|-----------|---------|
| **Framework** | PyTorch | JAX + Haiku |
| **Action Space** | Discrete (3: BUY/SELL/HOLD) | Discrete (game actions) |
| **State Space** | 5-10 features | Image pixels (Atari) |
| **Update Rule** | Fixed (DQN/PPO) | Meta-learned |
| **Training** | Online + Replay | Rollout-based |

---

## 3. Compatibility Assessment

### What Works Well

1. **Discrete Actions**: Both use discrete action spaces
2. **Value-based**: Both compute Q-values / advantages
3. **LSTM Support**: Our system has LSTM DQN, DiscoRL uses meta-LSTM
4. **Categorical Values**: DiscoRL uses distributional RL (we could adopt)

### Challenges

1. **Framework Mismatch**: JAX vs PyTorch (need conversion or bridge)
2. **Environment Design**: DiscoRL expects game-like episodes, trading is continuous
3. **State Representation**:
   - DiscoRL: Image observations → Conv layers
   - Trading: Feature vectors (RSI, MACD, etc.)
4. **Episode Structure**:
   - DiscoRL: Clear episode boundaries (game over)
   - Trading: Artificial episode splits (daily/weekly)

### Critical Question: Does Disco103 Transfer?

**Uncertain**. The meta-network was trained on Atari-like environments. Financial markets have:
- Different reward distributions (sparse, high variance)
- Non-stationary dynamics (regime changes)
- Partial observability (hidden information)
- Transaction costs and slippage

**Recommendation**: Test Disco103 first, then consider meta-training from scratch on trading environments.

---

## 4. Integration Options

### Option A: Direct Disco103 Port (Low Effort, High Risk)
- Port JAX weights to PyTorch
- Use as drop-in replacement for DQN update rule
- **Risk**: May not transfer to financial domain

### Option B: Meta-Train Trading-Specific Rule (High Effort, High Potential)
- Create trading environment in DiscoRL's format
- Meta-train from scratch on trading episodes
- **Timeline**: 2-4 weeks of compute

### Option C: Hybrid Approach (Medium Effort, Medium Risk)
- Keep our DQN architecture
- Adopt specific DiscoRL innovations:
  - Categorical value distribution
  - Input transformations
  - Moving average normalization
  - Auxiliary prediction tasks

**Recommended: Option C** (Start here, evaluate before deeper integration)

---

## 5. Concrete Integration Steps

### Phase 1: Adopt DiscoRL Innovations (Week 1)

```python
# Add to src/ml/dqn_agent.py

class DiscoInspiredDQN(DQNAgent):
    def __init__(self, ...):
        # Categorical value distribution (like DiscoRL)
        self.num_bins = 601
        self.max_abs_value = 300.0

        # Moving average normalization for advantages
        self.adv_ema = MovingAverage(decay=0.99)

        # Auxiliary prediction tasks
        self.aux_predictor = AuxPredictionHead(...)
```

### Phase 2: Create Trading Environment Wrapper (Week 2)

```python
# Create src/environments/disco_trading_env.py

class DiscoTradingEnv:
    """DiscoRL-compatible trading environment"""

    def step(self, action) -> types.EnvironmentTimestep:
        # Execute trade
        # Return observation, reward, discount, step_type
        pass
```

### Phase 3: Test Disco103 Transfer (Week 3)

```python
# Test if pre-trained weights work for trading
from disco_rl.agent import Agent, get_settings_disco

agent = Agent(
    single_observation_spec=trading_obs_spec,
    single_action_spec=trading_action_spec,
    agent_settings=get_settings_disco(),
    batch_axis_name=None,
)
```

### Phase 4: Evaluate & Decide (Week 4)

- Compare Disco103 vs our DQN on backtests
- If promising: Consider meta-training on trading data
- If not: Keep Option C innovations, skip meta-training

---

## 6. Code Locations

### DiscoRL Repository (cloned)
```
research/disco_rl/
├── disco_rl/
│   ├── agent.py              # Main agent implementation
│   ├── update_rules/
│   │   ├── disco.py          # DiscoUpdateRule (key file)
│   │   ├── actor_critic.py   # Baseline AC
│   │   └── policy_gradient.py
│   ├── networks/
│   │   ├── meta_nets.py      # Meta-LSTM architecture
│   │   └── nets.py           # Agent networks
│   └── value_fns/
│       └── value_utils.py    # Value function utilities
└── colabs/
    ├── eval.ipynb            # Use Disco103 weights
    └── meta_train.ipynb      # Train new update rules
```

### Our RL System
```
src/
├── agents/
│   ├── rl_agent.py           # RLFilter (Gate 2)
│   └── rl_transformer.py     # Transformer policy
├── ml/
│   ├── dqn_agent.py          # DQN implementation
│   └── dqn_networks.py       # Network architectures
└── environments/             # To be created
    └── disco_trading_env.py  # DiscoRL wrapper
```

---

## 7. Dependencies

### DiscoRL Requirements
```
jax[cuda12]
haiku
distrax
rlax
optax
chex
ml_collections
```

### Integration Requirements
```bash
# Install DiscoRL
pip install git+https://github.com/google-deepmind/disco_rl.git

# JAX-PyTorch bridge (if needed)
pip install jax2torch  # or manual conversion
```

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Disco103 doesn't transfer | High | Medium | Test quickly, fallback to Option C |
| JAX/PyTorch incompatibility | Medium | Low | Use pure JAX for DiscoRL, keep PyTorch for DQN |
| Compute requirements too high | Low | Medium | Use Colab GPUs for meta-training |
| Integration delays R&D goals | Medium | Medium | Timebox to 1 week experimentation |

---

## 9. Decision Matrix

| Criteria | Weight | Disco103 | Our DQN | DiscoRL Meta-Train |
|----------|--------|----------|---------|-------------------|
| Implementation Effort | 30% | 2/5 | 5/5 | 1/5 |
| Potential Performance | 40% | 3/5 (uncertain) | 3/5 | 5/5 |
| Risk | 20% | 3/5 | 4/5 | 2/5 |
| Time to Value | 10% | 4/5 | 5/5 | 2/5 |
| **Weighted Score** | | **2.8** | **4.1** | **3.0** |

**Conclusion**: Start with our existing DQN + Option C innovations. Evaluate Disco103 transfer. Only pursue full meta-training if transfer shows promise.

---

## 10. Next Steps

1. **Immediate**: Add categorical value distribution to DQN (low effort, proven benefit)
2. **Week 1**: Implement moving average normalization for advantages
3. **Week 2**: Create DiscoRL-compatible trading environment wrapper
4. **Week 3**: Test Disco103 weights on trading backtests
5. **Month 2**: Decide on full meta-training based on results

---

## References

- [Nature Paper](https://www.nature.com/articles/s41586-025-09761-x)
- [GitHub Repository](https://github.com/google-deepmind/disco_rl)
- [DeepMind Project Page](https://google-deepmind.github.io/disco_rl/)

---

**Last Updated**: December 8, 2025
