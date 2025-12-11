# Promotion Gate Capital Scaling Feature

## Overview

Updated `/home/user/trading/scripts/enforce_promotion_gate.py` to automatically calculate and emit capital scaling recommendations when the promotion gate passes.

## New Arguments

### `--emit-scaling-plan`
- **Type**: Boolean flag
- **Default**: `True`
- **Purpose**: Controls whether to emit capital scaling plan to `data/plan/next_capital_step.json`

### `--current-daily-investment`
- **Type**: Float
- **Default**: `10.0`
- **Purpose**: Specifies the current daily investment amount as baseline for scaling calculations

## Scaling Logic

The script evaluates metrics against three tiers:

### 1. SCALE_UP (2.5x scaling)
**Criteria:**
- Sharpe ratio > 1.5 AND
- Win rate > 60% AND
- Max drawdown < 5%

**Example Output:**
```json
{
  "decision": "SCALE_UP",
  "from_daily_investment": 10.0,
  "to_daily_investment": 25.0,
  "scale_factor": 2.5,
  "confidence": 0.9,
  "justification": "Strong performance: Sharpe 2.00, Win Rate 65.0%, Drawdown 3.5% - exceeds all targets for aggressive scaling"
}
```

### 2. PROMOTE (1.5x scaling)
**Criteria:**
- Sharpe ratio >= threshold (1.2) AND
- Win rate >= threshold (55%) AND
- Max drawdown <= threshold (10%)

**Example Output:**
```json
{
  "decision": "PROMOTE",
  "from_daily_investment": 10.0,
  "to_daily_investment": 15.0,
  "scale_factor": 1.5,
  "confidence": 0.75,
  "justification": "Meets promotion criteria: Sharpe 1.30, Win Rate 57.0%, Drawdown 8.0% - conservative scaling recommended"
}
```

### 3. HOLD (1.0x - no scaling)
**Criteria:**
- Gate passes but metrics are borderline or don't meet higher tiers

**Example Output:**
```json
{
  "decision": "HOLD",
  "from_daily_investment": 10.0,
  "to_daily_investment": 10.0,
  "scale_factor": 1.0,
  "confidence": 0.5,
  "justification": "Borderline metrics: Sharpe 1.00, Win Rate 52.0%, Drawdown 9.0% - hold current capital until stronger performance"
}
```

## When Scaling Plan is Emitted

The script **only** emits `data/plan/next_capital_step.json` when:

1. ✅ `--emit-scaling-plan` is enabled (default: True)
2. ✅ Promotion gate passes with **no deficits**
3. ✅ **No override flags active** (clean pass only)

**The file is NOT emitted if:**
- ❌ Gate fails (any deficits)
- ❌ Override flags are active (ALLOW_PROMOTION_OVERRIDE, stale data)
- ❌ `--emit-scaling-plan` explicitly disabled

## Output File Structure

**Location:** `/home/user/trading/data/plan/next_capital_step.json`

**Format:**
```json
{
  "decision": "PROMOTE" | "HOLD" | "SCALE_UP",
  "timestamp": "2025-12-11T22:25:08.009185Z",
  "from_daily_investment": 10.0,
  "to_daily_investment": 15.0,
  "scale_factor": 1.5,
  "justification": "Sharpe 1.3, Win Rate 57%, Drawdown 8% - meets promotion criteria",
  "metrics": {
    "win_rate": 57.0,
    "sharpe_ratio": 1.3,
    "max_drawdown": 8.0,
    "total_trades": 120
  },
  "confidence": 0.75
}
```

## Usage Examples

### Default behavior (emit scaling plan enabled)
```bash
python3 scripts/enforce_promotion_gate.py
```

### Custom daily investment baseline
```bash
python3 scripts/enforce_promotion_gate.py --current-daily-investment 25.0
```

### Disable scaling plan emission
```bash
python3 scripts/enforce_promotion_gate.py --emit-scaling-plan=False
```

### Combined with other flags
```bash
python3 scripts/enforce_promotion_gate.py \
  --current-daily-investment 10.0 \
  --required-sharpe 1.5 \
  --required-win-rate 60.0 \
  --max-drawdown 5.0
```

## Console Output

When gate passes and scaling plan is emitted:
```
✅ Promotion gate satisfied. System may proceed to next stage.

📊 Capital scaling recommendation: SCALE_UP
   Current: $10.00/day
   Recommended: $25.00/day
   Confidence: 90%
   Plan saved to: data/plan/next_capital_step.json
```

## Integration with CI/CD

The scaling plan can be consumed by automated workflows:

```bash
# Check if scaling plan exists
if [ -f data/plan/next_capital_step.json ]; then
  DECISION=$(jq -r '.decision' data/plan/next_capital_step.json)
  NEW_AMOUNT=$(jq -r '.to_daily_investment' data/plan/next_capital_step.json)

  if [ "$DECISION" = "SCALE_UP" ]; then
    echo "🚀 Aggressive scaling recommended: $NEW_AMOUNT/day"
  elif [ "$DECISION" = "PROMOTE" ]; then
    echo "📈 Conservative scaling recommended: $NEW_AMOUNT/day"
  else
    echo "⏸️  Hold current investment level"
  fi
fi
```

## Benefits

1. **Automated Decision Support**: Removes guesswork from capital scaling decisions
2. **Risk-Aware**: Three tiers ensure conservative scaling for marginal performance
3. **Confidence Scoring**: Provides transparency on recommendation strength
4. **Audit Trail**: JSON artifact provides full context for scaling decisions
5. **CI/CD Ready**: Machine-parsable format enables automated workflows

## Created

- **Date**: December 11, 2025
- **Modified Files**: `/home/user/trading/scripts/enforce_promotion_gate.py`
- **New Output**: `/home/user/trading/data/plan/next_capital_step.json`
