# RL Architecture - Simplified (2025-12-04)

## Summary

Cleaned up unused RL scaffolding to reduce tech debt and confusion. The system now has **ONE working RL approach** instead of 6 unused implementations.

## What Was Removed

### 1. DQN Implementation (862KB + code)
- **Files Removed:**
  - `src/ml/dqn_agent.py` (13KB)
  - `src/ml/dqn_networks.py` (7.5KB)
  - `src/ml/multi_step_learning.py`
  - **Models:** `models/ml/*_lstm_ppo.pt` (3.4MB total - 862KB × 4 symbols)

- **Usage:** Behind `USE_DQN=true` env flag (never enabled)
- **Referenced in:** `elite_orchestrator.py`, `executor_agent.py`, training scripts
- **Reason:** Complex, unused, adds tech debt

### 2. PPO Implementation
- **Files Removed:**
  - `src/ml/enhanced_ppo.py` (8.7KB)
  - `src/ml/networks.py` (3.7KB - LSTMPPO class)

- **Usage:** Only in offline training scripts
- **Reason:** Not used in production trading flow

### 3. Ensemble RL
- **Files Removed:**
  - `src/ml/ensemble_rl.py` (9KB)

- **Usage:** Behind `USE_ENSEMBLE_RL=true` env flag (never enabled)
- **Referenced in:** `elite_orchestrator.py`, `trainer.py`
- **Reason:** Scaffolding only, never integrated into production

### 4. Supporting Infrastructure (Unused)
- **Files Removed:**
  - `src/ml/prioritized_replay.py` (5.8KB - for DQN)
  - `src/ml/position_sizing_rl.py` (7.2KB - unused)
  - `src/ml/rl_service_client.py` (13.5KB - cloud RL, not used)

- **Reason:** Dependencies of removed implementations

### 5. Deprecated Training Infrastructure
- **Files Marked DEPRECATED (not removed):**
  - `src/ml/trainer.py` - Now raises NotImplementedError
  - `src/ml/walk_forward_validator.py` - Marked as BROKEN

- **Reason:** Offline training tools for removed LSTM-PPO models
- **Note:** Kept files for reference but made them non-functional

## What Was Kept (Production RL)

### Primary RL System: RLFilter (Gate 2)

**File:** `src/agents/rl_agent.py` (242 lines)

**What it does:**
- Lightweight RL inference layer (heuristic-based Q-approximation)
- Uses learned weights from `models/ml/rl_filter_weights.json`
- Blends heuristic decisions with Transformer predictions
- Primary RL gate in production trading orchestrator

**Key methods:**
- `predict(market_state)` → action/confidence/multiplier
- `update_from_telemetry()` → recompute weights from audit trail

**Used in:** `src/orchestrator/main.py` (TradingOrchestrator, Gate 2)

### Transformer RL Policy

**File:** `src/agents/rl_transformer.py` (250 lines)

**What it does:**
- Encoder-only transformer for time-series price/volume features
- Loads trained weights from `models/ml/rl_transformer_state.pt` (301KB)
- Outputs confidence score + explainability metadata
- Provides regime classification (bull_accel, bear_trend, etc.)

**Architecture:**
- 2 transformer encoder layers, 4 attention heads
- Input: 64-timestep context window × 6 features
- Features: pct_return, rolling_vol, volume_zscore, rsi_norm, price_zscore, drawdown

**Used by:** RLFilter (optional, via `RL_USE_TRANSFORMER=true`)

### Supporting Files

**File:** `src/agents/rl_transformer_features.py` (80 lines)
- Feature engineering for transformer: `build_feature_matrix(df)`

**File:** `src/agents/rl_weight_updater.py` (240 lines)
- Updates RLFilter weights from telemetry using PPO-style training
- Reads audit trail → trains policy → exports weights JSON

### Secondary RL: RLPolicyLearner (Q-learning)

**File:** `src/agents/reinforcement_learning.py` (236 lines)

**What it does:**
- Simple tabular Q-learning for discrete state-action pairs
- State: regime + RSI + MACD + trend (discretized)
- Actions: BUY, SELL, HOLD
- Epsilon-greedy exploration

**Used in:** `src/strategies/core_strategy.py` (legacy, not main orchestrator)

**File:** `src/agents/reinforcement_learning_optimized.py` (enhanced version)
- Experience replay buffer
- Epsilon decay
- Risk-adjusted rewards

## The ONE RL Approach Going Forward

**Production RL Stack:**

```
┌─────────────────────────────────────────────────┐
│ Trading Orchestrator (main.py)                  │
│                                                  │
│  Gate 1: Momentum Agent (math, free)            │
│  Gate 2: RLFilter ──────┐                       │
│  Gate 3: LLM Analyst    │                       │
│  Gate 4: Risk Manager   │                       │
└─────────────────────────┼───────────────────────┘
                          │
              ┌───────────▼──────────────┐
              │ RLFilter (rl_agent.py)   │
              │  - Heuristic weights     │
              │  - Transformer policy    │
              └───────────┬──────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                  │
    ┌────▼─────────┐            ┌─────────▼────────┐
    │ rl_filter_   │            │ TransformerRL    │
    │ weights.json │            │ Policy           │
    │ (heuristic)  │            │ (rl_transformer  │
    └──────────────┘            │  _state.pt)      │
                                └──────────────────┘
```

**Why this approach?**
1. **Simple & Fast:** Heuristic weights + lightweight transformer
2. **Proven:** Already in production (Day 9 of R&D phase)
3. **Explainable:** Attribution scores + regime classification
4. **Updateable:** Weights learned from telemetry via `rl_weight_updater`
5. **Hybrid:** Blends rule-based + learned approaches

## Model Files Status

**Kept (Production):**
- `models/ml/rl_filter_weights.json` (716 bytes) ✅
- `models/ml/rl_transformer_state.pt` (301KB) ✅

**Removed (Unused):**
- `models/ml/SPY_lstm_ppo.pt` (862KB) ❌
- `models/ml/QQQ_lstm_ppo.pt` (862KB) ❌
- `models/ml/VOO_lstm_ppo.pt` (862KB) ❌
- `models/ml/BND_lstm_ppo.pt` (862KB) ❌

**Space saved:** 3.4MB

## Code Changes Summary

**Files Removed:** 10
- 6 RL implementation files
- 4 LSTM-PPO model files

**Files Modified:** 3
- `src/orchestration/elite_orchestrator.py` - Removed DQN/Ensemble RL blocks
- `src/agent_framework/executor_agent.py` - Removed DQN block
- `src/ml/trainer.py` - Marked DEPRECATED

**Files Deprecated:** 2
- `src/ml/trainer.py` - Raises NotImplementedError
- `src/ml/walk_forward_validator.py` - Warning added

**Files Kept (Production):** 6
- `src/agents/rl_agent.py` (RLFilter)
- `src/agents/rl_transformer.py` (TransformerRLPolicy)
- `src/agents/rl_transformer_features.py`
- `src/agents/rl_weight_updater.py`
- `src/agents/reinforcement_learning.py` (RLPolicyLearner)
- `src/agents/reinforcement_learning_optimized.py`

## Verification

```bash
# Core RL files compile successfully
python3 -m py_compile src/agents/rl_agent.py
python3 -m py_compile src/agents/reinforcement_learning.py
python3 -m py_compile src/orchestrator/main.py

# ✅ All pass
```

## Migration Guide

### If you were using DQN:
```python
# OLD (removed)
from src.ml.dqn_agent import DQNAgent
agent = DQNAgent(state_dim=50)

# NEW (use RLFilter instead)
from src.agents.rl_agent import RLFilter
rl_filter = RLFilter()
decision = rl_filter.predict(market_state)
```

### If you were using Ensemble RL:
```python
# OLD (removed)
from src.ml.ensemble_rl import EnsembleRLAgent
agent = EnsembleRLAgent(input_dim=50)

# NEW (use TransformerRLPolicy)
from src.agents.rl_transformer import TransformerRLPolicy
policy = TransformerRLPolicy()
decision = policy.predict(symbol, market_state)
```

### If you were using LSTM-PPO:
```python
# OLD (removed)
from src.ml.networks import LSTMPPO
model = LSTMPPO(input_dim=50)

# NEW (use RLFilter for production)
from src.agents.rl_agent import RLFilter
rl_filter = RLFilter()
# Already uses transformer under the hood
```

## Environment Variables

**Removed (no longer used):**
- `USE_DQN` - DQN agent removed
- `USE_ENSEMBLE_RL` - Ensemble RL removed
- `EXECUTOR_USE_DQN` - Executor DQN removed

**Active (production):**
- `RL_USE_TRANSFORMER` - Enable/disable transformer in RLFilter (default: true)
- `RL_CONFIDENCE_THRESHOLD` - RLFilter confidence threshold (default: 0.6)
- `RL_TRANSFORMER_WINDOW` - Context window size (default: 64)
- `RL_TRANSFORMER_THRESHOLD` - Transformer confidence threshold (default: 0.55)

## Benefits of Cleanup

1. **Reduced Tech Debt:** 10 fewer files to maintain
2. **Clear Architecture:** ONE RL approach, not 6 competing ones
3. **Smaller Codebase:** 3.4MB models + ~60KB code removed
4. **Less Confusion:** No more "which RL should I use?"
5. **Focused Development:** Improve RLFilter instead of maintaining multiple implementations

## Next Steps

1. **Enhance RLFilter:** Improve transformer training with more data
2. **Better Feature Engineering:** Add more signals to rl_transformer_features.py
3. **Telemetry-Driven Learning:** Use rl_weight_updater more aggressively
4. **Regime Adaptation:** Make RLFilter more adaptive to market regimes

## References

- **Main Orchestrator:** `src/orchestrator/main.py` (Gate 2 = RLFilter)
- **RLFilter Implementation:** `src/agents/rl_agent.py`
- **Transformer Policy:** `src/agents/rl_transformer.py`
- **Weight Updates:** `src/agents/rl_weight_updater.py`
- **Legacy Q-learning:** `src/agents/reinforcement_learning.py`

---

**Cleanup Date:** 2025-12-04
**Status:** ✅ Complete
**Production Status:** Gate 2 (RLFilter) running in Day 9 of R&D phase
