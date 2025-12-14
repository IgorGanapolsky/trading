"""Regime-Aware Position Sizing Anomaly Detector.

Detects position sizing anomalies relative to current market regime (volatile vs calm).
Uses ATR-based volatility classification to adjust position limits dynamically.

Market regimes are classified based on ATR as % of price:
- CALM: < 1% ATR (low volatility, allow larger positions)
- NORMAL: 1-2% ATR (typical volatility, standard limits)
- VOLATILE: 2-3% ATR (elevated volatility, reduce exposure)
- EXTREME: > 5% ATR (crisis-level volatility, minimal exposure)

This prevents the common mistake of over-sizing positions during market turmoil,
which is a leading cause of catastrophic losses in quant trading.

Author: Trading System CTO
Created: 2025-12-11
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PositionAnomalyResult:
    """Result of position sizing anomaly check."""

    safe: bool
    risk_score: float  # 0-100 (0 = safe, 100 = critical)
    regime: str
    max_allowed: float  # Max position % allowed in this regime
    actual_pct: float  # Actual position % requested
    recommendation: str
    atr_pct: float
    violation_severity: str  # 'none', 'minor', 'major', 'critical'


class RegimeAwarePositionChecker:
    """
    Detects position sizing anomalies relative to current market regime.

    Uses ATR (Average True Range) as a % of price to classify market volatility
    and enforce regime-appropriate position limits.

    Example:
        checker = RegimeAwarePositionChecker(portfolio_value=10000)
        result = checker.check_position(
            symbol='SPY',
            amount=1500,  # $1500 position
            atr_pct=1.2    # 1.2% ATR
        )
        if not result.safe:
            print(f"WARNING: {result.recommendation}")
    """

    # Regime thresholds based on ATR as % of price
    REGIME_THRESHOLDS = {
        "CALM": (0.0, 1.0),  # < 1% ATR
        "NORMAL": (1.0, 2.0),  # 1-2% ATR
        "VOLATILE": (2.0, 5.0),  # 2-5% ATR
        "EXTREME": (5.0, float("inf")),  # > 5% ATR
    }

    # Maximum position size as % of portfolio for each regime
    MAX_POSITION_PCT = {
        "CALM": 0.08,  # 8% in calm markets (lower vol = can size up)
        "NORMAL": 0.05,  # 5% in normal markets (standard risk)
        "VOLATILE": 0.03,  # 3% in volatile markets (reduce exposure)
        "EXTREME": 0.01,  # 1% in extreme markets (survival mode)
    }

    def __init__(
        self,
        portfolio_value: float,
        enable_rag_query: bool = True,
        rag_query_threshold: float = 70.0,  # Query RAG if risk score > 70
    ):
        """
        Initialize regime-aware position checker.

        Args:
            portfolio_value: Current portfolio value in dollars
            enable_rag_query: Whether to query RAG for violation context
            rag_query_threshold: Risk score threshold for RAG queries
        """
        self.portfolio_value = portfolio_value
        self.enable_rag_query = enable_rag_query
        self.rag_query_threshold = rag_query_threshold

        logger.info(
            f"RegimeAwarePositionChecker initialized: "
            f"Portfolio=${portfolio_value:,.2f}, RAG={'enabled' if enable_rag_query else 'disabled'}"
        )

    def classify_regime(self, atr_pct: float) -> str:
        """
        Classify market regime based on ATR percentage.

        Args:
            atr_pct: ATR as percentage of price (e.g., 1.5 for 1.5%)

        Returns:
            Regime classification: CALM, NORMAL, VOLATILE, or EXTREME
        """
        # Handle negative ATR (invalid but defensive)
        if atr_pct < 0:
            atr_pct = abs(atr_pct)

        for regime, (min_atr, max_atr) in self.REGIME_THRESHOLDS.items():
            if min_atr <= atr_pct < max_atr:
                return regime

        # Fallback to EXTREME if somehow not matched
        return "EXTREME"

    def get_max_position_pct(self, regime: str) -> float:
        """
        Get maximum position size as % of portfolio for given regime.

        Args:
            regime: Market regime (CALM, NORMAL, VOLATILE, EXTREME)

        Returns:
            Maximum position size as decimal (e.g., 0.05 for 5%)
        """
        return self.MAX_POSITION_PCT.get(regime, 0.01)  # Default to 1% if unknown

    def check_position(
        self,
        symbol: str,
        amount: float,
        atr_pct: float,
    ) -> PositionAnomalyResult:
        """
        Check if position size is appropriate for current market regime.

        Args:
            symbol: Ticker symbol
            amount: Position size in dollars
            atr_pct: ATR as percentage of price (e.g., 1.5 for 1.5%)

        Returns:
            PositionAnomalyResult with safety assessment and recommendations
        """
        # Classify market regime
        regime = self.classify_regime(atr_pct)

        # Get max allowed position for this regime
        max_allowed_pct = self.get_max_position_pct(regime)
        max_allowed_dollars = self.portfolio_value * max_allowed_pct

        # Calculate actual position as % of portfolio
        actual_pct = amount / self.portfolio_value if self.portfolio_value > 0 else 0.0

        # Check if position is safe
        safe = amount <= max_allowed_dollars

        # Calculate risk score (0-100)
        if safe:
            # Safe positions get low scores (0-30)
            risk_score = (actual_pct / max_allowed_pct) * 30.0
        else:
            # Violations get high scores (50-100)
            overage_pct = (actual_pct - max_allowed_pct) / max_allowed_pct
            risk_score = min(100.0, 50.0 + (overage_pct * 100.0))

        # Determine violation severity
        if risk_score < 30:
            violation_severity = "none"
        elif risk_score < 50:
            violation_severity = "minor"
        elif risk_score < 75:
            violation_severity = "major"
        else:
            violation_severity = "critical"

        # Generate recommendation
        recommendation = self._generate_recommendation(
            symbol=symbol,
            regime=regime,
            safe=safe,
            actual_pct=actual_pct,
            max_allowed_pct=max_allowed_pct,
            atr_pct=atr_pct,
            risk_score=risk_score,
        )

        # Query RAG if high risk and enabled
        if self.enable_rag_query and risk_score >= self.rag_query_threshold:
            self._query_rag_for_context(symbol, regime, atr_pct, actual_pct)

        return PositionAnomalyResult(
            safe=safe,
            risk_score=risk_score,
            regime=regime,
            max_allowed=max_allowed_pct,
            actual_pct=actual_pct,
            recommendation=recommendation,
            atr_pct=atr_pct,
            violation_severity=violation_severity,
        )

    def _generate_recommendation(
        self,
        symbol: str,
        regime: str,
        safe: bool,
        actual_pct: float,
        max_allowed_pct: float,
        atr_pct: float,
        risk_score: float,
    ) -> str:
        """Generate human-readable recommendation."""
        if safe:
            return (
                f"✅ SAFE: {symbol} position {actual_pct * 100:.1f}% is within "
                f"{max_allowed_pct * 100:.1f}% limit for {regime} regime (ATR: {atr_pct:.1f}%)"
            )

        # Violation
        overage = (actual_pct - max_allowed_pct) * self.portfolio_value

        # Avoid division by zero for edge cases
        if actual_pct > 0:
            reduction_pct = ((actual_pct - max_allowed_pct) / actual_pct) * 100
        else:
            reduction_pct = 0.0

        severity_emoji = {
            "minor": "⚠️",
            "major": "🚨",
            "critical": "🔴",
        }.get("critical" if risk_score >= 75 else "major" if risk_score >= 50 else "minor", "⚠️")

        return (
            f"{severity_emoji} VIOLATION: {symbol} position {actual_pct * 100:.1f}% exceeds "
            f"{max_allowed_pct * 100:.1f}% limit for {regime} regime (ATR: {atr_pct:.1f}%). "
            f"Reduce position by ${overage:,.2f} ({reduction_pct:.1f}%) to comply. "
            f"Risk score: {risk_score:.0f}/100"
        )

    def _query_rag_for_context(
        self,
        symbol: str,
        regime: str,
        atr_pct: float,
        actual_pct: float,
    ) -> list[dict[str, Any]]:
        """
        Query RAG knowledge base for context on position sizing violations.

        This helps provide historical context on why large positions in volatile
        markets are dangerous (e.g., past incidents, best practices).

        Args:
            symbol: Ticker symbol
            regime: Market regime
            atr_pct: ATR percentage
            actual_pct: Actual position percentage

        Returns:
            List of relevant RAG results
        """
        try:
            # Import here to avoid circular dependency
            from src.rag.rag_retriever import query_rag

            # Query for relevant lessons learned
            query = f"large position volatile market {regime} regime {symbol} risk management"
            results = query_rag(query, top_k=3)

            if results:
                logger.info(
                    f"RAG context retrieved for {symbol} violation: "
                    f"{len(results)} relevant lessons found"
                )
                # Log key findings
                for result in results:
                    logger.info(
                        f"  - {result.get('title', 'Unknown')}: {result.get('summary', '')[:100]}"
                    )

            return results

        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return []

    def check_multiple_positions(
        self,
        positions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Check multiple positions for regime-aware sizing violations.

        Args:
            positions: List of position dicts with keys:
                - symbol: str
                - amount: float (position size in dollars)
                - atr_pct: float (ATR as % of price)

        Returns:
            Summary dict with:
                - total_positions: int
                - safe_count: int
                - violation_count: int
                - violations: list[PositionAnomalyResult]
                - total_risk_score: float
                - passed: bool
        """
        results = []
        violations = []

        for pos in positions:
            result = self.check_position(
                symbol=pos["symbol"],
                amount=pos["amount"],
                atr_pct=pos["atr_pct"],
            )
            results.append(result)

            if not result.safe:
                violations.append(result)

        # Calculate summary stats
        total_risk_score = sum(r.risk_score for r in results) / len(results) if results else 0.0
        passed = len(violations) == 0

        return {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(positions),
            "safe_count": len(results) - len(violations),
            "violation_count": len(violations),
            "violations": [
                {
                    "symbol": v.recommendation.split()[2],  # Extract symbol
                    "regime": v.regime,
                    "risk_score": v.risk_score,
                    "recommendation": v.recommendation,
                }
                for v in violations
            ],
            "total_risk_score": round(total_risk_score, 2),
            "passed": passed,
        }

    def to_dict(self, result: PositionAnomalyResult) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "safe": result.safe,
            "risk_score": round(result.risk_score, 2),
            "regime": result.regime,
            "max_allowed_pct": round(result.max_allowed * 100, 2),
            "actual_pct": round(result.actual_pct * 100, 2),
            "recommendation": result.recommendation,
            "atr_pct": round(result.atr_pct, 2),
            "violation_severity": result.violation_severity,
        }


def create_regime_checker(
    portfolio_value: float | None = None,
) -> RegimeAwarePositionChecker:
    """
    Create regime-aware position checker with defaults.

    Args:
        portfolio_value: Portfolio value (if None, uses $10000 default)

    Returns:
        Configured RegimeAwarePositionChecker instance
    """
    if portfolio_value is None:
        portfolio_value = 10000.0  # Default for testing

    return RegimeAwarePositionChecker(
        portfolio_value=portfolio_value,
        enable_rag_query=True,
    )


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    checker = create_regime_checker(portfolio_value=10000)

    # Test scenarios
    test_positions = [
        {"symbol": "SPY", "amount": 500, "atr_pct": 0.8},  # CALM regime, safe
        {"symbol": "QQQ", "amount": 700, "atr_pct": 1.5},  # NORMAL regime, safe
        {"symbol": "TSLA", "amount": 1000, "atr_pct": 4.0},  # VOLATILE regime, VIOLATION
        {"symbol": "GME", "amount": 1500, "atr_pct": 8.0},  # EXTREME regime, VIOLATION
    ]

    print("=" * 70)
    print("REGIME-AWARE POSITION ANOMALY DETECTOR - DEMO")
    print("=" * 70)

    for pos in test_positions:
        result = checker.check_position(
            symbol=pos["symbol"],
            amount=pos["amount"],
            atr_pct=pos["atr_pct"],
        )

        print(f"\n{pos['symbol']}:")
        print(f"  Amount: ${pos['amount']:,}")
        print(f"  ATR: {pos['atr_pct']:.1f}%")
        print(f"  {result.recommendation}")

    # Summary check
    summary = checker.check_multiple_positions(test_positions)
    print(f"\n{'=' * 70}")
    print("SUMMARY:")
    print(f"  Total Positions: {summary['total_positions']}")
    print(f"  Safe: {summary['safe_count']}")
    print(f"  Violations: {summary['violation_count']}")
    print(f"  Overall Risk Score: {summary['total_risk_score']:.1f}/100")
    print(f"  Status: {'✅ PASSED' if summary['passed'] else '❌ FAILED'}")
    print("=" * 70)
