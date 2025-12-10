# Model Validation Checklist

A formal validation checklist that every new model, strategy, or gate must pass before deployment. Inspired by banking model risk management guidelines (SR 11-7, OCC 2011-12) adapted for systematic trading.

## Purpose

This checklist ensures consistent validation standards across all models and gates in the trading system. Every new model or significant parameter change is treated as a "new model version" requiring full validation.

---

## Pre-Deployment Validation Checklist

### 1. Data Quality Checks

- [ ] **Data Completeness**: Verify no missing values in critical features
  - Check: `df.isnull().sum()` for each feature
  - Threshold: < 1% missing values

- [ ] **Data Freshness**: Confirm data is current
  - Check: Latest data point within expected timeframe
  - Threshold: Data must be < 24 hours old for live trading

- [ ] **Data Consistency**: Verify no outliers or anomalies
  - Check: Z-score analysis on price/volume data
  - Threshold: Flag values > 5 standard deviations

- [ ] **Data Source Verification**: Confirm data from authorized sources
  - Sources: Alpaca API (primary), Yahoo Finance (fallback)
  - Document: Data source for each feature

### 2. Walk-Forward Validation

- [ ] **Out-of-Sample Testing**: All parameters tested on unseen data
  - Method: Rolling walk-forward with train/test splits
  - Minimum: 4 walk-forward windows
  - Reference: `src/backtesting/walk_forward_matrix.py`

- [ ] **OOS Sharpe Ratio**: Meet minimum threshold
  - Threshold: Mean OOS Sharpe >= 0.8
  - Check: `results.mean_oos_sharpe`

- [ ] **Sharpe Decay**: Verify no significant overfitting
  - Threshold: IS Sharpe - OOS Sharpe <= 0.5
  - Check: `results.avg_sharpe_decay`

- [ ] **Consistency Across Windows**: Stable performance
  - Threshold: > 60% of windows profitable
  - Check: `results.sharpe_consistency`

### 3. Sensitivity Analysis

- [ ] **Parameter Sensitivity**: Test stability across parameter ranges
  - Method: Vary each parameter ±20% from optimal
  - Threshold: Performance degradation < 30%

- [ ] **Regime Sensitivity**: Test across market conditions
  - Regimes: Bull, Bear, Sideways, High Volatility
  - Threshold: Positive expectancy in at least 3/4 regimes

- [ ] **Time Period Sensitivity**: Test across different periods
  - Minimum: 3 non-overlapping periods
  - Threshold: Consistent positive returns

### 4. Benchmarking

- [ ] **Benchmark Comparison**: Outperform relevant benchmark
  - Equity strategies: SPY buy-and-hold
  - Threshold: Alpha > 0 with statistical significance (p < 0.05)

- [ ] **Risk-Adjusted Comparison**: Better risk-adjusted returns
  - Metric: Sharpe, Sortino, Calmar ratios
  - Threshold: Sharpe >= 1.0 for production

- [ ] **Maximum Drawdown**: Within acceptable limits
  - Threshold: Max DD <= 15%

### 5. Error Tolerance

- [ ] **Graceful Degradation**: System handles errors safely
  - Test: Simulate API failures, data gaps
  - Behavior: Fail-safe to cash or reduce exposure

- [ ] **Circuit Breaker Integration**: Connected to safety systems
  - Check: Model triggers appropriate circuit breaker on failure
  - Reference: `src/safety/multi_tier_circuit_breaker.py`

- [ ] **Logging & Alerting**: Errors properly captured
  - Check: All errors logged with context
  - Check: Critical errors trigger alerts

---

## Post-Deployment Monitoring

### 6. Live vs Backtest Divergence

- [ ] **Performance Tracking**: Monitor live vs expected
  - Metric: Sharpe divergence, return divergence
  - Threshold: Alert if divergence > 30%
  - Reference: `src/backtesting/walk_forward_matrix.py:LiveVsBacktestTracker`

- [ ] **30-Day Monitoring Period**: New models under observation
  - Check: Compare live metrics to validation metrics
  - Action: Auto-rollback if significant underperformance

### 7. Regime Change Detection

- [ ] **Regime Monitoring**: Detect changing market conditions
  - Method: Rolling volatility, trend detection
  - Action: Adjust parameters via adaptive system

- [ ] **Performance Decay Detection**: Identify strategy decay
  - Metric: Rolling 90-day Sharpe
  - Threshold: Alert if Sharpe drops below 1.0
  - Reference: `src/safety/circuit_breakers.py:SharpeKillSwitch`

---

## Approval Requirements

### For Minor Changes (< 10% parameter adjustment)
- [ ] Walk-forward validation passed
- [ ] Sensitivity analysis complete
- [ ] Automated approval via CI/CD

### For Major Changes (new model or > 10% parameter change)
- [ ] Full checklist completed
- [ ] Documentation updated
- [ ] 30-day paper trading validation
- [ ] CEO approval for production deployment

### For Critical Systems (circuit breakers, risk management)
- [ ] All above requirements
- [ ] Code review by second developer
- [ ] Stress testing under extreme conditions
- [ ] Manual CEO/CTO sign-off

---

## Validation Record Template

```json
{
  "model_name": "string",
  "version": "string",
  "validation_date": "YYYY-MM-DD",
  "validator": "string",

  "data_quality": {
    "completeness_check": true,
    "freshness_check": true,
    "consistency_check": true,
    "missing_value_pct": 0.0
  },

  "walk_forward_validation": {
    "total_windows": 4,
    "mean_oos_sharpe": 1.2,
    "sharpe_decay": 0.3,
    "sharpe_consistency": 0.75,
    "passed": true
  },

  "sensitivity_analysis": {
    "parameter_sensitivity": "low",
    "regime_sensitivity": "acceptable",
    "time_sensitivity": "acceptable"
  },

  "benchmarking": {
    "vs_spy_alpha": 0.05,
    "sharpe_ratio": 1.2,
    "max_drawdown": 0.08,
    "passed": true
  },

  "error_handling": {
    "graceful_degradation": true,
    "circuit_breaker_integrated": true,
    "logging_complete": true
  },

  "approval": {
    "automated_checks_passed": true,
    "manual_review_required": false,
    "approved_by": "system",
    "approved_date": "YYYY-MM-DD"
  }
}
```

---

## Related Documentation

- [Model Risk Management](MODEL_RISK_MANAGEMENT.md)
- [Walk-Forward Matrix](../src/backtesting/walk_forward_matrix.py)
- [Multi-Tier Circuit Breaker](../src/safety/multi_tier_circuit_breaker.py)
- [Adaptive Parameters](../src/utils/adaptive_parameters.py)

---

**Last Updated**: 2025-12-02
**Version**: 1.0
