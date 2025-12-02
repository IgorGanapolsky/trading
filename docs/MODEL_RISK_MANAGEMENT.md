# Model Risk Management

A comprehensive model risk management framework inspired by banking regulatory guidelines (SR 11-7, OCC 2011-12, FDIC guidelines). This document provides an inventory of all models/gates, their assumptions, known limitations, and parameter governance.

## Purpose

Model risk is the potential for adverse consequences from decisions based on incorrect or misused model outputs. This framework ensures:

1. All models are properly inventoried and documented
2. Assumptions and limitations are clearly understood
3. Parameter changes are governed and tracked
4. Model performance is continuously monitored

---

## Model Inventory

### Gate 1: Momentum Signal Generator

| Attribute | Value |
|-----------|-------|
| **Model Name** | MomentumAgent |
| **Location** | `src/agents/momentum_agent.py` |
| **Type** | Rule-based indicator analysis |
| **Owner** | Trading System |
| **Last Validated** | 2025-12-02 |

**Description**: Analyzes technical indicators (MACD, RSI, volume) to generate momentum signals.

**Key Inputs**:
- Price history (60+ days)
- Volume data
- Configurable thresholds

**Key Outputs**:
- `is_buy`: Boolean buy signal
- `strength`: Signal strength (0-1)
- `indicators`: Dict of indicator values

**Assumptions**:
1. Technical indicators have predictive power for short-term price movements
2. Historical patterns repeat with similar probability
3. Market microstructure remains stable

**Known Limitations**:
- Performs poorly in gap-up/gap-down scenarios
- Lag inherent in moving average indicators
- May generate false signals in sideways markets

**Parameter Governance**:
| Parameter | Default | Range | Owner | Change Authority |
|-----------|---------|-------|-------|-----------------|
| `min_score` | 0.0 | -10 to 20 | System | Automated |
| `macd_threshold` | 0.0 | -0.1 to 0.1 | System | Automated |
| `rsi_overbought` | 70 | 60-80 | System | CEO approval |
| `volume_min` | 0.8 | 0.5-1.5 | System | Automated |

---

### Gate 2: RL Filter

| Attribute | Value |
|-----------|-------|
| **Model Name** | RLFilter (LSTM-PPO) |
| **Location** | `src/agents/rl_agent.py` |
| **Type** | Deep reinforcement learning |
| **Owner** | Trading System |
| **Last Validated** | 2025-12-02 |

**Description**: LSTM-PPO neural network that filters momentum signals based on learned patterns.

**Key Inputs**:
- Momentum signal indicators
- Historical state features
- Market regime indicators

**Key Outputs**:
- `action`: "long", "short", "hold"
- `confidence`: Model confidence (0-1)
- `explainability`: Feature contributions

**Assumptions**:
1. Patterns in historical data generalize to future
2. Training data is representative of future regimes
3. Model capacity sufficient for market complexity

**Known Limitations**:
- May overfit to training data regime
- Cold start problem with new market regimes
- Requires periodic retraining
- Black-box nature limits interpretability

**Parameter Governance**:
| Parameter | Default | Range | Owner | Change Authority |
|-----------|---------|-------|-------|-----------------|
| `confidence_threshold` | 0.6 | 0.4-0.85 | System | Automated |
| `model_path` | models/rl_agent.pt | - | System | Manual + Validation |
| `hidden_dim` | 128 | 64-256 | ML Team | Manual + Validation |

**Retraining Policy**:
- Frequency: Monthly minimum, triggered by performance decay
- Validation: Walk-forward with 4+ windows
- Approval: Automated if metrics pass thresholds

---

### Gate 3: LLM Sentiment Analyst

| Attribute | Value |
|-----------|-------|
| **Model Name** | LangChainSentimentAgent |
| **Location** | `src/langchain_agents/analyst.py` |
| **Type** | LLM-based sentiment analysis |
| **Owner** | Trading System |
| **Last Validated** | 2025-12-02 |

**Description**: Uses LLM to analyze news and sentiment for trading signals.

**Key Inputs**:
- News articles
- Social media sentiment
- Market context

**Key Outputs**:
- `score`: Sentiment score (-1 to 1)
- `reason`: Natural language explanation
- `cost`: API cost for the call

**Assumptions**:
1. LLM can accurately interpret market sentiment
2. News sentiment correlates with short-term price moves
3. API responses are consistent and reliable

**Known Limitations**:
- API latency and cost constraints
- Potential for prompt injection in news content
- May not capture real-time sentiment shifts
- Budget constraints limit call frequency

**Parameter Governance**:
| Parameter | Default | Range | Owner | Change Authority |
|-----------|---------|-------|-------|-----------------|
| `negative_threshold` | -0.2 | -0.5 to 0 | System | Automated |
| `model_name` | gpt-4o | - | System | Manual |
| `monthly_budget` | $100 | - | CEO | CEO approval |

---

### Gate 4: Risk Manager

| Attribute | Value |
|-----------|-------|
| **Model Name** | RiskManager |
| **Location** | `src/risk/risk_manager.py` |
| **Type** | Kelly criterion + ATR sizing |
| **Owner** | Trading System |
| **Last Validated** | 2025-12-02 |

**Description**: Calculates position sizes based on signal strength, confidence, and risk parameters.

**Key Inputs**:
- Account equity
- Signal strength
- RL confidence
- Sentiment score
- Market volatility (ATR)

**Key Outputs**:
- `notional`: Dollar amount to trade
- `stop_loss`: Calculated stop price

**Assumptions**:
1. Kelly criterion provides optimal position sizing
2. ATR is a good volatility proxy
3. Past volatility predicts future volatility

**Known Limitations**:
- Kelly can suggest aggressive sizing
- ATR lag in volatile transitions
- Doesn't account for correlation between positions

**Parameter Governance**:
| Parameter | Default | Range | Owner | Change Authority |
|-----------|---------|-------|-------|-----------------|
| `max_position_pct` | 5% | 2-10% | System | Automated |
| `min_notional` | $3 | $1-10 | System | Automated |
| `atr_multiplier` | 2.0 | 1.5-4.0 | System | Automated |
| `kelly_cap` | 5% | 2-10% | CEO | CEO approval |

---

### Safety System: Multi-Tier Circuit Breaker

| Attribute | Value |
|-----------|-------|
| **Model Name** | MultiTierCircuitBreaker |
| **Location** | `src/safety/multi_tier_circuit_breaker.py` |
| **Type** | Rule-based safety system |
| **Owner** | Trading System |
| **Last Validated** | 2025-12-02 |

**Description**: Multi-tier circuit breaker with soft pause and hard stop capabilities.

**Assumptions**:
1. VIX is a valid proxy for market stress
2. Consecutive losses indicate strategy problems
3. Daily loss limits prevent catastrophic losses

**Known Limitations**:
- May trigger false positives in volatile but profitable periods
- Requires manual reset for HALT tier
- Doesn't prevent intraday flash crashes

**Parameter Governance**:
| Parameter | Default | Range | Owner | Change Authority |
|-----------|---------|-------|-------|-----------------|
| `tier1_loss_pct` | 1% | 0.5-2% | System | Automated |
| `tier2_loss_pct` | 2% | 1-3% | System | Automated |
| `tier3_loss_pct` | 3% | 2-5% | CEO | CEO approval |
| `tier4_loss_pct` | 5% | 3-10% | CEO | CEO approval |
| `vix_critical` | 40 | 30-50 | System | Manual |

---

## Model Change Governance

### Change Classification

| Change Type | Examples | Approval Required |
|-------------|----------|-------------------|
| **Minor** | Threshold adjustment < 10% | Automated validation |
| **Moderate** | New feature, 10-30% parameter change | Walk-forward + automated |
| **Major** | New model architecture | Full validation + manual review |
| **Critical** | Safety system changes | Full validation + CEO sign-off |

### Change Process

1. **Proposal**: Document proposed change with rationale
2. **Development**: Implement change in isolated branch
3. **Validation**: Run MODEL_VALIDATION_CHECKLIST
4. **Review**: Appropriate approval based on classification
5. **Deployment**: Deploy to paper trading first
6. **Monitoring**: 30-day observation period
7. **Confirmation**: Confirm or rollback based on performance

### Version Control

All model versions are tracked in `data/model_versions.json`:

```json
{
  "v20251202_123456": {
    "created_at": "2025-12-02T12:34:56",
    "parameters": {...},
    "validation_results": {...},
    "is_active": true,
    "superseded_by": null,
    "notes": "Created by automated re-optimization"
  }
}
```

---

## Risk Monitoring

### Key Risk Indicators (KRIs)

| KRI | Threshold | Action |
|-----|-----------|--------|
| Rolling 30-day Sharpe | < 0.5 | Alert |
| Rolling 30-day Sharpe | < 0 | Soft pause |
| Rolling 90-day Sharpe | < 1.0 | Review strategy |
| Max Drawdown | > 10% | Alert |
| Max Drawdown | > 15% | Hard stop |
| Daily Loss | > 2% | Soft pause |
| Daily Loss | > 5% | Full halt |
| Gate Error Rate | > 5% | Alert |
| Live vs Backtest Divergence | > 30% | Review |

### Monitoring Dashboard

Real-time monitoring available via:
- `src/orchestrator/sre_monitor.py` - SRE-style metrics
- `dashboard/` - Streamlit dashboard

---

## Model Lifecycle

### Development → Validation → Production → Retirement

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Development  │───▶│  Validation  │───▶│  Production  │───▶│  Retirement  │
│              │    │              │    │              │    │              │
│ - Design     │    │ - Checklist  │    │ - Monitoring │    │ - Deprecated │
│ - Implement  │    │ - Backtest   │    │ - Alerts     │    │ - Archived   │
│ - Unit test  │    │ - Review     │    │ - Reoptimize │    │ - Replaced   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Retirement Criteria

A model should be retired when:
1. Performance has degraded below acceptable thresholds for 90+ days
2. Market structure changes make assumptions invalid
3. Better alternative model is validated
4. Regulatory or compliance requirements change

---

## Regulatory Alignment

This framework aligns with:

- **SR 11-7**: Federal Reserve Supervisory Guidance on Model Risk Management
- **OCC 2011-12**: Comptroller's Handbook on Model Risk Management
- **FDIC Risk Management Manual**: Model Risk Management section

Key principles applied:
1. Sound model development and implementation
2. Thorough testing and validation
3. Effective challenge (independent review)
4. Ongoing monitoring

---

## Related Documentation

- [Model Validation Checklist](MODEL_VALIDATION_CHECKLIST.md)
- [Walk-Forward Matrix](../src/backtesting/walk_forward_matrix.py)
- [Multi-Tier Circuit Breaker](../src/safety/multi_tier_circuit_breaker.py)
- [Re-Optimization Scheduler](../src/ml/reoptimization_scheduler.py)
- [Adaptive Parameters](../src/utils/adaptive_parameters.py)

---

**Document Owner**: Trading System CTO  
**Review Frequency**: Quarterly  
**Last Updated**: 2025-12-02  
**Version**: 1.0
