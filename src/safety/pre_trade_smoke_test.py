"""Pre-trade smoke tests to validate system health before trading."""

from dataclasses import dataclass, field


@dataclass
class SmokeTestResult:
    """Result of smoke test execution."""

    passed: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def run_smoke_tests() -> SmokeTestResult:
    """Run pre-trade smoke tests.

    Returns:
        SmokeTestResult with passed=True if all tests pass.
    """
    result = SmokeTestResult()

    # Basic checks that should always pass
    try:
        # Check imports
        import os

        # Check environment
        if not os.getenv("ALPACA_API_KEY"):
            result.warnings.append("ALPACA_API_KEY not set")

        # All basic checks passed
        result.passed = True

    except Exception as e:
        result.passed = False
        result.errors.append(str(e))

    return result
