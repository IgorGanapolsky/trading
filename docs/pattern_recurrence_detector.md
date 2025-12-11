# Pattern Recurrence Detector

**Module**: `src/verification/pattern_recurrence_detector.py`
**Created**: December 11, 2025
**Purpose**: Detect when the same type of mistake is happening repeatedly

## Overview

The Pattern Recurrence Detector analyzes anomaly logs to identify recurring patterns that indicate systemic issues. It detects temporal clustering (patterns recurring every 2-5 days), escalates severity based on frequency, and provides RAG-based prevention suggestions.

## Key Features

1. **Temporal Clustering Detection**: Identifies patterns recurring every 2-5 days
2. **Severity Escalation**: LOW → MEDIUM → HIGH → CRITICAL based on recurrence count
3. **Trend Analysis**: Detects if patterns are increasing, stable, or decreasing
4. **RAG Integration**: Queries lessons learned for prevention suggestions
5. **GitHub Integration**: Auto-creates issues for critical patterns
6. **JSON Reports**: Generates detailed reports for monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Pattern Recurrence Flow                    │
└─────────────────────────────────────────────────────────────┘

1. Load Anomalies
   ↓
   data/anomaly_log.json → PatternRecurrenceDetector

2. Filter by Time Window
   ↓
   Last N days (default: 7)

3. Group by Type
   ↓
   order_amount, data_staleness, price_deviation, etc.

4. Analyze Each Pattern
   ↓
   ├─ Calculate frequency (avg days between occurrences)
   ├─ Determine severity (based on count)
   ├─ Analyze trend (increasing/stable/decreasing)
   └─ Query RAG for prevention suggestions

5. Generate Report
   ↓
   data/pattern_recurrence_report.json

6. Optional: Create GitHub Issues
   ↓
   Critical patterns → GitHub Issues (auto-labeled)
```

## Usage

### Basic Usage

```python
from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

# Create detector
detector = PatternRecurrenceDetector(
    recurrence_threshold=3,  # Flag patterns with 3+ occurrences
    window_days=7,           # Look back 7 days
    clustering_threshold_days=5  # Flag patterns recurring every 5 days
)

# Analyze patterns
report = detector.analyze_patterns()

# Print summary
print(f"Total Anomalies: {report['total_anomalies']}")
print(f"Recurring Patterns: {len(report['recurring_patterns'])}")
print(f"Critical Patterns: {len(report['critical_patterns'])}")

# Inspect patterns
for pattern in report['recurring_patterns']:
    print(f"{pattern['pattern_type']}: {pattern['severity']} ({pattern['count']} occurrences)")
```

### Get Recurring Patterns

```python
# Get patterns as RecurringPattern objects
patterns = detector.get_recurring_patterns()

for pattern in patterns:
    print(f"{pattern.pattern_type}:")
    print(f"  Severity: {pattern.severity}")
    print(f"  Frequency: Every {pattern.frequency_days:.1f} days")
    print(f"  Trend: {pattern.trend}")
    print(f"  Prevention: {pattern.prevention}")
```

### Escalate Pattern Severity

```python
# Manually escalate a pattern (e.g., based on human review)
detector.escalate_pattern("order_amount")
# This escalates: LOW → MEDIUM → HIGH → CRITICAL
```

### Create GitHub Issues

```python
# Create GitHub issue for critical pattern (requires gh CLI)
for pattern in detector.patterns:
    if pattern.severity == "CRITICAL":
        url = detector.create_github_issue(pattern)
        print(f"Created issue: {url}")
```

### Daily Cron Job

```python
from src.verification.pattern_recurrence_detector import run_daily_pattern_analysis

# Run analysis (designed for cron)
report = run_daily_pattern_analysis(
    recurrence_threshold=3,
    window_days=7,
    auto_create_issues=True  # Auto-create GitHub issues for critical patterns
)
```

**Cron Setup (8 AM ET daily)**:
```bash
0 8 * * * cd /home/user/trading && python3 -c "from src.verification.pattern_recurrence_detector import run_daily_pattern_analysis; run_daily_pattern_analysis(auto_create_issues=True)"
```

## Severity Levels

Pattern severity is determined by occurrence count within the time window:

| Severity | Count | Action Required |
|----------|-------|-----------------|
| LOW | 2-3 | Monitor |
| MEDIUM | 4-6 | Review and address |
| HIGH | 7-10 | Urgent attention |
| CRITICAL | 11+ | **Immediate action** + auto-create GitHub issue |

## Temporal Clustering

Patterns recurring every 2-5 days are flagged as "clustered":

```python
detector = PatternRecurrenceDetector(clustering_threshold_days=5)
report = detector.analyze_patterns()

# Clustered patterns logged as warnings
# Example: "CLUSTERING DETECTED: order_amount recurring every 2.3 days"
```

This detects systematic issues like:
- Daily cron job failures
- Recurring data staleness at specific times
- Periodic configuration errors

## Trend Analysis

The detector analyzes if patterns are increasing, stable, or decreasing:

- **Increasing**: Second half of window has 1.5x+ more occurrences than first half
- **Decreasing**: Second half has <67% occurrences of first half
- **Stable**: Between 67%-150%

Example:
```python
pattern.trend  # "increasing", "stable", or "decreasing"
```

## RAG Integration

The detector queries `data/rag/lessons_learned.json` for prevention suggestions:

```python
# RAG lookup happens automatically
pattern.prevention  # "Implement stricter validation and circuit breakers"
```

**Fallback**: If no RAG match found, returns generic suggestion:
```
"Review anomaly log and implement targeted prevention measures"
```

## Report Format

**Location**: `data/pattern_recurrence_report.json`

```json
{
  "recurring_patterns": [
    {
      "pattern_type": "order_amount",
      "count": 12,
      "first_seen": "2025-11-27T10:00:00+00:00",
      "last_seen": "2025-12-11T10:00:00+00:00",
      "frequency_days": 2.0,
      "severity": "CRITICAL",
      "trend": "increasing",
      "prevention": "Implement stricter validation and circuit breakers",
      "occurrences": [...]
    }
  ],
  "total_anomalies": 42,
  "unique_types": 5,
  "critical_patterns": [...],
  "generated_at": "2025-12-11T14:30:00+00:00",
  "window_days": 7,
  "recurrence_threshold": 3
}
```

## GitHub Issue Creation

For CRITICAL patterns, the detector can auto-create GitHub issues:

**Prerequisites**:
- `gh` CLI installed and authenticated
- Repository access: `IgorGanapolsky/trading`

**Issue Format**:
```
Title: [CRITICAL] Recurring Pattern: order_amount (12 occurrences)

Body:
## Critical Recurring Pattern Detected

**Pattern Type**: `order_amount`
**Severity**: CRITICAL
**Occurrences**: 12 times in 7 days
**Frequency**: Every 2.0 days
**Trend**: increasing

### Timeline
- **First Seen**: 2025-11-27T10:00:00+00:00
- **Last Seen**: 2025-12-11T10:00:00+00:00

### Prevention Suggestion
Implement stricter validation and circuit breakers

### Action Required
This pattern has been flagged as CRITICAL due to high recurrence rate.
Review the anomaly log and implement preventive measures immediately.
```

**Labels**: `bug`, `critical`, `automated`

## Integration with Anomaly Detector

The Pattern Recurrence Detector reads anomalies logged by `src/ml/anomaly_detector.py`:

```python
# Anomaly types tracked:
- order_amount        # Unusual order size
- order_frequency     # Too many/few orders
- price_deviation     # Price far from expected
- data_staleness      # Old data being used
- execution_failure   # Trade execution issues
- symbol_unknown      # Unknown trading symbol
- market_hours        # Trading outside hours
- position_size       # Position too large
- volatility_spike    # Unusual market volatility
```

## Testing

**Test Suite**: `tests/test_pattern_recurrence_detector.py`
**Coverage**: 28 tests, all passing

Run tests:
```bash
python3 -m pytest tests/test_pattern_recurrence_detector.py -v
```

Test categories:
- Pattern detection and grouping
- Frequency calculation
- Severity escalation
- Trend analysis
- RAG integration
- Report generation
- GitHub issue creation
- Edge cases (empty logs, malformed JSON, etc.)

## Example Scenarios

### Scenario 1: Detecting Systematic Order Amount Errors

```
Day 1: order_amount anomaly (severity: LOW)
Day 3: order_amount anomaly (severity: LOW)
Day 5: order_amount anomaly (severity: MEDIUM)
Day 7: order_amount anomaly (severity: MEDIUM)
Day 9: order_amount anomaly (severity: HIGH)

Detector Output:
  Pattern: order_amount
  Count: 5
  Severity: MEDIUM
  Frequency: Every 2.0 days
  Trend: stable
  Action: Review and address
```

### Scenario 2: Escalating Data Staleness

```
Week 1: 3 data_staleness anomalies (MEDIUM)
Week 2: 6 data_staleness anomalies (MEDIUM → escalated to HIGH)
Week 3: 12 data_staleness anomalies (HIGH → escalated to CRITICAL)

Detector Output:
  Pattern: data_staleness
  Count: 21
  Severity: CRITICAL
  Frequency: Every 1.3 days
  Trend: increasing
  Action: Immediate - GitHub issue created
```

### Scenario 3: Decreasing Price Deviation

```
Days 1-7: 8 price_deviation anomalies (HIGH)
Days 8-14: 3 price_deviation anomalies (LOW)

Detector Output:
  Pattern: price_deviation
  Count: 11
  Severity: CRITICAL
  Frequency: Every 1.4 days
  Trend: decreasing
  Action: Monitor (improving but still high count)
```

## Best Practices

1. **Run Daily**: Set up cron job to run at 8 AM ET daily
2. **Review Critical Patterns**: Check GitHub issues for CRITICAL patterns
3. **Escalate Manually**: Use `escalate_pattern()` when human review identifies severity
4. **Adjust Thresholds**: Tune `recurrence_threshold` and `window_days` based on your needs
5. **RAG Integration**: Keep `data/rag/lessons_learned.json` updated for better prevention suggestions
6. **Monitor Trends**: Pay special attention to "increasing" trends

## Monitoring Dashboard Integration

Add to Streamlit dashboard:

```python
import streamlit as st
from src.verification.pattern_recurrence_detector import PatternRecurrenceDetector

def show_recurring_patterns():
    detector = PatternRecurrenceDetector(window_days=7)
    report = detector.analyze_patterns()

    st.header("Recurring Patterns")
    st.metric("Total Anomalies", report['total_anomalies'])
    st.metric("Critical Patterns", len(report['critical_patterns']))

    # Show critical patterns
    if report['critical_patterns']:
        st.error("⚠️ Critical patterns requiring attention:")
        for pattern in report['critical_patterns']:
            st.write(f"- {pattern['pattern_type']}: {pattern['count']} occurrences")
```

## Files

- **Core**: `/home/user/trading/src/verification/pattern_recurrence_detector.py`
- **Tests**: `/home/user/trading/tests/test_pattern_recurrence_detector.py`
- **Examples**: `/home/user/trading/examples/pattern_recurrence_example.py`
- **Documentation**: `/home/user/trading/docs/pattern_recurrence_detector.md`

## Related Systems

- **Anomaly Detector**: `src/ml/anomaly_detector.py` (logs anomalies)
- **RAG System**: `src/rag/lessons_learned_rag.py` (provides prevention suggestions)
- **Verification Framework**: `src/verification/` (pre-merge checks, output verification)

## Future Enhancements

1. **Email Alerts**: Send email for critical patterns
2. **Slack Integration**: Post to Slack channel for high-severity patterns
3. **Auto-Remediation**: Trigger automated fixes for known patterns
4. **Pattern Correlation**: Detect when multiple patterns occur together
5. **Predictive Alerting**: Predict when patterns will recur next

## Changelog

- **2025-12-11**: Initial implementation
  - Basic pattern detection
  - Severity escalation
  - RAG integration
  - GitHub issue creation
  - Comprehensive test suite (28 tests)
