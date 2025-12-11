"""
Pre-Trade Validation Hook

A lightweight hook that MUST be called before any trade executes.
Integrates verification framework, RAG lessons, circuit breakers,
and enhanced volatility-adjusted safety checks.

Enhanced Dec 11, 2025: Added ATR-based limits, drift detection,
hourly heartbeat, and LLM hallucination checks based on Deep Research.

Usage:
    from src.safety.pre_trade_hook import validate_before_trade

    result = validate_before_trade(
        symbol="SPY",
        side="buy",
        amount=10.0,
        portfolio_value=100000.0,
        entry_price=500.0,  # For drift detection
        llm_output={"ticker": "SPY", "side": "buy"}  # For hallucination check
    )

    if not result["approved"]:
        logger.error(f"Trade blocked: {result['reason']}")
        return

    # Proceed with trade...

Author: Trading System
Created: 2025-12-11
Enhanced: 2025-12-11 (ATR limits, drift, heartbeat, hallucination checks)
"""

import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_verifier = None
_rag = None
_circuit_breaker = None
_volatility_safety = None  # Enhanced safety checks (Dec 11, 2025)


def _get_verifier():
    """Lazy load verifier."""
    global _verifier
    if _verifier is None:
        try:
            from src.safety.verification_framework import PreTradeVerifier
            _verifier = PreTradeVerifier()
        except ImportError:
            logger.warning("PreTradeVerifier not available")
    return _verifier


def _get_rag():
    """Lazy load RAG."""
    global _rag
    if _rag is None:
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG
            _rag = LessonsLearnedRAG()
        except ImportError:
            logger.warning("LessonsLearnedRAG not available")
    return _rag


def _get_circuit_breaker():
    """Lazy load circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        try:
            from src.safety.circuit_breakers import CircuitBreaker
            _circuit_breaker = CircuitBreaker()
        except ImportError:
            logger.warning("CircuitBreaker not available")
    return _circuit_breaker


def _get_volatility_safety():
    """Lazy load volatility-adjusted safety checks (Dec 11, 2025 enhancement)."""
    global _volatility_safety
    if _volatility_safety is None:
        try:
            from src.safety import volatility_adjusted_safety
            _volatility_safety = volatility_adjusted_safety
        except ImportError:
            logger.warning("Volatility-adjusted safety module not available")
    return _volatility_safety


def validate_before_trade(
    symbol: str,
    side: str,
    amount: float,
    portfolio_value: float,
    current_pl_today: float = 0.0,
    current_positions: Optional[dict] = None,
    bypass_checks: bool = False,
    entry_price: Optional[float] = None,
    llm_output: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Validate a trade before execution.

    This function MUST be called before any trade executes.
    It runs all safety checks and returns approval status.

    Enhanced Dec 11, 2025: Added ATR-based volatility limits, drift detection,
    hourly loss heartbeat, and LLM hallucination checks.

    Args:
        symbol: Trading symbol
        side: "buy" or "sell"
        amount: Trade amount in dollars
        portfolio_value: Current portfolio value
        current_pl_today: Today's P/L (for circuit breaker)
        current_positions: Current positions dict
        bypass_checks: Set True only in testing (not recommended!)
        entry_price: Current market price (for drift detection)
        llm_output: LLM output dict (for hallucination check)

    Returns:
        Dict with:
        - approved: bool - Whether trade should proceed
        - reason: str - Reason if not approved
        - warnings: list - Non-blocking warnings
        - context: dict - RAG context for the trade
        - enhanced_checks: dict - Results from volatility-adjusted safety checks
    """
    if bypass_checks:
        logger.warning("⚠️ Pre-trade checks BYPASSED - not recommended!")
        return {
            "approved": True,
            "reason": "Checks bypassed",
            "warnings": ["Safety checks were bypassed"],
            "context": {},
        }

    result = {
        "approved": True,
        "reason": "All checks passed",
        "warnings": [],
        "context": {},
        "checks_run": [],
    }

    # 1. Circuit Breaker Check
    cb = _get_circuit_breaker()
    if cb:
        cb_result = cb.check_before_trade(
            portfolio_value=portfolio_value,
            proposed_position_size=amount,
            current_pl_today=current_pl_today,
        )
        result["checks_run"].append("circuit_breaker")

        if not cb_result["allowed"]:
            return {
                "approved": False,
                "reason": cb_result["reason"],
                "warnings": [],
                "context": {"circuit_breaker": cb_result},
                "checks_run": result["checks_run"],
            }

    # 2. Verification Framework
    verifier = _get_verifier()
    if verifier:
        verification = verifier.verify_trade(
            symbol=symbol,
            side=side,
            amount=amount,
            portfolio_value=portfolio_value,
            current_positions=current_positions,
        )
        result["checks_run"].append("verification_framework")

        if verification.blocked:
            return {
                "approved": False,
                "reason": verification.block_reason or "Verification failed",
                "warnings": [],
                "context": {"verification": verification.to_dict()},
                "checks_run": result["checks_run"],
            }

        # Add non-blocking warnings
        for check in verification.checks:
            if not check.passed or check.severity in ["WARNING", "ERROR"]:
                result["warnings"].append(f"[{check.check_name}] {check.message}")

    # 3. RAG Lessons Context
    rag = _get_rag()
    if rag:
        context = rag.get_context_for_trade(symbol, side, amount)
        result["context"] = context
        result["checks_run"].append("rag_lessons")

        # Add RAG warnings
        for warning in context.get("warnings", []):
            if warning.get("severity") in ["high", "critical"]:
                result["warnings"].append(
                    f"[RAG] {warning['title']}: {warning['prevention']}"
                )

    # 4. Final size sanity check (critical safety net)
    HARD_MAX_TRADE = 50000  # $50k absolute max per trade
    if amount > HARD_MAX_TRADE:
        return {
            "approved": False,
            "reason": f"Trade ${amount:.2f} exceeds hard max ${HARD_MAX_TRADE}",
            "warnings": result["warnings"],
            "context": result["context"],
            "checks_run": result["checks_run"],
        }

    # 5. Enhanced volatility-adjusted safety checks (Dec 11, 2025)
    vol_safety = _get_volatility_safety()
    if vol_safety and entry_price is not None:
        try:
            enhanced_results = vol_safety.run_all_safety_checks(
                symbol=symbol,
                entry_price=entry_price,
                notional=amount,
                account_equity=portfolio_value,
                llm_output=llm_output,
            )
            result["enhanced_checks"] = enhanced_results["checks"]
            result["checks_run"].append("volatility_adjusted_safety")

            if not enhanced_results["approved"]:
                return {
                    "approved": False,
                    "reason": "; ".join(enhanced_results["errors"]),
                    "warnings": result["warnings"] + enhanced_results["warnings"],
                    "context": result["context"],
                    "checks_run": result["checks_run"],
                    "enhanced_checks": enhanced_results["checks"],
                }

            # Add non-blocking warnings
            result["warnings"].extend(enhanced_results["warnings"])

        except Exception as e:
            logger.warning(f"Enhanced safety checks failed (non-blocking): {e}")
            result["warnings"].append(f"Enhanced safety checks unavailable: {e}")

    # Log result
    if result["approved"]:
        if result["warnings"]:
            logger.warning(
                f"Trade approved with {len(result['warnings'])} warnings: "
                f"{symbol} {side} ${amount:.2f}"
            )
        else:
            logger.info(f"Trade approved: {symbol} {side} ${amount:.2f}")
    else:
        logger.error(f"Trade BLOCKED: {symbol} {side} ${amount:.2f} - {result['reason']}")

    return result


def quick_validate(
    amount: float,
    daily_budget: float = 10.0,
) -> tuple[bool, str]:
    """
    Quick validation for simple checks.

    Args:
        amount: Trade amount
        daily_budget: Expected daily budget

    Returns:
        Tuple of (is_valid, reason)
    """
    # Check for obvious bugs
    if amount > daily_budget * 100:
        return False, f"Amount ${amount:.2f} is {amount/daily_budget:.0f}x daily budget - likely bug"

    if amount < 0:
        return False, "Amount cannot be negative"

    if amount > 50000:
        return False, f"Amount ${amount:.2f} exceeds $50k safety limit"

    return True, "OK"


def record_signal_price(symbol: str, price: float) -> None:
    """
    Record the signal price for drift detection.

    Call this when a trading decision is made, BEFORE execution.
    This enables the drift detector to compare signal price vs entry price.

    Args:
        symbol: Trading symbol
        price: Price at time of signal
    """
    vol_safety = _get_volatility_safety()
    if vol_safety:
        try:
            drift_detector = vol_safety.get_drift_detector()
            drift_detector.record_signal(symbol, price)
            logger.debug(f"Signal recorded for {symbol} at ${price:.2f}")
        except Exception as e:
            logger.warning(f"Could not record signal price: {e}")


def record_trade_result_for_heartbeat(symbol: str, profit_loss: float) -> dict:
    """
    Record trade result for hourly heartbeat tracking.

    Call this AFTER every trade completes to update the hourly loss tracker.

    Args:
        symbol: Trading symbol
        profit_loss: Profit (+) or loss (-) from the trade

    Returns:
        Heartbeat status dict
    """
    vol_safety = _get_volatility_safety()
    if vol_safety:
        try:
            heartbeat = vol_safety.get_hourly_heartbeat()
            status = heartbeat.record_trade_result(symbol, profit_loss)
            return {
                "hourly_loss": status.current_hourly_loss,
                "hourly_limit": status.hourly_limit,
                "is_blocked": status.is_blocked,
                "reason": status.reason,
            }
        except Exception as e:
            logger.warning(f"Could not record trade result for heartbeat: {e}")
    return {"is_blocked": False, "reason": "Heartbeat unavailable"}


def log_trade_for_learning(
    symbol: str,
    side: str,
    amount: float,
    expected_amount: float,
    result: str,
    error: Optional[str] = None,
) -> None:
    """
    Log trade for ML learning and anomaly detection.

    Call this after every trade (successful or not) to feed
    the ML pipeline with new data.

    Args:
        symbol: Trading symbol
        side: "buy" or "sell"
        amount: Actual trade amount
        expected_amount: Expected amount
        result: "success", "failed", "blocked"
        error: Error message if failed
    """
    rag = _get_rag()

    # Detect anomaly
    if expected_amount > 0 and amount > expected_amount * 5:
        # Size anomaly detected - add lesson
        if rag:
            from src.rag.lessons_learned_rag import ingest_trade_anomaly
            ingest_trade_anomaly(
                rag=rag,
                anomaly_type="size_discrepancy",
                description=f"Trade executed at ${amount:.2f} vs expected ${expected_amount:.2f}",
                root_cause="Size calculation error or unit confusion",
                symbol=symbol,
                financial_impact=abs(amount - expected_amount),
            )
        logger.error(f"SIZE ANOMALY: {symbol} actual=${amount:.2f} expected=${expected_amount:.2f}")

    # Log for ML training data
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "expected_amount": expected_amount,
        "result": result,
        "error": error,
        "anomaly": amount > expected_amount * 2 if expected_amount > 0 else False,
    }

    logger.info(f"Trade logged: {log_entry}")


# Convenience decorators
def require_validation(func):
    """
    Decorator that requires pre-trade validation.

    Usage:
        @require_validation
        def execute_trade(symbol, side, amount, portfolio_value, **kwargs):
            # Trade logic here
            pass
    """
    def wrapper(symbol: str, side: str, amount: float, portfolio_value: float, **kwargs):
        # Validate first
        validation = validate_before_trade(
            symbol=symbol,
            side=side,
            amount=amount,
            portfolio_value=portfolio_value,
            current_positions=kwargs.get("current_positions"),
        )

        if not validation["approved"]:
            raise ValueError(f"Trade blocked: {validation['reason']}")

        # Proceed with trade
        return func(symbol, side, amount, portfolio_value, **kwargs)

    return wrapper


if __name__ == "__main__":
    """Demo the pre-trade hook."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("PRE-TRADE VALIDATION HOOK DEMO")
    print("=" * 80)

    # Test scenarios
    tests = [
        {"symbol": "SPY", "side": "buy", "amount": 10.0, "portfolio": 100000},
        {"symbol": "SPY", "side": "buy", "amount": 1600.0, "portfolio": 100000},  # Suspicious
        {"symbol": "SPY", "side": "buy", "amount": 100000.0, "portfolio": 100000},  # Way too big
    ]

    for test in tests:
        print(f"\n{'-'*60}")
        print(f"Testing: {test['symbol']} {test['side']} ${test['amount']:.2f}")

        result = validate_before_trade(
            symbol=test["symbol"],
            side=test["side"],
            amount=test["amount"],
            portfolio_value=test["portfolio"],
        )

        status = "✅ APPROVED" if result["approved"] else "🚫 BLOCKED"
        print(f"Result: {status}")

        if not result["approved"]:
            print(f"Reason: {result['reason']}")

        if result["warnings"]:
            print("Warnings:")
            for w in result["warnings"]:
                print(f"  ⚠️ {w}")

    # Quick validate test
    print(f"\n{'='*80}")
    print("QUICK VALIDATE TEST")
    print("=" * 80)

    for amount in [8, 100, 2000, 60000]:
        valid, reason = quick_validate(amount, daily_budget=10.0)
        status = "✅" if valid else "❌"
        print(f"  ${amount}: {status} {reason}")
