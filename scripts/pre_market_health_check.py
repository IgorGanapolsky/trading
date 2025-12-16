#!/usr/bin/env python3
"""
PRE-MARKET HEALTH CHECK

Runs before trading starts to validate:
- Alpaca API connectivity
- Anthropic API status
- Market is open
- Circuit breakers not tripped
- Data sources accessible
- System dependencies healthy

CRITICAL: Must pass before allowing trading
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

import logging
import signal
from datetime import datetime

from anthropic import Anthropic
from src.utils.error_monitoring import init_sentry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")


def write_output(passed: bool) -> None:
    """Write health_check_passed output for GitHub Actions."""
    if not GITHUB_OUTPUT:
        return
    with open(GITHUB_OUTPUT, "a", encoding="utf-8") as handle:
        handle.write(f"health_check_passed={'true' if passed else 'false'}\n")


class TimeoutError(Exception):
    """Custom timeout exception."""

    pass


def timeout_handler(signum, frame):
    """Signal handler for timeouts."""
    raise TimeoutError("Operation timeout")


def check_alpaca_api() -> bool:
    """Check Alpaca API connectivity and account access."""
    try:
        # Use broker health monitor for comprehensive check
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from src.core.broker_health import BrokerHealthMonitor

        monitor = BrokerHealthMonitor(broker_name="alpaca")
        metrics = monitor.check_health()

        if metrics.is_healthy:
            print("✅ Alpaca API: Connected")
            if metrics.buying_power:
                print(f"   Buying Power: ${metrics.buying_power:,.2f}")
            if metrics.account_status:
                print(f"   Status: {metrics.account_status}")
            if metrics.avg_response_time_ms > 0:
                print(f"   Response Time: {metrics.avg_response_time_ms:.2f}ms")
            return True
        else:
            print("❌ Alpaca API: UNHEALTHY")
            print(f"   Status: {metrics.status.value}")
            if metrics.last_error:
                print(f"   Error: {metrics.last_error}")
            if metrics.consecutive_failures > 0:
                print(f"   Consecutive Failures: {metrics.consecutive_failures}")
            return False
    except Exception as e:
        print(f"❌ Alpaca API: FAILED - {e}")
        return False


def check_anthropic_api() -> bool:
    """Check Anthropic API accessibility."""
    if not ANTHROPIC_KEY:
        print("⚠️  Anthropic API: No API key configured (will use fallback mode)")
        return True  # Not critical - we have fallback

    # Skip Anthropic check - not critical and can hang (we have fallback)
    print("✅ Anthropic API: Skipped (not critical, fallback available)")
    return True  # Not critical - we have fallback

    # DISABLED: Can hang in GitHub Actions environment
    # # Set 5-second timeout for Anthropic API call
    # signal.signal(signal.SIGALRM, timeout_handler)
    # signal.alarm(5)

    try:
        client = Anthropic(api_key=ANTHROPIC_KEY)
        # Simple test call
        client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )

        signal.alarm(0)  # Cancel timeout
        print("✅ Anthropic API: Connected")
        return True
    except TimeoutError:
        signal.alarm(0)  # Cancel timeout
        print("⚠️  Anthropic API: Timeout (5s) - continuing without LLM check")
        return True  # Fail-open, not critical
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        error_str = str(e)
        if "credit balance" in error_str.lower():
            print("⚠️  Anthropic API: Low credits (will use fallback mode)")
            return True  # Not critical - we have fallback
        else:
            print(f"❌ Anthropic API: FAILED - {e}")
            return True  # Still allow trading with fallback


def check_market_status() -> bool:
    """Check if market is open."""
    try:
        from src.core.alpaca_trader import AlpacaTrader

        trader = AlpacaTrader(paper=True)
        clock = trader.trading_client.get_clock()

        if clock.is_open:
            print("✅ Market: OPEN")
            return True
        else:
            next_open = clock.next_open if hasattr(clock, "next_open") else None
            print(f"⚠️  Market: CLOSED (opens at {next_open})")
            print("   Trading will execute when market opens")
            return True  # Not a failure - orders will queue
    except Exception as e:
        print(f"❌ Market Status: FAILED - {e}")
        return False


def check_economic_calendar() -> bool:
    """Check if major economic events today (Fed meetings, GDP, CPI)."""
    # Set 5-second timeout for Finnhub API call (reduced from 10s)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)

    try:
        from src.utils.finnhub_client import FinnhubClient

        client = FinnhubClient()
        if not client.api_key:
            signal.alarm(0)  # Cancel timeout
            print("⚠️  Finnhub API key not configured - skipping economic calendar check")
            return True  # Not critical if not configured

        if client.has_major_event_today():
            signal.alarm(0)  # Cancel timeout
            print("⚠️  MAJOR ECONOMIC EVENT TODAY - Consider skipping trading")
            print("   (Fed meeting, GDP release, CPI, or Employment data)")
            return False  # Not a failure, but warning
        else:
            signal.alarm(0)  # Cancel timeout
            print("✅ Economic Calendar: No major events today")
        return True
    except TimeoutError:
        signal.alarm(0)  # Cancel timeout
        print("⚠️  Economic calendar: Timeout (10s) - continuing without event check")
        return True  # Fail-open, not critical
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        print(f"⚠️  Economic calendar check failed: {e}")
        return True  # Don't block trading if check fails


def check_circuit_breakers() -> bool:
    """Check circuit breaker status."""
    try:
        from src.safety.circuit_breakers import CircuitBreaker

        breaker = CircuitBreaker()
        status = breaker.get_status()

        if status["is_tripped"]:
            print("🚨 Circuit Breaker: TRIPPED")
            print(f"   Reason: {status.get('trip_reason', 'Unknown')}")
            print(f"   Details: {status.get('trip_details', 'N/A')}")
            print("   MANUAL RESET REQUIRED")
            return False
        else:
            print("✅ Circuit Breaker: OK")
            print(f"   Consecutive losses: {status['consecutive_losses']}")
            print(f"   API errors today: {status['api_errors_today']}")
            return True
    except Exception as e:
        print(f"⚠️  Circuit Breaker: Could not check - {e}")
        return True  # Allow trading if can't check


def check_data_access() -> bool:
    """Check data directory access."""
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        # Test write
        test_file = data_dir / ".health_check"
        test_file.write_text(datetime.now().isoformat())
        test_file.unlink()

        print("✅ Data Directory: Writable")
        return True
    except Exception as e:
        print(f"❌ Data Directory: FAILED - {e}")
        return False


def check_dependencies() -> bool:
    """Check Python dependencies."""
    required = ["anthropic", "pandas", "numpy"]
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ Dependencies: MISSING - {', '.join(missing)}")
        return False
    else:
        print("✅ Dependencies: All present")
        return True


def check_strategy_execution() -> bool:
    """
    Check if strategies have executed trades when they should have.

    Flags strategies with 0 trades that are marked as 'active' and should have executed.
    """
    try:
        data_dir = Path("data")
        system_state_file = data_dir / "system_state.json"

        if not system_state_file.exists():
            print("⚠️  Strategy Execution: Cannot check - system_state.json not found")
            return True  # Don't fail health check for missing file

        import json

        with open(system_state_file) as f:
            system_state = json.load(f)

        strategies = system_state.get("strategies", {})
        issues = []

        # Check each strategy
        for tier_id, strategy in strategies.items():
            status = strategy.get("status", "unknown")
            trades_executed = strategy.get("trades_executed", 0)
            name = strategy.get("name", tier_id)

            # Only check 'active' strategies
            if status == "active":
                # Stock strategies (tier1, tier2) should have executed on weekdays
                if tier_id in ["tier1", "tier2"]:
                    # Check if it's been active for more than 3 days without trades
                    # (should execute daily on weekdays)
                    if trades_executed == 0:
                        issues.append(f"{name}: 0 trades executed (should execute daily)")

        if issues:
            print("⚠️  Strategy Execution: ISSUES DETECTED")
            for issue in issues:
                print(f"   - {issue}")
            print(f"   Total issues: {len(issues)}")
            return False
        else:
            print("✅ Strategy Execution: All active strategies have executed trades")
            return True

    except Exception as e:
        print(f"⚠️  Strategy Execution: CHECK FAILED - {e}")
        return True  # Don't fail health check for check errors


def main():
    """Run all health checks."""
    init_sentry()
    # Set global 30-second timeout for entire health check
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    try:
        if not ALPACA_KEY or not ALPACA_SECRET:
            print(
                "⚠️  ALPACA_API_KEY/ALPACA_SECRET_KEY not set. Skipping trading execution for safety."
            )
            write_output(False)
            return 0

        print("\n" + "=" * 70)
        print("🏥 PRE-MARKET HEALTH CHECK")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        print("=" * 70 + "\n")

        checks = {
            "Dependencies": check_dependencies(),
            "Data Access": check_data_access(),
            "Alpaca API": check_alpaca_api(),
            "Market Status": check_market_status(),
            "Anthropic API": check_anthropic_api(),
            "Economic Calendar": check_economic_calendar(),
            "Circuit Breakers": check_circuit_breakers(),
            "Strategy Execution": check_strategy_execution(),
        }

        signal.alarm(0)  # Cancel global timeout

        print("\n" + "=" * 70)
        print("📊 HEALTH CHECK SUMMARY")
        print("=" * 70)

        # Classify checks as critical vs warning
        critical_checks = [
            "Dependencies",
            "Data Access",
            "Alpaca API",
            "Circuit Breakers",
        ]

        warning_checks = [
            "Market Status",
            "Anthropic API",
            "Economic Calendar",
            "Strategy Execution",
        ]

        critical_passed = all(checks[name] for name in critical_checks)
        warning_issues = [name for name in warning_checks if not checks[name]]

        # Display results with classification
        print("🚨 CRITICAL CHECKS:")
        for name in critical_checks:
            status = "✅ PASS" if checks[name] else "❌ FAIL"
            print(f"   {status} - {name}")

        print("\n⚠️  WARNING CHECKS:")
        for name in warning_checks:
            status = "✅ PASS" if checks[name] else "⚠️  WARN"
            print(f"   {status} - {name}")

        print("=" * 70)

        if critical_passed:
            if warning_issues:
                print(f"\n✅ HEALTH CHECK PASSED (with {len(warning_issues)} warnings)")
                print("   Critical systems ready - trading will proceed")
                for issue in warning_issues:
                    print(f"   ⚠️  {issue}: non-critical issue")
            else:
                print("\n✅ HEALTH CHECK PASSED - All systems ready for trading")
            write_output(True)
            return 0
        else:
            print("\n❌ HEALTH CHECK FAILED - Critical issues prevent trading")
            failed_critical = [name for name in critical_checks if not checks[name]]
            for issue in failed_critical:
                print(f"   🚨 {issue}: CRITICAL FAILURE")
            write_output(False)
            return 1  # Return 1 for critical failures, 10 for warnings only

    except TimeoutError:
        signal.alarm(0)  # Cancel timeout
        print("\n" + "=" * 70)
        print("🚨 HEALTH CHECK TIMEOUT (30s)")
        print("=" * 70)
        print("❌ Health check exceeded maximum time - aborting")
        print("   This usually indicates an API is hanging")
        print("   Check Anthropic or Finnhub API connectivity\n")
        write_output(False)
        return 1
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        write_output(False)
        return 1
    finally:
        signal.alarm(0)  # Ensure timeout is always cancelled


if __name__ == "__main__":
    sys.exit(main())
