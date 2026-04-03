import pytest

# Skip all tests if anthropic is not available
pytest.importorskip("anthropic")

from src.agents.observability_agent import ObservabilityAgent
from src.monitoring.telemetry_gateway import TelemetryGateway


def test_observability_agent_detects_mismatch():
    gateway = TelemetryGateway()
    agent = ObservabilityAgent()

    trace_id = "test_mismatch_123"

    # 1. Capture 'submitted' but NOT 'filled'
    gateway.capture_span("order_submitted", trace_id=trace_id)

    # 2. Audit the trace
    report = agent.audit_trace(trace_id)

    # 3. Verify it found the mismatch
    assert report["healthy"] is False
    assert report["issue"] == "UNFILLED_ORDER"


def test_observability_agent_verifies_success():
    gateway = TelemetryGateway()
    agent = ObservabilityAgent()

    trace_id = "test_success_123"

    # 1. Capture full cycle
    gateway.capture_span("order_submitted", trace_id=trace_id)
    gateway.capture_span("order_filled", trace_id=trace_id)

    # 2. Audit the trace
    report = agent.audit_trace(trace_id)

    # 3. Verify it passes
    assert report["healthy"] is True


def test_observability_agent_detects_juror_bypass():
    gateway = TelemetryGateway()
    agent = ObservabilityAgent()

    trace_id = "test_bypass_123"

    # 1. Only capture entry without juror
    gateway.capture_span("strategy_entry", trace_id=trace_id)

    # 2. Audit the trace
    report = agent.audit_trace(trace_id)

    # 3. Verify violation flagged
    assert report["healthy"] is False
    assert report["issue"] == "JUROR_BYPASS"
