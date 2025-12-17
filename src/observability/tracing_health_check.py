"""
Tracing Health Check - Verify LangSmith is operational before trading.

This module ensures we NEVER trade without working observability.
If LangSmith is down or misconfigured, trading should be blocked.

Created: Dec 16, 2025
Purpose: 100% operational integrity for tracing
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TracingHealthResult:
    """Result of tracing health check."""

    healthy: bool
    langsmith_configured: bool
    langsmith_reachable: bool
    tracer_initialized: bool
    test_trace_sent: bool
    errors: list[str]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "langsmith_configured": self.langsmith_configured,
            "langsmith_reachable": self.langsmith_reachable,
            "tracer_initialized": self.tracer_initialized,
            "test_trace_sent": self.test_trace_sent,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


class TracingHealthChecker:
    """
    Verify LangSmith tracing is fully operational.
    
    Run this BEFORE any trading to ensure observability is working.
    """

    def __init__(self):
        self.errors: list[str] = []

    def check_langsmith_configured(self) -> bool:
        """Check if LangSmith API key is configured."""
        api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
        if not api_key:
            self.errors.append("LANGSMITH_API_KEY not configured")
            return False
        if len(api_key) < 10:
            self.errors.append("LANGSMITH_API_KEY appears invalid (too short)")
            return False
        return True

    def check_langsmith_reachable(self) -> bool:
        """Check if LangSmith API is reachable."""
        try:
            from langsmith import Client

            api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
            if not api_key:
                return False

            client = Client(api_key=api_key)
            # Try to get info - this will fail if unreachable
            info = client.info
            if info:
                logger.info(f"LangSmith reachable: org={info.org_id if hasattr(info, 'org_id') else 'unknown'}")
                return True
            return False
        except ImportError:
            self.errors.append("langsmith package not installed")
            return False
        except Exception as e:
            self.errors.append(f"LangSmith unreachable: {e}")
            return False

    def check_tracer_initialized(self) -> bool:
        """Check if our tracer can be initialized."""
        try:
            from src.observability.langsmith_tracer import get_tracer

            tracer = get_tracer()
            if tracer is None:
                self.errors.append("Tracer returned None")
                return False
            return True
        except ImportError as e:
            self.errors.append(f"Tracer import failed: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Tracer initialization failed: {e}")
            return False

    def send_test_trace(self) -> bool:
        """Send a test trace to verify end-to-end functionality."""
        try:
            from src.observability.langsmith_tracer import TraceType, get_tracer

            tracer = get_tracer()
            
            with tracer.trace(
                name="health_check_test_trace",
                trace_type=TraceType.VERIFICATION,
            ) as span:
                span.inputs = {
                    "test": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "purpose": "Pre-trading health check",
                }
                span.add_output("status", "healthy")
                span.add_metadata({"health_check": True})

            logger.info("✅ Test trace sent successfully")
            return True
        except Exception as e:
            self.errors.append(f"Test trace failed: {e}")
            return False

    def run_full_check(self) -> TracingHealthResult:
        """
        Run complete health check.
        
        Returns TracingHealthResult with all checks.
        """
        self.errors = []
        timestamp = datetime.now(timezone.utc).isoformat()

        # Run all checks
        langsmith_configured = self.check_langsmith_configured()
        langsmith_reachable = self.check_langsmith_reachable() if langsmith_configured else False
        tracer_initialized = self.check_tracer_initialized()
        test_trace_sent = self.send_test_trace() if tracer_initialized else False

        # Overall health
        healthy = all([
            langsmith_configured,
            langsmith_reachable,
            tracer_initialized,
            test_trace_sent,
        ])

        result = TracingHealthResult(
            healthy=healthy,
            langsmith_configured=langsmith_configured,
            langsmith_reachable=langsmith_reachable,
            tracer_initialized=tracer_initialized,
            test_trace_sent=test_trace_sent,
            errors=self.errors,
            timestamp=timestamp,
        )

        if healthy:
            logger.info("✅ TRACING HEALTH CHECK PASSED - All systems operational")
        else:
            logger.error(f"❌ TRACING HEALTH CHECK FAILED: {self.errors}")

        return result


def verify_tracing_health(block_on_failure: bool = False) -> TracingHealthResult:
    """
    Verify tracing is healthy before trading.
    
    Args:
        block_on_failure: If True, raise exception on failure
        
    Returns:
        TracingHealthResult
        
    Raises:
        RuntimeError: If block_on_failure=True and check fails
    """
    checker = TracingHealthChecker()
    result = checker.run_full_check()

    if not result.healthy and block_on_failure:
        raise RuntimeError(
            f"Tracing health check failed - BLOCKING TRADING: {result.errors}"
        )

    return result


def require_healthy_tracing() -> TracingHealthResult:
    """
    Require healthy tracing or raise exception.
    
    Call this before any trading to ensure observability.
    """
    return verify_tracing_health(block_on_failure=True)


if __name__ == "__main__":
    # Run health check directly
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    result = verify_tracing_health()
    print(f"\nHealth Check Result: {'✅ HEALTHY' if result.healthy else '❌ UNHEALTHY'}")
    print(f"  LangSmith Configured: {result.langsmith_configured}")
    print(f"  LangSmith Reachable: {result.langsmith_reachable}")
    print(f"  Tracer Initialized: {result.tracer_initialized}")
    print(f"  Test Trace Sent: {result.test_trace_sent}")
    
    if result.errors:
        print("\nErrors:")
        for err in result.errors:
            print(f"  - {err}")
    
    sys.exit(0 if result.healthy else 1)
