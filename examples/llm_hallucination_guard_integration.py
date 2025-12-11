"""
LLM Hallucination Guard Integration Example

Shows how to integrate the hallucination guard into the trading system
to validate LLM outputs before executing trades.

Integration Points:
1. Signal Agent - Validate technical analysis outputs
2. RL Agent - Validate action recommendations
3. Execution Agent - Final validation before trade submission

Author: Trading System
Created: 2025-12-11
"""

import logging
from typing import Any

from src.verification import LLMHallucinationGuard, create_hallucination_guard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Signal Agent Integration
# ============================================================================

def validate_signal_agent_output(signal_output: dict[str, Any]) -> dict[str, Any]:
    """
    Validate signal agent output before passing to RL agent.

    Args:
        signal_output: Raw output from SignalAgent.analyze()

    Returns:
        Validation result with pass/fail and detailed violations
    """
    # Create guard with approved tickers
    guard = create_hallucination_guard(
        valid_tickers=["SPY", "QQQ", "AAPL", "NVDA", "TSLA"],
        max_position_pct=0.10
    )

    # Map signal output to guard's expected format
    output_for_validation = {
        "symbol": signal_output.get("symbol", "UNKNOWN"),
        "action": signal_output.get("action", "HOLD"),
        "confidence": signal_output.get("confidence", 0.5),
        "reasoning": signal_output.get("full_reasoning", ""),
    }

    # Add optional fields if present
    if "sentiment" in signal_output:
        output_for_validation["sentiment"] = signal_output["sentiment"]

    # Validate
    result = guard.validate_output(output_for_validation)

    if not result["valid"]:
        logger.warning(
            "Signal agent output validation FAILED: %d violations, risk score: %.2f",
            len(result["violations"]),
            result["risk_score"]
        )

        # Log critical violations
        critical = [v for v in result["violations"] if v["severity"] == "critical"]
        for violation in critical:
            logger.error(
                "CRITICAL: %s - %s (got: %s, expected: %s)",
                violation["field"],
                violation["message"],
                violation["actual_value"],
                violation["expected_format"]
            )

        # Log prevention steps from RAG
        if result["prevention_steps"]:
            logger.info("Prevention steps from past incidents:")
            for step in result["prevention_steps"]:
                logger.info("  - %s", step)

    return result


# ============================================================================
# Example 2: RL Agent Integration
# ============================================================================

def validate_rl_agent_output(rl_output: dict[str, Any]) -> dict[str, Any]:
    """
    Validate RL agent action recommendation.

    Args:
        rl_output: Output from RLFilter.predict()

    Returns:
        Validation result
    """
    guard = LLMHallucinationGuard(max_position_pct=0.10)

    # Map RL output format
    output_for_validation = {
        "action": rl_output.get("action", "neutral"),
        "confidence": rl_output.get("confidence", 0.5),
    }

    # Add features if present
    if "features" in rl_output:
        features = rl_output["features"]
        if "sentiment" in features:
            output_for_validation["sentiment"] = features["sentiment"]

    result = guard.validate_output(output_for_validation)

    if not result["valid"]:
        logger.warning(
            "RL agent output validation FAILED: %d violations",
            len(result["violations"])
        )

    return result


# ============================================================================
# Example 3: Pre-Trade Validation Pipeline
# ============================================================================

def validate_trade_before_execution(
    symbol: str,
    side: str,
    amount: float,
    confidence: float,
    reasoning: str,
    portfolio_value: float
) -> tuple[bool, str]:
    """
    Final validation gate before submitting trade to Alpaca.

    Args:
        symbol: Ticker symbol
        side: Trade direction (buy/sell)
        amount: Dollar amount
        confidence: Model confidence
        reasoning: Trade reasoning
        portfolio_value: Current portfolio value

    Returns:
        (approved: bool, message: str)
    """
    guard = create_hallucination_guard(
        valid_tickers=["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "IWM", "VTI"],
        max_position_pct=0.10
    )

    trade_output = {
        "symbol": symbol,
        "action": side.upper(),
        "amount": amount,
        "confidence": confidence,
        "reasoning": reasoning,
        "portfolio_value": portfolio_value,
    }

    result = guard.validate_output(trade_output)

    if result["valid"]:
        return True, "✅ Trade validated, ready for execution"

    # Build detailed error message
    critical_violations = [
        v for v in result["violations"]
        if v["severity"] == "critical"
    ]

    if critical_violations:
        errors = [
            f"{v['field']}: {v['message']}"
            for v in critical_violations
        ]
        message = f"❌ Trade BLOCKED: {', '.join(errors)}"
        return False, message

    # Warnings only - allow but log
    warnings = [
        v for v in result["violations"]
        if v["severity"] == "warning"
    ]
    warning_msgs = [f"{v['field']}: {v['message']}" for v in warnings]
    message = f"⚠️  Trade approved with warnings: {', '.join(warning_msgs)}"

    return True, message


# ============================================================================
# Example 4: Batch Validation for Multi-LLM Council
# ============================================================================

def validate_llm_council_votes(votes: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Validate outputs from multiple LLMs in the council.

    Args:
        votes: List of vote dicts from each LLM

    Returns:
        Summary of validation results
    """
    guard = create_hallucination_guard(max_position_pct=0.10)

    results = {
        "total_votes": len(votes),
        "valid_votes": 0,
        "invalid_votes": 0,
        "risk_scores": [],
        "violations_by_model": {},
    }

    for i, vote in enumerate(votes):
        model_name = vote.get("model", f"model_{i}")

        validation = guard.validate_output({
            "symbol": vote.get("symbol", ""),
            "action": vote.get("vote", "HOLD"),
            "confidence": vote.get("confidence", 0.5),
            "reasoning": vote.get("reasoning", ""),
        })

        if validation["valid"]:
            results["valid_votes"] += 1
        else:
            results["invalid_votes"] += 1
            results["violations_by_model"][model_name] = validation["violations"]

        results["risk_scores"].append({
            "model": model_name,
            "risk_score": validation["risk_score"]
        })

    # Calculate summary stats
    if results["risk_scores"]:
        avg_risk = sum(r["risk_score"] for r in results["risk_scores"]) / len(results["risk_scores"])
        results["average_risk_score"] = round(avg_risk, 3)

    logger.info(
        "LLM Council validation: %d/%d votes valid, avg risk: %.3f",
        results["valid_votes"],
        results["total_votes"],
        results.get("average_risk_score", 0)
    )

    return results


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("LLM Hallucination Guard Integration Examples")
    print("=" * 70)
    print()

    # Example 1: Valid signal
    print("1. Valid Signal Agent Output:")
    print("-" * 70)
    valid_signal = {
        "symbol": "SPY",
        "action": "BUY",
        "confidence": 0.68,
        "full_reasoning": "Strong MACD crossover with RSI confirmation and volume support",
        "strength": 8,
    }
    result = validate_signal_agent_output(valid_signal)
    print(f"Valid: {result['valid']}, Risk Score: {result['risk_score']}")
    print()

    # Example 2: Invalid signal (hallucination detected)
    print("2. Invalid Signal Agent Output (Hallucination):")
    print("-" * 70)
    invalid_signal = {
        "symbol": "APPL",  # Typo
        "action": "MAYBE",  # Invalid action
        "confidence": 0.95,  # Exceeds FACTS ceiling
        "full_reasoning": "Buy",  # Too short
    }
    result = validate_signal_agent_output(invalid_signal)
    print(f"Valid: {result['valid']}, Risk Score: {result['risk_score']}")
    print(f"Violations: {len(result['violations'])}")
    for v in result["violations"][:3]:  # Show first 3
        print(f"  - {v['severity'].upper()}: {v['field']} - {v['message']}")
    print()

    # Example 3: Pre-trade validation
    print("3. Pre-Trade Validation:")
    print("-" * 70)
    approved, message = validate_trade_before_execution(
        symbol="SPY",
        side="buy",
        amount=8.50,
        confidence=0.65,
        reasoning="MACD positive, RSI oversold recovery, volume confirms",
        portfolio_value=100000.0
    )
    print(message)
    print()

    # Example 4: Multi-LLM council validation
    print("4. LLM Council Validation:")
    print("-" * 70)
    council_votes = [
        {
            "model": "claude-3.5-sonnet",
            "symbol": "SPY",
            "vote": "BUY",
            "confidence": 0.68,
            "reasoning": "Technical indicators strong"
        },
        {
            "model": "gpt-4o",
            "symbol": "SPY",
            "vote": "BUY",
            "confidence": 0.72,  # Exceeds FACTS ceiling
            "reasoning": "Momentum positive"
        },
        {
            "model": "gemini-pro",
            "symbol": "UNKNOWN",  # Invalid
            "vote": "BUY",
            "confidence": 0.65,
            "reasoning": "Market conditions favorable"
        }
    ]
    council_result = validate_llm_council_votes(council_votes)
    print(f"Valid votes: {council_result['valid_votes']}/{council_result['total_votes']}")
    print(f"Average risk score: {council_result.get('average_risk_score', 0)}")
    print()

    print("=" * 70)
    print("Integration examples complete!")
    print("=" * 70)
