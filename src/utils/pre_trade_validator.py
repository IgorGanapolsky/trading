#!/usr/bin/env python3
"""
Pre-Trade Validator - MANDATORY before ANY trade execution.

Created: Jan 22, 2026 after LL-282 CTO Failure Crisis
Purpose: Enforce Phil Town Rule #1 - Don't Lose Money

This validator MUST be called before any trade. It:
1. Queries RAG for relevant lessons
2. Validates against SPY-ONLY mandate
3. Checks position balance requirements
4. Verifies risk limits
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PreTradeValidationError(Exception):
    """Raised when pre-trade validation fails."""
    pass


class PreTradeValidator:
    """
    MANDATORY pre-trade validation.

    Usage:
        validator = PreTradeValidator()
        validator.validate(symbol="SPY", strategy="iron_condor", quantity=1)
    """

    # From LL-203: These are the ONLY allowed tickers
    ALLOWED_TICKERS = {"SPY"}  # Removed IWM per CLAUDE.md - SPY ONLY

    # From CLAUDE.md: Maximum position size
    MAX_POSITION_PCT = 0.05  # 5% max per trade

    # From LL-277: Required win rate for strategy
    MIN_WIN_RATE = 0.80  # 80% minimum

    def __init__(self, account_value: float = 5000.0):
        self.account_value = account_value
        self.max_risk = account_value * self.MAX_POSITION_PCT

    def validate(
        self,
        symbol: str,
        strategy: str,
        quantity: int,
        risk_amount: float,
        long_legs: int = 0,
        short_legs: int = 0,
    ) -> bool:
        """
        Validate a trade BEFORE execution.

        Raises PreTradeValidationError if ANY check fails.
        Returns True only if ALL checks pass.
        """
        errors = []

        # Check 1: SPY-ONLY mandate (from CLAUDE.md, LL-203, LL-247)
        base_symbol = symbol.split("2")[0] if "2" in symbol else symbol  # Extract base from options
        if base_symbol not in self.ALLOWED_TICKERS:
            errors.append(
                f"BLOCKED: {symbol} violates SPY-ONLY mandate. "
                f"LL-247 documents SOFI disaster. LL-203 shows SPY works."
            )

        # Check 2: Position size limit (from CLAUDE.md)
        if risk_amount > self.max_risk:
            errors.append(
                f"BLOCKED: Risk ${risk_amount:.2f} exceeds 5% limit (${self.max_risk:.2f}). "
                f"Phil Town Rule #1: Don't lose money."
            )

        # Check 3: Position balance for spreads/condors (from LL-278)
        if strategy in ["iron_condor", "credit_spread", "put_spread", "call_spread"]:
            if long_legs != short_legs:
                errors.append(
                    f"BLOCKED: Position imbalance. Long legs: {long_legs}, Short legs: {short_legs}. "
                    f"LL-278 documents orphan position crisis. Must be equal."
                )

        # Check 4: Strategy must be defined risk (from LL-203)
        allowed_strategies = ["iron_condor", "credit_spread", "put_spread", "call_spread"]
        if strategy not in allowed_strategies:
            errors.append(
                f"BLOCKED: Strategy '{strategy}' not allowed. "
                f"LL-203: Use defined risk strategies only (iron condors, spreads)."
            )

        # If any errors, raise exception
        if errors:
            error_msg = "\n".join(errors)
            logger.error(f"PRE-TRADE VALIDATION FAILED:\n{error_msg}")
            raise PreTradeValidationError(error_msg)

        # All checks passed
        logger.info(f"PRE-TRADE VALIDATION PASSED: {symbol} {strategy} x{quantity}")
        return True

    def get_rag_advice(self, symbol: str, strategy: str) -> str:
        """
        Query RAG for relevant lessons before trading.

        This should be called at session start, not per-trade.
        """
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG
            rag = LessonsLearnedRAG()
            results = rag.search(f"{symbol} {strategy} lessons", top_k=3)

            advice = ["=== RAG ADVICE FOR THIS TRADE ==="]
            for lesson, score in results:
                advice.append(f"- {lesson.title}: {lesson.snippet[:200]}...")

            return "\n".join(advice)
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return "RAG unavailable - proceed with caution"


def validate_trade(
    symbol: str,
    strategy: str,
    quantity: int = 1,
    risk_amount: float = 0,
    long_legs: int = 0,
    short_legs: int = 0,
    account_value: float = 5000.0,
) -> bool:
    """
    Convenience function for pre-trade validation.

    Usage:
        from src.utils.pre_trade_validator import validate_trade
        validate_trade("SPY", "iron_condor", quantity=1, risk_amount=200, long_legs=2, short_legs=2)
    """
    validator = PreTradeValidator(account_value=account_value)
    return validator.validate(
        symbol=symbol,
        strategy=strategy,
        quantity=quantity,
        risk_amount=risk_amount,
        long_legs=long_legs,
        short_legs=short_legs,
    )


if __name__ == "__main__":
    # Test the validator
    validator = PreTradeValidator(account_value=5000)

    print("Test 1: Valid SPY iron condor")
    try:
        validator.validate("SPY", "iron_condor", 1, 200, long_legs=2, short_legs=2)
        print("✅ PASSED\n")
    except PreTradeValidationError as e:
        print(f"❌ FAILED: {e}\n")

    print("Test 2: Invalid SOFI trade (should fail)")
    try:
        validator.validate("SOFI", "credit_spread", 1, 200, long_legs=1, short_legs=1)
        print("❌ Should have failed!\n")
    except PreTradeValidationError as e:
        print(f"✅ Correctly blocked: {e}\n")

    print("Test 3: Position imbalance (should fail)")
    try:
        validator.validate("SPY", "iron_condor", 1, 200, long_legs=6, short_legs=4)
        print("❌ Should have failed!\n")
    except PreTradeValidationError as e:
        print(f"✅ Correctly blocked: {e}\n")

    print("Test 4: Excessive risk (should fail)")
    try:
        validator.validate("SPY", "iron_condor", 1, 500, long_legs=2, short_legs=2)
        print("❌ Should have failed!\n")
    except PreTradeValidationError as e:
        print(f"✅ Correctly blocked: {e}\n")
