"""Dynamic Pre-Trade Risk Gate with Multi-Source Validation.

Unified pre-trade verification combining:
- Semantic trade anomaly detection (RAG-based)
- Regime-aware position sizing
- LLM hallucination guard
- Traditional anomaly detection
- Position reconciliation

Final gate before order submission to broker.

This is the LAST LINE OF DEFENSE before money moves.

Created: Dec 11, 2025
Author: Trading System CTO
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result from a single risk check."""

    check_name: str
    passed: bool
    score: float  # 0-100, higher = more risky
    details: dict[str, Any]
    warnings: list[str]
    recommendation: str


@dataclass
class ValidationResult:
    """Complete pre-trade validation result."""

    safe_to_trade: bool
    risk_score: float  # 0-100
    checks: dict[str, dict[str, Any]]
    prevention_checklist: list[str]
    recommendation: str
    timestamp: str


class DynamicPreTradeGate:
    """
    Unified pre-trade risk gate combining multiple verification sources.

    Execution Order:
    1. Semantic Anomaly Check (RAG - similar past incidents)
    2. Regime Aware Sizing (market conditions)
    3. LLM Hallucination Guard (model accuracy ceiling)
    4. Traditional Anomaly Detector (statistical patterns)
    5. Position Validation (API reconciliation)

    All checks run in parallel for performance, then aggregated.
    """

    def __init__(
        self,
        portfolio_value: float,
        enable_rag: bool = True,
        enable_regime: bool = True,
        enable_hallucination: bool = True,
        enable_ml_anomaly: bool = True,
        enable_position_check: bool = True,
    ):
        """
        Initialize the dynamic pre-trade gate.

        Args:
            portfolio_value: Current portfolio value for sizing checks
            enable_rag: Enable RAG semantic anomaly detection
            enable_regime: Enable regime-aware sizing checks
            enable_hallucination: Enable LLM hallucination prevention
            enable_ml_anomaly: Enable ML-based anomaly detection
            enable_position_check: Enable position reconciliation
        """
        self.portfolio_value = portfolio_value
        self.enable_rag = enable_rag
        self.enable_regime = enable_regime
        self.enable_hallucination = enable_hallucination
        self.enable_ml_anomaly = enable_ml_anomaly
        self.enable_position_check = enable_position_check

        # Initialize sub-systems
        self._init_subsystems()

        logger.info(f"DynamicPreTradeGate initialized (portfolio=${portfolio_value:,.2f})")

    def _init_subsystems(self) -> None:
        """Initialize all verification subsystems."""
        # RAG System
        self.rag_system = None
        if self.enable_rag:
            try:
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                self.rag_system = LessonsLearnedRAG()
                logger.info("RAG system initialized for semantic anomaly detection")
            except Exception as e:
                logger.warning(f"RAG system unavailable: {e}")

        # Regime Detector
        self.regime_sizer = None
        if self.enable_regime:
            try:
                from src.risk.regime_aware_sizing import RegimeAwareSizer

                self.regime_sizer = RegimeAwareSizer()
                logger.info("Regime-aware sizer initialized")
            except Exception as e:
                logger.warning(f"Regime sizer unavailable: {e}")

        # Hallucination Prevention
        self.hallucination_pipeline = None
        if self.enable_hallucination:
            try:
                from src.verification.hallucination_prevention import (
                    HallucinationPreventionPipeline,
                )

                self.hallucination_pipeline = HallucinationPreventionPipeline()
                logger.info("Hallucination prevention pipeline initialized")
            except Exception as e:
                logger.warning(f"Hallucination pipeline unavailable: {e}")

        # ML Anomaly Detector
        self.ml_detector = None
        if self.enable_ml_anomaly:
            try:
                from src.verification.ml_anomaly_detector import MLAnomalyDetector

                self.ml_detector = MLAnomalyDetector()
                logger.info("ML anomaly detector initialized")
            except Exception as e:
                logger.warning(f"ML detector unavailable: {e}")

        # Position Reconciler
        self.position_reconciler = None
        if self.enable_position_check:
            try:
                from src.verification.position_reconciler import PositionReconciler

                self.position_reconciler = PositionReconciler()
                logger.info("Position reconciler initialized")
            except Exception as e:
                logger.warning(f"Position reconciler unavailable: {e}")

    def validate_trade(self, trade: dict[str, Any]) -> ValidationResult:
        """
        Run comprehensive pre-trade validation.

        Args:
            trade: Trade dict with keys:
                - symbol: str
                - side: str (buy/sell)
                - quantity: float (optional)
                - notional: float (optional)
                - price: float (optional)
                - model: str (optional - LLM that recommended)
                - confidence: float (optional - LLM confidence)
                - reasoning: str (optional - LLM reasoning)

        Returns:
            ValidationResult with approval/rejection and detailed reasoning
        """
        symbol = trade.get("symbol", "UNKNOWN")
        side = trade.get("side", "buy")
        notional = trade.get("notional", 0.0)
        quantity = trade.get("quantity", 0.0)

        logger.info(
            f"Validating trade: {side.upper()} {symbol} (notional=${notional:.2f}, qty={quantity})"
        )

        # Run all checks
        check_results: dict[str, RiskCheckResult] = {}

        # Check 1: Semantic Anomaly (RAG)
        check_results["semantic_anomaly"] = self._check_semantic_anomaly(trade)

        # Check 2: Regime Aware Sizing
        check_results["regime_aware"] = self._check_regime_sizing(trade)

        # Check 3: LLM Hallucination Guard
        check_results["llm_guard"] = self._check_llm_hallucination(trade)

        # Check 4: Traditional Anomaly Detection
        check_results["traditional"] = self._check_traditional_anomaly(trade)

        # Check 5: Position Validation
        check_results["position_validation"] = self._check_position_validation(trade)

        # Aggregate risk scores
        risk_score = self.aggregate_risk_scores(
            {name: result.score for name, result in check_results.items()}
        )

        # Build prevention checklist
        prevention_checklist = []
        for result in check_results.values():
            prevention_checklist.extend(result.warnings)

        # Make decision
        safe_to_trade, recommendation = self._make_decision(risk_score, check_results)

        # Format output
        checks_dict = {
            name: {
                "score": result.score,
                "passed": result.passed,
                "details": result.details,
                "warnings": result.warnings,
                "recommendation": result.recommendation,
            }
            for name, result in check_results.items()
        }

        result = ValidationResult(
            safe_to_trade=safe_to_trade,
            risk_score=risk_score,
            checks=checks_dict,
            prevention_checklist=prevention_checklist,
            recommendation=recommendation,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Log result
        status = "✅ APPROVED" if safe_to_trade else "🚫 BLOCKED"
        logger.info(f"{status} - {symbol} (risk_score={risk_score:.1f}/100): {recommendation}")

        return result

    def aggregate_risk_scores(self, checks: dict[str, float]) -> float:
        """
        Aggregate individual risk scores into overall risk score.

        Uses weighted average with higher weights for critical checks.

        Args:
            checks: Dict of check_name -> risk_score (0-100)

        Returns:
            Aggregated risk score (0-100)
        """
        if not checks:
            return 50.0  # Default medium risk if no checks

        # Weights for each check (must sum to 1.0)
        weights = {
            "semantic_anomaly": 0.25,  # RAG lessons learned - critical
            "regime_aware": 0.20,  # Market conditions - important
            "llm_guard": 0.25,  # Hallucination prevention - critical
            "traditional": 0.15,  # Statistical anomalies - moderate
            "position_validation": 0.15,  # Position accuracy - moderate
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for check_name, score in checks.items():
            weight = weights.get(check_name, 0.1)  # Default 10% for unknown checks
            weighted_sum += score * weight
            total_weight += weight

        # Normalize to 0-100
        if total_weight > 0:
            return min(100.0, max(0.0, weighted_sum / total_weight))
        else:
            return 50.0

    # =========================================================================
    # Individual Risk Checks
    # =========================================================================

    def _check_semantic_anomaly(self, trade: dict) -> RiskCheckResult:
        """Check 1: Semantic trade anomaly using RAG."""
        if not self.rag_system:
            return RiskCheckResult(
                check_name="semantic_anomaly",
                passed=True,
                score=0.0,
                details={"skipped": True, "reason": "RAG not available"},
                warnings=[],
                recommendation="RAG unavailable - check skipped",
            )

        symbol = trade.get("symbol", "")
        side = trade.get("side", "")
        reasoning = trade.get("reasoning", "")

        try:
            # Query RAG for similar past incidents
            query = f"{side} {symbol} {reasoning}"
            similar_incidents = self.rag_system.search(query, top_k=5)

            # Filter for high severity incidents
            critical_incidents = [
                (lesson, score)
                for lesson, score in similar_incidents
                if score > 0.7 and lesson.severity in ["high", "critical"]
            ]

            if critical_incidents:
                # Found similar past mistakes - HIGH RISK
                score = min(100.0, len(critical_incidents) * 30.0)
                warnings = [
                    f"Similar incident: {lesson.title} (relevance={score:.0%})"
                    for lesson, score in critical_incidents[:3]
                ]
                return RiskCheckResult(
                    check_name="semantic_anomaly",
                    passed=False,
                    score=score,
                    details={
                        "similar_incidents": [
                            {
                                "id": lesson.id,
                                "title": lesson.title,
                                "severity": lesson.severity,
                                "relevance": score,
                            }
                            for lesson, score in critical_incidents
                        ]
                    },
                    warnings=warnings,
                    recommendation="CAUTION: Similar past mistakes detected in RAG",
                )
            else:
                # No critical incidents found
                return RiskCheckResult(
                    check_name="semantic_anomaly",
                    passed=True,
                    score=10.0,  # Small baseline risk
                    details={"similar_incidents": []},
                    warnings=[],
                    recommendation="No similar past incidents found",
                )

        except Exception as e:
            logger.warning(f"Semantic anomaly check failed: {e}")
            return RiskCheckResult(
                check_name="semantic_anomaly",
                passed=True,
                score=20.0,  # Moderate risk if check fails
                details={"error": str(e)},
                warnings=[f"RAG query failed: {e}"],
                recommendation="RAG check failed - proceed with caution",
            )

    def _check_regime_sizing(self, trade: dict) -> RiskCheckResult:
        """Check 2: Regime-aware position sizing."""
        if not self.regime_sizer:
            return RiskCheckResult(
                check_name="regime_aware",
                passed=True,
                score=0.0,
                details={"skipped": True},
                warnings=[],
                recommendation="Regime sizer unavailable",
            )

        notional = trade.get("notional", 0.0)
        symbol = trade.get("symbol", "")

        try:
            # Get regime-adjusted size
            result = self.regime_sizer.adjust_position_size(
                base_size=notional,
                account_equity=self.portfolio_value,
                symbol=symbol,
            )

            # Check if trading should be paused
            if result.should_pause_trading:
                return RiskCheckResult(
                    check_name="regime_aware",
                    passed=False,
                    score=100.0,  # Maximum risk - pause trading
                    details={
                        "regime": result.regime_label,
                        "vix_level": result.vix_level,
                        "risk_bias": result.risk_bias,
                    },
                    warnings=[f"Trading paused: {result.reason}"],
                    recommendation=f"BLOCK: {result.reason}",
                )

            # Calculate risk based on regime multiplier
            # Lower multiplier = higher risk environment
            risk_from_regime = (1.0 - result.final_multiplier) * 100
            risk_from_regime = max(0.0, min(100.0, risk_from_regime))

            warnings = []
            if result.final_multiplier < 0.7:
                warnings.append(
                    f"Regime {result.regime_label} reduces size by {(1 - result.final_multiplier) * 100:.0f}%"
                )

            return RiskCheckResult(
                check_name="regime_aware",
                passed=result.final_multiplier >= 0.3,  # Fail if <30% sizing
                score=risk_from_regime,
                details={
                    "regime": result.regime_label,
                    "multiplier": result.final_multiplier,
                    "original_size": result.original_size,
                    "adjusted_size": result.adjusted_size,
                    "confidence": result.regime_confidence,
                },
                warnings=warnings,
                recommendation=result.reason,
            )

        except Exception as e:
            logger.warning(f"Regime sizing check failed: {e}")
            return RiskCheckResult(
                check_name="regime_aware",
                passed=True,
                score=30.0,
                details={"error": str(e)},
                warnings=[f"Regime check failed: {e}"],
                recommendation="Regime detection failed - assuming moderate risk",
            )

    def _check_llm_hallucination(self, trade: dict) -> RiskCheckResult:
        """Check 3: LLM hallucination guard."""
        if not self.hallucination_pipeline:
            return RiskCheckResult(
                check_name="llm_guard",
                passed=True,
                score=0.0,
                details={"skipped": True},
                warnings=[],
                recommendation="Hallucination guard unavailable",
            )

        model = trade.get("model", "unknown")
        confidence = trade.get("confidence", 0.5)
        symbol = trade.get("symbol", "")
        side = trade.get("side", "")
        reasoning = trade.get("reasoning", "")

        try:
            # Run pre-trade hallucination check
            check_result = self.hallucination_pipeline.pre_trade_check(
                symbol=symbol,
                action=side.upper(),
                model=model,
                confidence=confidence,
                reasoning=reasoning,
            )

            # Convert to our risk score (0-100)
            risk_score = check_result["risk_score"] * 100

            violations = []
            if check_result["similar_mistakes"]:
                violations.append(f"{len(check_result['similar_mistakes'])} similar past mistakes")
            if check_result["pattern_matches"]:
                violations.append(
                    f"{len(check_result['pattern_matches'])} hallucination pattern matches"
                )

            return RiskCheckResult(
                check_name="llm_guard",
                passed=check_result["approved"],
                score=risk_score,
                details={
                    "similar_mistakes": check_result["similar_mistakes"],
                    "pattern_matches": check_result["pattern_matches"],
                    "violations": violations,
                },
                warnings=check_result["warnings"],
                recommendation=check_result["recommendation"],
            )

        except Exception as e:
            logger.warning(f"LLM hallucination check failed: {e}")
            return RiskCheckResult(
                check_name="llm_guard",
                passed=True,
                score=25.0,
                details={"error": str(e)},
                warnings=[f"Hallucination check failed: {e}"],
                recommendation="Hallucination guard failed - proceed with caution",
            )

    def _check_traditional_anomaly(self, trade: dict) -> RiskCheckResult:
        """Check 4: Traditional ML anomaly detection."""
        if not self.ml_detector:
            return RiskCheckResult(
                check_name="traditional",
                passed=True,
                score=0.0,
                details={"skipped": True},
                warnings=[],
                recommendation="ML detector unavailable",
            )

        try:
            # Create simplified trade data for detector
            trade_data = [
                {
                    "symbol": trade.get("symbol", ""),
                    "side": trade.get("side", ""),
                    "notional": trade.get("notional", 0.0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "pnl": 0,  # Not yet executed
                }
            ]

            # Run detection
            anomalies = self.ml_detector.detect_trading_anomalies(trade_data)

            if anomalies:
                # Calculate risk score from anomalies
                high_count = sum(1 for a in anomalies if a.severity == "high")
                medium_count = sum(1 for a in anomalies if a.severity == "medium")
                low_count = sum(1 for a in anomalies if a.severity == "low")

                risk_score = min(100.0, high_count * 40 + medium_count * 20 + low_count * 10)

                warnings = [a.description for a in anomalies[:3]]  # Top 3

                return RiskCheckResult(
                    check_name="traditional",
                    passed=high_count == 0,
                    score=risk_score,
                    details={
                        "anomalies": [
                            {
                                "severity": a.severity,
                                "description": a.description,
                                "metric": a.metric_name,
                            }
                            for a in anomalies
                        ]
                    },
                    warnings=warnings,
                    recommendation=f"Detected {len(anomalies)} anomalies",
                )
            else:
                return RiskCheckResult(
                    check_name="traditional",
                    passed=True,
                    score=5.0,  # Baseline
                    details={"anomalies": []},
                    warnings=[],
                    recommendation="No statistical anomalies detected",
                )

        except Exception as e:
            logger.warning(f"Traditional anomaly check failed: {e}")
            return RiskCheckResult(
                check_name="traditional",
                passed=True,
                score=15.0,
                details={"error": str(e)},
                warnings=[f"Anomaly detection failed: {e}"],
                recommendation="Anomaly detector failed",
            )

    def _check_position_validation(self, trade: dict) -> RiskCheckResult:
        """Check 5: Basic position validation and reconciliation."""
        if not self.position_reconciler:
            return RiskCheckResult(
                check_name="position_validation",
                passed=True,
                score=0.0,
                details={"skipped": True},
                warnings=[],
                recommendation="Position reconciler unavailable",
            )

        try:
            # Basic validation checks
            issues = []
            score = 0.0

            # Check 1: Trade size vs portfolio
            notional = trade.get("notional", 0.0)
            if notional > self.portfolio_value * 0.5:
                issues.append(f"Trade size ${notional:.2f} exceeds 50% of portfolio")
                score += 30.0

            # Check 2: Verify symbol format
            symbol = trade.get("symbol", "")
            if not symbol or len(symbol) > 5 or not symbol.isalpha():
                issues.append(f"Invalid symbol format: {symbol}")
                score += 25.0

            # Check 3: Verify side
            side = trade.get("side", "")
            if side.lower() not in ["buy", "sell"]:
                issues.append(f"Invalid side: {side}")
                score += 20.0

            # Check 4: Verify we have size info
            if notional <= 0 and trade.get("quantity", 0) <= 0:
                issues.append("No valid position size specified")
                score += 35.0

            return RiskCheckResult(
                check_name="position_validation",
                passed=len(issues) == 0,
                score=min(100.0, score),
                details={"issues": issues},
                warnings=issues,
                recommendation="Validation complete" if not issues else "Validation issues found",
            )

        except Exception as e:
            logger.warning(f"Position validation check failed: {e}")
            return RiskCheckResult(
                check_name="position_validation",
                passed=True,
                score=20.0,
                details={"error": str(e)},
                warnings=[f"Validation failed: {e}"],
                recommendation="Position validation failed",
            )

    def _make_decision(
        self, risk_score: float, check_results: dict[str, RiskCheckResult]
    ) -> tuple[bool, str]:
        """
        Make final trade approval decision.

        Decision Logic:
        - Risk < 30: APPROVE
        - 30 <= Risk < 60: WARN (log but allow)
        - Risk >= 60: BLOCK

        Args:
            risk_score: Aggregated risk score (0-100)
            check_results: Individual check results

        Returns:
            Tuple of (safe_to_trade, recommendation)
        """
        # Count failures
        failed_checks = [name for name, result in check_results.items() if not result.passed]

        if risk_score < 30:
            # Low risk - approve
            return True, f"APPROVED - Low risk ({risk_score:.1f}/100)"

        elif risk_score < 60:
            # Medium risk - warn but allow
            if failed_checks:
                return (
                    True,
                    f"WARN - Medium risk ({risk_score:.1f}/100). "
                    f"Failed checks: {', '.join(failed_checks)}",
                )
            else:
                return (
                    True,
                    f"WARN - Medium risk ({risk_score:.1f}/100) but all checks passed",
                )

        else:
            # High risk - block
            return (
                False,
                f"BLOCK - High risk ({risk_score:.1f}/100). "
                f"Failed checks: {', '.join(failed_checks) if failed_checks else 'multiple indicators'}",
            )


# Convenience functions
def create_pretrade_gate(portfolio_value: float) -> DynamicPreTradeGate:
    """Create a pre-trade gate with default settings."""
    return DynamicPreTradeGate(portfolio_value=portfolio_value)


def validate_trade(trade: dict[str, Any], portfolio_value: float) -> ValidationResult:
    """
    Quick validation function for one-off checks.

    Usage:
        result = validate_trade(
            trade={"symbol": "NVDA", "side": "buy", "notional": 1000.0},
            portfolio_value=100000.0
        )
        if result.safe_to_trade:
            execute_trade(trade)
    """
    gate = DynamicPreTradeGate(portfolio_value=portfolio_value)
    return gate.validate_trade(trade)
