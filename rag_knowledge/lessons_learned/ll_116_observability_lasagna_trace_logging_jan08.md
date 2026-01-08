# Lesson Learned #116: Observability Lasagna - Connecting Logs to Traces

**Date**: 2026-01-08
**Category**: Observability
**Severity**: Enhancement
**Source**: InfoQ presentation by Martha (Incident.io) - "Stop Building Dashboard Soup"

## Summary

Implemented the "observability lasagna" pattern from Incident.io's framework. The key insight: having logs, traces, and metrics isn't enough - they must be **connected**. Added trace_id/span_id to all log entries, enabling direct navigation from logs to LangSmith traces.

## The Problem: Dashboard Soup

Before this change, our observability was disconnected:
- LangSmith traces existed but logs didn't reference them
- When debugging, you'd see a log error but couldn't find the trace
- Slack alerts had no link to the trace context

This is "dashboard soup" - tools exist but don't connect.

## The Solution: Lasagna Layers with Arrows

The "lasagna" model has 4 layers, each connected to the next:

```
┌─────────────────────────────────────┐
│  1. Overview Dashboard (traffic light) │
│         ↓ (drill down)               │
│  2. System Dashboard (SLIs)          │
│         ↓ (click metric)             │
│  3. Logs (with trace_id/span_id)     │
│         ↓ (trace URL)                │
│  4. Traces (detailed execution)      │
└─────────────────────────────────────┘
```

**The critical part**: Each layer has an "arrow" to the next.

## Implementation

### 1. TraceContextFilter (logging_config.py:21-93)

Injects trace_id and span_id into every log record:

```python
class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = "-"  # default
        record.span_id = "-"

        tracer = self._get_tracer()
        if tracer and tracer._current_trace:
            record.trace_id = tracer._current_trace.trace_id[:8]
        if tracer and tracer._span_stack:
            record.span_id = tracer._span_stack[-1].span_id
        return True
```

### 2. Updated Log Format

Before:
```
2026-01-08 10:30:00 - trading - INFO - Message
```

After:
```
2026-01-08 10:30:00 - trading - INFO - [trace:abc123/span:def456] - Message
```

### 3. Trace URLs in Slack Alerts (error_monitoring.py)

Slack alerts now include clickable trace links:
```
:rotating_light: Trading System Alert
Risk limit exceeded for TSLA

:mag: View Trace in LangSmith  ← Clickable link!

trace_id: abc123
```

## What We Skipped (Right-Sizing for Our Scale)

Incident.io is a 100+ engineer SaaS company. We're a 2-person trading bot. These were **overkill**:

| Framework Feature | Why We Skipped |
|-------------------|----------------|
| Grafana K6 load testing | Our load is ~5 trades/day |
| Exemplars (clickable metric dots) | Complex infrastructure for minimal gain |
| Quarterly game days | 2-person team |
| Live capacity visualization | Not a high-traffic system |

## Testing

```bash
# Without trace - shows [trace:-/span:-]
logger.info("No trace active")

# With trace - shows actual IDs
with tracer.trace("operation") as span:
    logger.info("Processing...")  # [trace:40307846/span:44c859ad]
```

## Files Changed

- `src/utils/logging_config.py` - TraceContextFilter, get_trace_context(), get_langsmith_trace_url()
- `src/utils/error_monitoring.py` - Trace URLs in Slack alerts

## Key Takeaway

**Don't just add observability tools - connect them.** A log entry should lead to a trace. A metric should drill down to logs. An alert should link to the source.

## References

- Source video: https://youtu.be/3LZmc8-8des
- InfoQ: "Stop Building Dashboard Soup: Scalable Observability Lasagna"
- LangSmith documentation for trace context
