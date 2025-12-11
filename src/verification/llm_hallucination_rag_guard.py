"""LLM Hallucination Guard with RAG Validation.

Detects when LLM outputs invalid trades, validates against past hallucination patterns.
Uses regex validation + RAG similarity search for known hallucination types.

This guard focuses on immediate structural validation before trade execution,
complementing the HallucinationPreventionPipeline which tracks predictions over time.

Key Features:
1. Regex-based field validation (tickers, amounts, sentiments)
2. Type safety checks (NaN, null, infinity detection)
3. Range validation (sentiment, confidence, position size)
4. RAG integration for similar past hallucinations
5. Actionable prevention steps from lessons learned

Author: Trading System
Created: 2025-12-11
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Validation patterns
TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")
SIDE_PATTERN = re.compile(r"^(buy|sell|long|short|hold|neutral)$", re.IGNORECASE)
ACTION_PATTERN = re.compile(r"^(BUY|SELL|HOLD)$", re.IGNORECASE)

# Known invalid values that LLMs sometimes hallucinate
INVALID_STRINGS = {
    "nan", "null", "undefined", "none", "infinity", "inf", "-inf",
    "n/a", "unknown", "error", "invalid", "missing"
}


@dataclass
class Violation:
    """A validation violation."""

    field: str
    severity: str  # "critical", "warning", "info"
    message: str
    actual_value: Any
    expected_format: str


@dataclass
class HallucinationType:
    """A type of hallucination with examples."""

    type_id: str
    description: str
    detection_pattern: str
    examples: list[str] = field(default_factory=list)
    frequency: int = 0
    prevention_steps: list[str] = field(default_factory=list)


class LLMHallucinationGuard:
    """
    Validates LLM outputs against known hallucination patterns.

    Validation Stages:
    1. Type Safety - Check for NaN, null, infinity
    2. Format Validation - Regex matching for tickers, sides
    3. Range Validation - Check bounds (sentiment, confidence, amounts)
    4. Business Logic - Position sizing, portfolio constraints
    5. RAG Lookup - Query for similar past hallucinations

    Integration Points:
    - Pre-trade verification pipeline
    - Signal agent output validation
    - RL agent output validation
    - Execution agent input validation
    """

    def __init__(
        self,
        valid_tickers: Optional[list[str]] = None,
        max_position_pct: float = 0.10,
        rag_system: Optional[Any] = None,
    ):
        """
        Initialize the hallucination guard.

        Args:
            valid_tickers: List of valid ticker symbols (None = allow all matching regex)
            max_position_pct: Maximum position size as % of portfolio
            rag_system: LessonsLearnedRAG instance for pattern lookup
        """
        self.valid_tickers = set(valid_tickers) if valid_tickers else None
        self.max_position_pct = max_position_pct
        self.rag_system = rag_system

        # Load or initialize hallucination patterns
        self.patterns: dict[str, HallucinationType] = {}
        self._init_default_patterns()

        logger.info(
            "LLMHallucinationGuard initialized (max_position=%.1f%%, rag=%s)",
            max_position_pct * 100,
            "enabled" if rag_system else "disabled"
        )

    def validate_output(self, llm_output: dict[str, Any]) -> dict[str, Any]:
        """
        Validate LLM output against all hallucination patterns.

        Args:
            llm_output: Raw LLM output dict with fields like:
                - symbol: Ticker symbol
                - action/side: Trade direction
                - amount: Dollar amount or shares
                - confidence: Model confidence [0-1]
                - sentiment: Market sentiment [-1, 1]
                - reasoning: LLM's explanation

        Returns:
            {
                "valid": bool,
                "violations": List[Violation],
                "similar_hallucinations": List[Dict],
                "prevention_steps": List[str],
                "risk_score": float (0-1, higher = more risky)
            }
        """
        violations: list[Violation] = []

        # Stage 1: Type Safety
        violations.extend(self._check_type_safety(llm_output))

        # Stage 2: Format Validation
        violations.extend(self._check_formats(llm_output))

        # Stage 3: Range Validation
        violations.extend(self._check_ranges(llm_output))

        # Stage 4: Business Logic
        violations.extend(self._check_business_logic(llm_output))

        # Stage 5: RAG Lookup for similar hallucinations
        similar_hallucinations = []
        prevention_steps = []

        if self.rag_system and violations:
            similar_hallucinations, prevention_steps = self._query_rag_for_patterns(
                llm_output, violations
            )

        # Calculate risk score based on violations
        risk_score = self._calculate_risk_score(violations)

        # Determine if valid (no critical violations)
        critical_violations = [v for v in violations if v.severity == "critical"]
        is_valid = len(critical_violations) == 0

        return {
            "valid": is_valid,
            "violations": [self._violation_to_dict(v) for v in violations],
            "similar_hallucinations": similar_hallucinations,
            "prevention_steps": prevention_steps,
            "risk_score": risk_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_hallucination_patterns(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Check output against known hallucination patterns.

        Args:
            output: LLM output to check

        Returns:
            List of matched patterns with metadata
        """
        matches = []

        # Check each known pattern
        for pattern in self.patterns.values():
            if self._matches_hallucination_pattern(output, pattern):
                matches.append({
                    "type_id": pattern.type_id,
                    "description": pattern.description,
                    "frequency": pattern.frequency,
                    "prevention_steps": pattern.prevention_steps,
                })

        return matches

    # =========================================================================
    # Validation Stages
    # =========================================================================

    def _check_type_safety(self, output: dict[str, Any]) -> list[Violation]:
        """Check for NaN, null, infinity, and other invalid types."""
        violations = []

        for key, value in output.items():
            # Check for None/null
            if value is None:
                violations.append(Violation(
                    field=key,
                    severity="critical",
                    message=f"Field '{key}' is None/null",
                    actual_value=value,
                    expected_format="non-null value"
                ))
                continue

            # Check for NaN/infinity in numeric fields
            if isinstance(value, float):
                if math.isnan(value):
                    violations.append(Violation(
                        field=key,
                        severity="critical",
                        message=f"Field '{key}' is NaN",
                        actual_value=value,
                        expected_format="valid number"
                    ))
                elif math.isinf(value):
                    violations.append(Violation(
                        field=key,
                        severity="critical",
                        message=f"Field '{key}' is infinity",
                        actual_value=value,
                        expected_format="finite number"
                    ))

            # Check for invalid string values
            if isinstance(value, str):
                if value.lower().strip() in INVALID_STRINGS:
                    violations.append(Violation(
                        field=key,
                        severity="critical",
                        message=f"Field '{key}' contains invalid string: '{value}'",
                        actual_value=value,
                        expected_format="valid string (not NaN/null/undefined)"
                    ))

        return violations

    def _check_formats(self, output: dict[str, Any]) -> list[Violation]:
        """Check format using regex patterns."""
        violations = []

        # Ticker validation
        if "symbol" in output:
            symbol = str(output["symbol"]).strip().upper()
            if not TICKER_PATTERN.match(symbol):
                violations.append(Violation(
                    field="symbol",
                    severity="critical",
                    message=f"Invalid ticker format: '{symbol}'",
                    actual_value=symbol,
                    expected_format="1-5 uppercase letters (e.g., AAPL, SPY)"
                ))
            elif self.valid_tickers and symbol not in self.valid_tickers:
                violations.append(Violation(
                    field="symbol",
                    severity="warning",
                    message=f"Ticker '{symbol}' not in approved list",
                    actual_value=symbol,
                    expected_format=f"one of: {', '.join(sorted(self.valid_tickers)[:10])}"
                ))

        # Side/Action validation
        for field_name in ["side", "action", "recommendation"]:
            if field_name in output:
                value = str(output[field_name]).strip()
                pattern = ACTION_PATTERN if field_name == "action" else SIDE_PATTERN
                if not pattern.match(value):
                    violations.append(Violation(
                        field=field_name,
                        severity="critical",
                        message=f"Invalid {field_name}: '{value}'",
                        actual_value=value,
                        expected_format="buy/sell/hold or long/short/neutral"
                    ))

        return violations

    def _check_ranges(self, output: dict[str, Any]) -> list[Violation]:
        """Check numeric ranges."""
        violations = []

        # Sentiment must be in [-1, 1]
        if "sentiment" in output:
            try:
                sentiment = float(output["sentiment"])
                if not -1.0 <= sentiment <= 1.0:
                    violations.append(Violation(
                        field="sentiment",
                        severity="critical",
                        message=f"Sentiment out of range: {sentiment}",
                        actual_value=sentiment,
                        expected_format="[-1.0, 1.0]"
                    ))
            except (TypeError, ValueError):
                violations.append(Violation(
                    field="sentiment",
                    severity="critical",
                    message=f"Sentiment not a number: {output['sentiment']}",
                    actual_value=output["sentiment"],
                    expected_format="float in [-1.0, 1.0]"
                ))

        # Confidence must be in [0, 1]
        if "confidence" in output:
            try:
                confidence = float(output["confidence"])
                if not 0.0 <= confidence <= 1.0:
                    violations.append(Violation(
                        field="confidence",
                        severity="critical",
                        message=f"Confidence out of range: {confidence}",
                        actual_value=confidence,
                        expected_format="[0.0, 1.0]"
                    ))
                # FACTS Benchmark: No model >70% factuality
                elif confidence > 0.70:
                    violations.append(Violation(
                        field="confidence",
                        severity="warning",
                        message=f"Confidence {confidence:.2f} exceeds FACTS ceiling (0.70)",
                        actual_value=confidence,
                        expected_format="[0.0, 0.70] per FACTS Benchmark"
                    ))
            except (TypeError, ValueError):
                violations.append(Violation(
                    field="confidence",
                    severity="critical",
                    message=f"Confidence not a number: {output['confidence']}",
                    actual_value=output["confidence"],
                    expected_format="float in [0.0, 1.0]"
                ))

        # Amount must be positive
        if "amount" in output:
            try:
                amount = float(output["amount"])
                if amount < 0:
                    violations.append(Violation(
                        field="amount",
                        severity="critical",
                        message=f"Negative amount: ${amount}",
                        actual_value=amount,
                        expected_format="positive number"
                    ))
                elif amount == 0:
                    violations.append(Violation(
                        field="amount",
                        severity="warning",
                        message="Amount is zero",
                        actual_value=amount,
                        expected_format="positive number"
                    ))
            except (TypeError, ValueError):
                violations.append(Violation(
                    field="amount",
                    severity="critical",
                    message=f"Amount not a number: {output['amount']}",
                    actual_value=output["amount"],
                    expected_format="positive float"
                ))

        return violations

    def _check_business_logic(self, output: dict[str, Any]) -> list[Violation]:
        """Check business logic constraints."""
        violations = []

        # Position sizing check (if portfolio_value provided)
        if "amount" in output and "portfolio_value" in output:
            try:
                amount = float(output["amount"])
                portfolio = float(output["portfolio_value"])

                if portfolio > 0:
                    position_pct = amount / portfolio
                    if position_pct > self.max_position_pct:
                        violations.append(Violation(
                            field="amount",
                            severity="critical",
                            message=f"Position size {position_pct:.1%} exceeds max {self.max_position_pct:.1%}",
                            actual_value=amount,
                            expected_format=f"<= ${portfolio * self.max_position_pct:.2f}"
                        ))
            except (TypeError, ValueError) as e:
                logger.warning(f"Could not validate position size: {e}")

        # Reasoning must not be empty
        if "reasoning" in output:
            reasoning = str(output["reasoning"]).strip()
            if not reasoning or len(reasoning) < 10:
                violations.append(Violation(
                    field="reasoning",
                    severity="warning",
                    message="Reasoning too short or empty",
                    actual_value=reasoning,
                    expected_format="detailed explanation (>10 chars)"
                ))

        return violations

    # =========================================================================
    # RAG Integration
    # =========================================================================

    def _query_rag_for_patterns(
        self,
        output: dict[str, Any],
        violations: list[Violation]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Query RAG for similar past hallucinations.

        Returns:
            (similar_hallucinations, prevention_steps)
        """
        similar = []
        prevention_steps = set()

        if not self.rag_system:
            return [], []

        try:
            # Build query from violations
            violation_types = [v.field for v in violations if v.severity == "critical"]

            for vtype in violation_types:
                query = f"LLM hallucination {vtype} invalid"

                # Search RAG
                results = self.rag_system.search(query, top_k=3)

                for lesson, score in results:
                    if score > 0.5:  # Relevance threshold
                        similar.append({
                            "id": lesson.id,
                            "title": lesson.title,
                            "description": lesson.description,
                            "prevention": lesson.prevention,
                            "severity": lesson.severity,
                            "relevance": round(score, 3),
                        })

                        # Extract prevention steps
                        if lesson.prevention:
                            prevention_steps.add(lesson.prevention)

        except Exception as e:
            logger.warning(f"RAG query failed: {e}")

        return similar, list(prevention_steps)

    def _matches_hallucination_pattern(
        self,
        output: dict[str, Any],
        pattern: HallucinationType
    ) -> bool:
        """Check if output matches a known hallucination pattern."""
        # Simple keyword matching for now
        # Could be enhanced with regex or ML classifier

        output_str = json.dumps(output).lower()

        if pattern.detection_pattern.lower() in output_str:
            pattern.frequency += 1
            return True

        return False

    # =========================================================================
    # Pattern Management
    # =========================================================================

    def _init_default_patterns(self) -> None:
        """Initialize default hallucination patterns."""
        default_patterns = [
            HallucinationType(
                type_id="invalid_ticker",
                description="LLM generates invalid ticker symbols",
                detection_pattern="symbol",
                examples=["APPL (typo for AAPL)", "MSFT123", "sp500"],
                prevention_steps=[
                    "Validate ticker with regex ^[A-Z]{1,5}$",
                    "Cross-check against approved ticker list",
                    "Query Alpaca API for ticker validation"
                ]
            ),
            HallucinationType(
                type_id="confidence_overestimation",
                description="LLM claims >70% confidence (exceeds FACTS benchmark)",
                detection_pattern="confidence",
                examples=["0.95", "0.85", "0.99"],
                prevention_steps=[
                    "Cap confidence at model's FACTS score (~0.68)",
                    "Warn when confidence >0.70",
                    "Require additional validation for high-confidence claims"
                ]
            ),
            HallucinationType(
                type_id="nan_values",
                description="LLM outputs NaN, null, or undefined",
                detection_pattern="nan",
                examples=["NaN", "null", "undefined", "None"],
                prevention_steps=[
                    "Check all numeric fields with math.isnan()",
                    "Reject any None/null values",
                    "Add type hints and validation decorators"
                ]
            ),
            HallucinationType(
                type_id="negative_amounts",
                description="LLM suggests negative trade amounts",
                detection_pattern="amount",
                examples=["-100", "-5.50"],
                prevention_steps=[
                    "Validate amount > 0",
                    "Check for sign errors in LLM reasoning",
                    "Use absolute values if direction is separate"
                ]
            ),
            HallucinationType(
                type_id="sentiment_out_of_range",
                description="LLM provides sentiment outside [-1, 1]",
                detection_pattern="sentiment",
                examples=["1.5", "-2.0", "5"],
                prevention_steps=[
                    "Clamp sentiment to [-1.0, 1.0]",
                    "Validate with regex or range check",
                    "Normalize before using in calculations"
                ]
            ),
            HallucinationType(
                type_id="fabricated_prices",
                description="LLM invents specific price levels without data",
                detection_pattern="price",
                examples=["exactly $500.00", "precisely $1234.56"],
                prevention_steps=[
                    "Always fetch real-time price from Alpaca API",
                    "Never trust LLM price claims",
                    "Flag keywords: 'exactly', 'precisely' in price context"
                ]
            ),
        ]

        for pattern in default_patterns:
            self.patterns[pattern.type_id] = pattern

    # =========================================================================
    # Utilities
    # =========================================================================

    def _calculate_risk_score(self, violations: list[Violation]) -> float:
        """
        Calculate risk score from violations.

        Returns:
            Risk score in [0, 1], higher = more risky
        """
        if not violations:
            return 0.0

        # Weight by severity
        severity_weights = {
            "critical": 0.4,
            "warning": 0.2,
            "info": 0.1,
        }

        total_risk = sum(
            severity_weights.get(v.severity, 0.1)
            for v in violations
        )

        # Cap at 1.0
        return min(1.0, total_risk)

    def _violation_to_dict(self, violation: Violation) -> dict[str, Any]:
        """Convert Violation to dict for serialization."""
        return {
            "field": violation.field,
            "severity": violation.severity,
            "message": violation.message,
            "actual_value": str(violation.actual_value),
            "expected_format": violation.expected_format,
        }

    def get_pattern_summary(self) -> dict[str, Any]:
        """Get summary of known hallucination patterns."""
        return {
            "total_patterns": len(self.patterns),
            "patterns": [
                {
                    "type_id": p.type_id,
                    "description": p.description,
                    "frequency": p.frequency,
                    "prevention_steps": len(p.prevention_steps),
                }
                for p in self.patterns.values()
            ]
        }


def create_hallucination_guard(
    valid_tickers: Optional[list[str]] = None,
    max_position_pct: float = 0.10,
) -> LLMHallucinationGuard:
    """
    Create a hallucination guard with RAG integration.

    Args:
        valid_tickers: List of approved ticker symbols
        max_position_pct: Maximum position size as % of portfolio

    Returns:
        Configured LLMHallucinationGuard instance
    """
    rag_system = None

    # Try to load RAG system
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG
        rag_system = LessonsLearnedRAG()
        logger.info("RAG system loaded for hallucination guard")
    except Exception as e:
        logger.warning(f"Could not load RAG system: {e}")

    return LLMHallucinationGuard(
        valid_tickers=valid_tickers,
        max_position_pct=max_position_pct,
        rag_system=rag_system,
    )


if __name__ == "__main__":
    # Example usage
    guard = create_hallucination_guard(
        valid_tickers=["SPY", "QQQ", "AAPL", "NVDA"],
        max_position_pct=0.10
    )

    # Test valid output
    valid_output = {
        "symbol": "SPY",
        "action": "BUY",
        "amount": 10.0,
        "confidence": 0.65,
        "sentiment": 0.3,
        "reasoning": "Strong uptrend with MACD crossover and volume confirmation",
        "portfolio_value": 100000.0
    }

    result = guard.validate_output(valid_output)
    print("Valid output test:")
    print(json.dumps(result, indent=2))
    print()

    # Test invalid output (multiple violations)
    invalid_output = {
        "symbol": "APPL",  # Typo
        "action": "MAYBE",  # Invalid action
        "amount": -5.0,  # Negative
        "confidence": 0.95,  # Exceeds FACTS ceiling
        "sentiment": 2.5,  # Out of range
        "reasoning": "Buy",  # Too short
        "portfolio_value": 100000.0
    }

    result = guard.validate_output(invalid_output)
    print("Invalid output test:")
    print(json.dumps(result, indent=2))
    print()

    # Pattern summary
    print("Pattern summary:")
    print(json.dumps(guard.get_pattern_summary(), indent=2))
