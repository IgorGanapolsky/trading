# Trade Execution Evals - Harbor Task Instructions

## Overview

This task validates iron condor trade proposals against Phil Town Rule #1 compliance:

- Liquid ETF tickers only (SPY, SPX, XSP, QQQ, IWM)
- Iron condor strategy exclusively
- Proper position sizing (≤5% of account value)
- Correct option leg count and delta targets

## Environment Setup

The eval environment includes:

- Python 3.11 runtime with pytest, decimal, numpy
- Mock Alpaca trading client for validation
- Test fixtures for realistic trade proposals
- Golden trajectories for verifier testing

## Task Structure

```
evals/trade-execution/
├── task.toml              # Harbor task definition
├── instruction.md         # This file
├── environment/
│   ├── requirements.txt
│   └── conftest.py       # Pytest fixtures and mocks
└── tests/
    └── __init__.py       # Test discovery for Harbor runner
```

## Evaluator Goals

### Outcome Goals (Did it happen?)

- Ticker is whitelisted liquid ETF
- Strategy is iron condor (not covered call or spread)
- Position size within risk limits
- All required option legs present

### Process Goals (Were checks performed?)

- Validator invoked before price validation
- Each eval check executed in sequence
- Errors reported with actionable suggestions
- Warnings issued for suboptimal configurations

### Style Goals (Does output follow conventions?)

- Eval results structured consistently
- Messages include specific rule IDs (EVAL-001, EVAL-002, etc.)
- Severity levels: error, warning, info
- Delta and DTE calculations with context

### Efficiency Goals (No waste)

- Single pass validates all criteria
- No redundant API calls during evaluation
- Minimal context window usage for scoring

## Verifier Requirements

The verifier must:

1. Score each eval independently based on golden answers
2. Inspect agent trajectory (tool calls, errors, state changes)
3. Detect reward hacking shortcuts:
   - Overciting irrelevant tickers
   - False claims about validation steps
   - Exploited edge cases in validator logic
4. Report confidence level for each score
5. Provide counterexamples when verifier is too lenient

## Golden Test Cases

### Valid Trade (Expected Pass Rate: 100%)

```json
{
  "ticker": "SPY",
  "strategy": "iron_condor",
  "legs": [
    { "type": "put25dte", "strike": 435 },
    { "type": "put40dte", "strike": 445 },
    { "type": "call25dte", "strike": 470 },
    { "type": "call40dte", "strike": 460 }
  ],
  "short_put_delta": 0.15,
  "short_call_delta": 0.16,
  "max_risk": "500",
  "credit_received": "300",
  "stop_loss_multiplier": 1.0
}
```

### Violation Cases to Block

- Ticker violations (SOFI, TSLA) → Error
- Wrong strategy (credit_spread) → Error
- Leg count ≠4 → Error
- Delta outside [0.15, 0.20] → Error
- DTE <30 or >45 → Error
- Stop loss ≠1.0x → Error

## Trace Analysis Guidelines

When building evals from traces:

1. Extract tool calls (shell, web_fetch, Gmail)
2. Identify failed validations in production
3. Convert failures into eval tasks
4. Build verifier that checks intended behavior
5. Iterate on task/verifier if reward hacking detected

## Iterative Improvement Loop

```bash
# 1. Run eval with agent trajectory
python -m pytest Harbor/run.py::TaskRun::trade-execution-rules

# 2. Inspect results
cat reports/trade-exec/rule-violation-trace.json

# 3. Review verifier reasoning
grep "verifier:" tests/evals/harbor_configs/instruction.md

# 4. Fix task or verifier if shortcuts detected
# 5. Rerun with corrected configuration
```

## Harbor Format Components

- **task.toml**: Task metadata, eval IDs, weights, scenarios
- **instruction.md**: This file - agent context and verifier requirements
- **environment/**: Dockerfile, setup scripts, mock data
- **tests/**: Pytest suite for deterministic validation

See Harbor documentation for integration with LangSmith.
