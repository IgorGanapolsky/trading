# AI Agent Adaptation Implementation Plan

## Overview

Based on the Stanford/Princeton/Harvard research taxonomy, almost all advanced AI agent systems use 4 basic adaptation modes. This document maps these modes to our trading system and provides concrete implementation steps.

**Taxonomy Source**: Multi-university research paper proposing first full taxonomy for agentic AI adaptation.

**Key Insight**: Adaptation means changing either the agent OR its tools using feedback signals.

---

## The 4 Adaptation Modes

| Mode | What Adapts | Feedback Source | Example |
|------|-------------|-----------------|---------|
| **A1** | Agent | Tool results | Trade P/L, order fills |
| **A2** | Agent | Output evaluations | Win rate, Sharpe ratio, human ratings |
| **T1** | Tools (agent frozen) | Separate training | Sentiment analyzer trained independently |
| **T2** | Tools (agent fixed) | Agent feedback | Risk calculator tuned from agent decisions |

---

## Current State Assessment

### What We Have (Day 9/90)

```
Architecture:
├── Gate 1: Momentum Agent (static)
├── Gate 2: RL Filter (A1 partially implemented)
│   ├── Heuristics (40%) - logistic regression
│   ├── Transformer (45%) - temporal patterns
│   └── DiscoRL DQN (15%) - categorical distribution
├── Gate 3: LLM Sentiment (static)
├── Gate 4: Risk Manager (static)
└── Telemetry → PPO Retraining (daily)
```

### Existing Feedback Loops

| Loop | Status | File |
|------|--------|------|
| Telemetry collection | ✅ Active | `src/orchestrator/telemetry.py` |
| PPO retraining | ✅ Active | `src/agents/rl_weight_updater.py` |
| Weight blending | ✅ Active | 70% old / 30% new |
| DiscoRL online learning | ⚠️ Initialized, not called | `src/ml/disco_dqn_agent.py` |

### Gap Analysis

| Mode | Current | Gap | Opportunity |
|------|---------|-----|-------------|
| A1 | Partial | Binary reward (+1/-1) | Rich reward signals |
| A2 | None | No systematic evaluation | Win rate, Sharpe tracking |
| T1 | None | All tools static | Train sentiment separately |
| T2 | None | Fixed thresholds | Adaptive position sizing |

---

## Implementation Plan

### Phase 1: Enhance A1 (Week 1-2)
**Agent learns from tool results**

#### 1.1 Rich Reward Signals
**Current**: Binary +1 (profit) / -1 (loss)
**Target**: Multi-dimensional reward

```python
# src/ml/reward_functions.py - Already exists but underutilized
reward = RiskAdjustedReward(
    return_weight=0.35,      # Annualized return
    downside_weight=0.25,    # Downside risk penalty
    sharpe_weight=0.20,      # Sharpe ratio
    drawdown_weight=0.15,    # Max drawdown penalty
    transaction_weight=0.05  # Transaction cost
)
```

**Action**: Integrate `RiskAdjustedReward` into `RLWeightUpdater.run()`

#### 1.2 Enable Online Learning
**Current**: DiscoRL DQN initialized but never trained
**Target**: Live learning from trade outcomes

```python
# In TradingOrchestrator._process_exit()
if hasattr(self.rl_filter, 'record_trade_outcome'):
    self.rl_filter.record_trade_outcome(
        entry_state=position.entry_features,
        action=1,  # long
        exit_state=current_features,
        reward=pnl_pct,
        done=True
    )
```

**Action**: Enable `record_trade_outcome()` call in orchestrator exit flow

#### 1.3 Execution Quality Feedback
**Current**: Only P/L tracked
**Target**: Track fill quality, slippage

```python
execution_feedback = {
    'requested_price': order.limit_price,
    'fill_price': fill.avg_entry_price,
    'slippage_bps': (fill.avg_entry_price - order.limit_price) / order.limit_price * 10000,
    'fill_rate': fill.filled_qty / order.qty,
    'latency_ms': fill.filled_at - order.submitted_at
}
```

**Action**: Add execution metrics to telemetry

---

### Phase 2: Implement A2 (Week 2-3)
**Agent learns from output evaluations**

#### 2.1 Systematic Performance Evaluation
**Current**: Manual review of win rate
**Target**: Automated evaluation pipeline

```python
# src/evaluation/agent_evaluator.py (new)
class AgentEvaluator:
    def evaluate_session(self, session_data: dict) -> EvaluationResult:
        return EvaluationResult(
            win_rate=self._calc_win_rate(session_data),
            sharpe_ratio=self._calc_sharpe(session_data),
            max_drawdown=self._calc_drawdown(session_data),
            profit_factor=self._calc_profit_factor(session_data),
            expectancy=self._calc_expectancy(session_data)
        )

    def generate_feedback(self, result: EvaluationResult) -> AgentFeedback:
        # Convert metrics to actionable feedback
        if result.win_rate < 0.5:
            return AgentFeedback(
                signal='tighten_entry',
                confidence_adjustment=-0.05
            )
```

#### 2.2 Prediction vs Reality Tracking
**Current**: Not tracked
**Target**: Measure prediction accuracy

```python
# Track: What did agent predict vs what happened?
prediction_accuracy = {
    'predicted_direction': 'long',
    'predicted_confidence': 0.72,
    'actual_return': -0.8,  # Negative = wrong direction
    'accuracy_score': 0 if actual_return < 0 else 1
}
```

**Action**: Add prediction tracking to telemetry

#### 2.3 Confidence Calibration
**Current**: Fixed threshold 0.6
**Target**: Adaptive threshold based on actual accuracy

```python
# If high confidence predictions are often wrong, lower threshold
# If low confidence predictions often win, raise threshold
def calibrate_threshold(historical_data):
    # Group by confidence bucket
    for bucket in [0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8+]:
        win_rate = calc_win_rate(bucket)
        # Adjust threshold toward buckets with highest win rate
```

---

### Phase 3: Implement T1 (Week 3-4)
**Tools trained separately, agent frozen**

#### 3.1 Sentiment Analyzer Fine-tuning
**Current**: Static sentiment scoring
**Target**: Domain-specific sentiment model

```python
# Train sentiment model on trading-relevant data
# Agent stays frozen, just uses improved sentiment scores
sentiment_trainer = SentimentFineTuner(
    base_model='finbert',
    training_data='data/labeled_sentiment.jsonl',
    output_path='models/ml/trading_sentiment.pt'
)
sentiment_trainer.train()  # Runs independently of agent
```

#### 3.2 Technical Indicator Learning
**Current**: Static MACD/RSI calculations
**Target**: Learned indicator weights per market regime

```python
# Learn optimal indicator combinations per regime
class IndicatorLearner:
    def fit(self, historical_data, regime_labels):
        # Random forest or XGBoost to learn:
        # Which indicators matter most in bull/bear/sideways?
        pass
```

#### 3.3 Domain Model Training
**Current**: No domain-specific models
**Target**: Symbol-specific pattern recognition

```python
# Train separate models for different asset classes
# ETF patterns differ from individual stocks
domain_models = {
    'etf': ETFPatternModel('SPY', 'QQQ', 'VOO'),
    'growth': GrowthStockModel('NVDA', 'GOOGL'),
    'safe': SafeHavenModel('GLD', 'TLT')
}
```

---

### Phase 4: Implement T2 (Week 4-5)
**Agent fixed, tools tuned from agent feedback**

#### 4.1 Adaptive Position Sizing
**Current**: Fixed position size based on volatility
**Target**: Position size learns from agent confidence accuracy

```python
# If agent's high-confidence trades have higher win rate,
# increase position size for high-confidence trades
class AdaptivePositionSizer:
    def __init__(self):
        self.confidence_multipliers = {}

    def update_from_outcomes(self, outcomes: list):
        # Group outcomes by confidence bucket
        for bucket, trades in grouped_outcomes.items():
            win_rate = sum(1 for t in trades if t.pnl > 0) / len(trades)
            # Higher win rate = higher multiplier
            self.confidence_multipliers[bucket] = win_rate / 0.5
```

#### 4.2 Dynamic Risk Thresholds
**Current**: Fixed stop-loss (3%), take-profit (3%)
**Target**: Thresholds adapt to volatility prediction accuracy

```python
# If ATR-based stops work well, weight them more
# If fixed stops work better, weight them more
class AdaptiveRiskManager:
    def tune_thresholds(self, historical_exits):
        atr_exits = [e for e in historical_exits if e.reason == 'atr_stop']
        fixed_exits = [e for e in historical_exits if e.reason == 'stop_loss']

        # Compare P/L of each exit type
        # Adjust weights toward better-performing method
```

#### 4.3 Entry Timing Optimization
**Current**: Fixed 9:35 AM entry
**Target**: Learn optimal entry timing

```python
# Track: Did 9:35 entries outperform 9:40 entries?
# Adjust entry time based on historical pattern
class EntryTimingOptimizer:
    def analyze(self, historical_entries):
        # Bucket by time of day
        # Find optimal entry window per symbol/regime
```

---

## Implementation Priority

Based on current gaps and potential impact:

| Priority | Mode | Action | Impact | Effort |
|----------|------|--------|--------|--------|
| 1 | A1 | Enable DiscoRL online learning | High | Low |
| 2 | A1 | Integrate RiskAdjustedReward | High | Low |
| 3 | A2 | Add prediction tracking | Medium | Low |
| 4 | T2 | Adaptive position sizing | High | Medium |
| 5 | A2 | Confidence calibration | Medium | Medium |
| 6 | T1 | Sentiment fine-tuning | Medium | High |

---

## Quick Wins (Next 48 Hours)

### 1. Enable Online Learning
```python
# src/orchestrator/main.py - Add to _process_exit()
self.rl_filter.record_trade_outcome(
    entry_state, action, exit_state, reward, done
)
```

### 2. Use RiskAdjustedReward
```python
# src/agents/rl_weight_updater.py - Replace binary reward
from src.ml.reward_functions import RiskAdjustedReward
reward_fn = RiskAdjustedReward()
reward = reward_fn.compute(trade_result)
```

### 3. Track Predictions
```python
# Add to telemetry.record()
'prediction': {
    'confidence': rl_result['confidence'],
    'direction': rl_result['action'],
    'timestamp': datetime.utcnow().isoformat()
}
```

---

## Success Metrics

| Metric | Current | Target (Day 30) | Target (Day 90) |
|--------|---------|-----------------|-----------------|
| Win Rate | 66.6% | >58% sustained | >62% |
| Sharpe Ratio | 2.18 (backtest) | >1.0 live | >1.5 |
| Prediction Accuracy | Not tracked | Track baseline | >60% |
| Adaptation Loops | 1 (A1 partial) | 3 (A1, A2, T2) | 4 (all modes) |

---

## References

- Multi-university taxonomy paper (Stanford, Princeton, Harvard, UW)
- [Large Language Model Agent Survey](https://arxiv.org/abs/2503.21460)
- [Self-Evolving Agents Survey](https://arxiv.org/html/2507.21046v1)
- [Agentic RL for LLMs Survey](https://arxiv.org/html/2509.02547v1)
- Our RL feedback loop: `docs/rl-feedback-loop.md`

---

**Created**: 2025-12-11
**Status**: Implementation ready
**Next Action**: Enable DiscoRL online learning (Priority 1)
