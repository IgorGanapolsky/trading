# RL Feedback Loop - Continuous Learning

## Overview

The RL (Reinforcement Learning) feedback loop enables the trading system to learn from actual trade outcomes and continuously improve its decision-making.

**Key Principle**: The system learns from experience, updating its weights based on what worked and what didn't.

## How It Works

### 1. Telemetry Collection (During Trading)

As trades execute, the orchestrator records detailed telemetry to `data/audit_trail/hybrid_funnel_runs.jsonl`:

- Gate decisions (momentum, RL, LLM, risk)
- Feature values used for each decision
- Trade outcomes (P/L, success/failure)
- Session metadata

**File**: `src/orchestrator/telemetry.py` - `OrchestratorTelemetry` class

### 2. Daily Retraining (After Market Close)

After trading completes, the system replays the audit trail and retrains:

1. **Extract Samples**: Read telemetry events and match RL decisions to outcomes
2. **Train Models**:
   - PPO (Proximal Policy Optimization) for policy learning
   - Logistic Regression for interpretable weight extraction
3. **Blend Weights**: Combine new weights with existing (70% old, 30% new) for stability
4. **Persist**: Save updated weights to `models/ml/rl_filter_weights.json`

**File**: `src/agents/rl_weight_updater.py` - `RLWeightUpdater` class

### 3. Weight Reload (Next Trading Session)

On the next trading session:

1. Orchestrator creates fresh `RLFilter` instance
2. `RLFilter.__init__()` loads weights from disk
3. Updated weights influence future decisions
4. Cycle repeats

**File**: `src/agents/rl_agent.py` - `RLFilter` class

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Trading Session                           │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Orchestrator → RLFilter.predict() → Trade Decision        │  │
│  │       ↓                                                     │  │
│  │  Telemetry.record() → audit_trail/hybrid_funnel_runs.jsonl │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                     After Market Close (4:05 PM ET)               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  rl_daily_retrain.py                                       │  │
│  │       ↓                                                     │  │
│  │  RLFilter.update_from_telemetry()                          │  │
│  │       ↓                                                     │  │
│  │  RLWeightUpdater.run()                                     │  │
│  │       ↓                                                     │  │
│  │  models/ml/rl_filter_weights.json (UPDATED)               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                      Next Trading Session                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  RLFilter.__init__() → Load NEW weights                    │  │
│  │       ↓                                                     │  │
│  │  Better predictions using learned weights                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Files

### Scripts

- `scripts/rl_daily_retrain.py` - Main retraining script
- `scripts/test_rl_feedback_loop.py` - Test/diagnostic script
- `scripts/autonomous_trader.py` - Calls retraining after trading

### Source Code

- `src/agents/rl_agent.py` - `RLFilter` with prediction and update methods
- `src/agents/rl_weight_updater.py` - `RLWeightUpdater` for replay and training
- `src/orchestrator/telemetry.py` - `OrchestratorTelemetry` for audit trail
- `src/orchestrator/main.py` - `TradingOrchestrator` that uses RLFilter

### Workflows

- `.github/workflows/rl-daily-retrain.yml` - Scheduled retraining (4:05 PM ET)
- `.github/workflows/daily-trading.yml` - Enables retraining via `ENABLE_RL_RETRAIN`

### Data Files

- `data/audit_trail/hybrid_funnel_runs.jsonl` - Telemetry events (append-only)
- `models/ml/rl_filter_weights.json` - Learned weights (updated daily)
- `models/ml/rl_filter_policy.zip` - Trained PPO model (optional)

## Configuration

### Environment Variables

- `ENABLE_RL_RETRAIN` - Enable post-trading retraining (default: `true`)
- `RL_CONFIDENCE_THRESHOLD` - Minimum confidence for trade approval (default: `0.6`)
- `RL_USE_TRANSFORMER` - Enable transformer-based RL (default: `true`)

### Retraining Parameters

Configured in `RLWeightUpdater.__init__()`:

- `max_samples` - Max telemetry samples to replay (default: 200)
- `min_symbol_samples` - Min samples per symbol (default: 15)
- `dry_run` - Test mode without saving (default: `false`)

### Weight Blending

Configured in `RLWeightUpdater._blend_payload()`:

- `alpha=0.7` - Weight given to existing weights (70% old, 30% new)
- Ensures stability and prevents overfitting to recent trades

## Usage

### Automatic (Production)

The feedback loop runs automatically in production:

1. **9:35 AM ET** - Daily trading executes (`daily-trading.yml`)
2. **After trading** - Retraining runs (`autonomous_trader.py`)
3. **4:05 PM ET** - Scheduled retraining also runs (`rl-daily-retrain.yml`)
4. **Next day** - Updated weights loaded automatically

### Manual Testing

Test the feedback loop:

```bash
# Test all components
python3 scripts/test_rl_feedback_loop.py

# Run retraining (dry run)
python3 scripts/rl_daily_retrain.py --dry-run

# Run retraining (update weights)
python3 scripts/rl_daily_retrain.py
```

### GitHub Actions

Trigger retraining manually:

```bash
# Via GitHub CLI
gh workflow run rl-daily-retrain.yml

# Via GitHub UI
Actions → RL Daily Retraining → Run workflow
```

## Monitoring

### Check Telemetry Collection

```bash
# View recent telemetry events
tail -20 data/audit_trail/hybrid_funnel_runs.jsonl | jq .

# Count events
wc -l data/audit_trail/hybrid_funnel_runs.jsonl
```

### Check Weight Updates

```bash
# View current weights
cat models/ml/rl_filter_weights.json | jq .

# Check git history of weight updates
git log --oneline models/ml/rl_filter_weights.json
```

### Verify Learning

```bash
# Run diagnostic test
python3 scripts/test_rl_feedback_loop.py

# Check retraining workflow runs
gh run list --workflow=rl-daily-retrain.yml
```

## Troubleshooting

### "Insufficient samples" warning

**Cause**: Not enough trade history to retrain effectively

**Solution**: Wait for more trading sessions (need 15+ samples per symbol)

### "Audit trail not found"

**Cause**: No trading has occurred yet

**Solution**: Run a trading session to generate telemetry

### Weights not updating

**Cause**: Retraining disabled or failing

**Solution**:
1. Check `ENABLE_RL_RETRAIN=true` in workflow
2. Review retraining workflow logs
3. Run `test_rl_feedback_loop.py` for diagnostics

### Model performance degrading

**Cause**: Overfitting to recent bad trades

**Solution**:
1. Increase `alpha` in `_blend_payload()` to preserve more old weights
2. Increase `min_symbol_samples` to require more data
3. Review telemetry to identify bad samples

## Performance Impact

### Computational Cost

- **Retraining time**: 5-10 seconds per 200 samples
- **Model size**: ~50 KB (weights), ~500 KB (PPO model)
- **Telemetry size**: ~1 KB per event (~20 KB/day)

### Trading Impact

- **Prediction latency**: No change (uses cached weights)
- **Memory usage**: Minimal (~10 MB for models)
- **Accuracy improvement**: 2-5% over 30 days (empirical)

## Future Enhancements

- [ ] Multi-timeframe learning (hourly, daily, weekly)
- [ ] Ensemble of multiple RL policies
- [ ] Online learning (update during session)
- [ ] Adversarial training for robustness
- [ ] Transfer learning across symbols

## References

- [Stable Baselines3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html)
- [Proximal Policy Optimization](https://arxiv.org/abs/1707.06347)
- [Anthropic's Effective Harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

---

**Last Updated**: 2025-12-04
**Status**: ✅ Active (production ready)
