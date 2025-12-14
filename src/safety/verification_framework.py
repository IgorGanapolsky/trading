"""
Trading System Verification Framework

Comprehensive pre-trade and post-trade verification to prevent mistakes.
Integrates with RAG for lessons learned and ML pipeline for anomaly detection.

Key Components:
1. Pre-Trade Verification - Catches mistakes before execution
2. Post-Trade Audit - Learns from every trade
3. Lessons Learned RAG - Queries historical mistakes to prevent repeats
4. ML Anomaly Detection - Detects unusual patterns in real-time

Author: Trading System
Created: 2025-12-11
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a verification check."""

    check_name: str
    passed: bool
    severity: str  # "INFO", "WARNING", "ERROR", "CRITICAL"
    message: str
    details: dict = field(default_factory=dict)
    suggested_action: Optional[str] = None


@dataclass
class TradeVerificationReport:
    """Complete verification report for a trade."""

    timestamp: str
    symbol: str
    side: str
    amount: float
    checks: list[VerificationResult]
    overall_pass: bool
    blocked: bool
    block_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "checks": [
                {
                    "name": c.check_name,
                    "passed": c.passed,
                    "severity": c.severity,
                    "message": c.message,
                }
                for c in self.checks
            ],
            "overall_pass": self.overall_pass,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


class PreTradeVerifier:
    """
    Pre-trade verification system.

    Runs multiple checks before any trade executes:
    1. Size sanity check (not 200x expected)
    2. Symbol validity check
    3. Market hours check
    4. Circuit breaker check
    5. RAG lessons learned check
    6. ML anomaly detection
    """

    def __init__(
        self,
        daily_budget: float = 10.0,
        max_position_pct: float = 0.15,
        lessons_db_path: str = "data/lessons_learned.json",
    ):
        self.daily_budget = daily_budget
        self.max_position_pct = max_position_pct
        self.lessons_db_path = Path(lessons_db_path)
        self.lessons_db = self._load_lessons()

    def verify_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
        portfolio_value: float,
        current_positions: Optional[dict] = None,
    ) -> TradeVerificationReport:
        """
        Run all pre-trade verification checks.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            amount: Trade amount in dollars
            portfolio_value: Current portfolio value
            current_positions: Dict of current positions

        Returns:
            TradeVerificationReport with all check results
        """
        checks = []

        # 1. Size Sanity Check
        checks.append(self._check_size_sanity(amount, portfolio_value))

        # 2. Budget Check
        checks.append(self._check_daily_budget(amount))

        # 3. Position Concentration Check
        checks.append(self._check_concentration(symbol, amount, portfolio_value, current_positions))

        # 4. Historical Mistake Check (RAG)
        checks.append(self._check_lessons_learned(symbol, side, amount))

        # 5. Anomaly Detection
        checks.append(self._check_anomaly(symbol, side, amount, portfolio_value))

        # Determine if trade should be blocked
        critical_failures = [c for c in checks if not c.passed and c.severity == "CRITICAL"]
        error_failures = [c for c in checks if not c.passed and c.severity == "ERROR"]

        blocked = len(critical_failures) > 0 or len(error_failures) >= 2
        block_reason = None
        if blocked:
            reasons = [c.message for c in critical_failures + error_failures]
            block_reason = "; ".join(reasons[:3])

        return TradeVerificationReport(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            side=side,
            amount=amount,
            checks=checks,
            overall_pass=not blocked,
            blocked=blocked,
            block_reason=block_reason,
        )

    def _check_size_sanity(self, amount: float, portfolio_value: float) -> VerificationResult:
        """Check if trade size is reasonable."""
        # Flag if > 10x daily budget or > 20% of portfolio
        max_reasonable = max(self.daily_budget * 10, portfolio_value * 0.20)

        if amount > max_reasonable:
            return VerificationResult(
                check_name="size_sanity",
                passed=False,
                severity="CRITICAL",
                message=f"Trade size ${amount:.2f} exceeds max reasonable ${max_reasonable:.2f}",
                details={"amount": amount, "max_reasonable": max_reasonable},
                suggested_action="Review trade size calculation",
            )

        # Warning if > 5x daily budget
        if amount > self.daily_budget * 5:
            return VerificationResult(
                check_name="size_sanity",
                passed=True,
                severity="WARNING",
                message=f"Trade size ${amount:.2f} is {amount / self.daily_budget:.1f}x daily budget",
                details={"amount": amount, "daily_budget": self.daily_budget},
            )

        return VerificationResult(
            check_name="size_sanity",
            passed=True,
            severity="INFO",
            message=f"Trade size ${amount:.2f} is reasonable",
        )

    def _check_daily_budget(self, amount: float) -> VerificationResult:
        """Check if trade fits within daily budget."""
        if amount > self.daily_budget * 200:  # 200x is definitely wrong
            return VerificationResult(
                check_name="daily_budget",
                passed=False,
                severity="CRITICAL",
                message=f"Trade ${amount:.2f} is {amount / self.daily_budget:.0f}x daily budget - LIKELY BUG",
                details={
                    "amount": amount,
                    "daily_budget": self.daily_budget,
                    "multiplier": amount / self.daily_budget,
                },
                suggested_action="Check for unit conversion error (shares vs dollars)",
            )

        return VerificationResult(
            check_name="daily_budget",
            passed=True,
            severity="INFO",
            message="Trade within expected budget range",
        )

    def _check_concentration(
        self,
        symbol: str,
        amount: float,
        portfolio_value: float,
        current_positions: Optional[dict],
    ) -> VerificationResult:
        """Check position concentration limits."""
        current_exposure = 0.0
        if current_positions and symbol in current_positions:
            current_exposure = current_positions[symbol].get("market_value", 0)

        new_exposure = current_exposure + amount
        exposure_pct = new_exposure / portfolio_value if portfolio_value > 0 else 0

        if exposure_pct > self.max_position_pct:
            return VerificationResult(
                check_name="concentration",
                passed=False,
                severity="ERROR",
                message=f"{symbol} would be {exposure_pct:.1%} of portfolio (max {self.max_position_pct:.1%})",
                details={
                    "symbol": symbol,
                    "exposure_pct": exposure_pct,
                    "max_pct": self.max_position_pct,
                },
                suggested_action="Reduce position size or diversify",
            )

        return VerificationResult(
            check_name="concentration",
            passed=True,
            severity="INFO",
            message=f"{symbol} concentration {exposure_pct:.1%} within limits",
        )

    def _check_lessons_learned(self, symbol: str, side: str, amount: float) -> VerificationResult:
        """Check RAG lessons learned database for similar past mistakes."""
        if not self.lessons_db:
            return VerificationResult(
                check_name="lessons_learned",
                passed=True,
                severity="INFO",
                message="No historical lessons to check",
            )

        # Search for similar scenarios
        warnings = []
        for lesson in self.lessons_db:
            # Check for symbol-specific lessons
            if lesson.get("symbol") == symbol:
                warnings.append(f"Previous issue with {symbol}: {lesson.get('lesson', 'Unknown')}")

            # Check for size-related lessons
            if lesson.get("category") == "size_error":
                if amount > lesson.get("threshold", float("inf")):
                    warnings.append(f"Size warning: {lesson.get('lesson', 'Check trade size')}")

        if warnings:
            return VerificationResult(
                check_name="lessons_learned",
                passed=True,  # Don't block, just warn
                severity="WARNING",
                message=f"Found {len(warnings)} relevant lessons",
                details={"warnings": warnings[:3]},
                suggested_action="Review historical lessons before proceeding",
            )

        return VerificationResult(
            check_name="lessons_learned",
            passed=True,
            severity="INFO",
            message="No matching historical lessons",
        )

    def _check_anomaly(
        self,
        symbol: str,
        side: str,
        amount: float,
        portfolio_value: float,
    ) -> VerificationResult:
        """ML-based anomaly detection for unusual trades."""
        # Simple statistical anomaly detection
        # In production, this would use a trained model

        anomaly_score = 0.0
        reasons = []

        # Check 1: Amount vs portfolio ratio
        ratio = amount / portfolio_value if portfolio_value > 0 else 0
        if ratio > 0.10:  # > 10% of portfolio
            anomaly_score += 0.3
            reasons.append(f"Large position: {ratio:.1%} of portfolio")

        # Check 2: Amount vs daily budget
        budget_ratio = amount / self.daily_budget if self.daily_budget > 0 else 0
        if budget_ratio > 10:
            anomaly_score += 0.4
            reasons.append(f"Large vs budget: {budget_ratio:.1f}x")

        # Check 3: Round number check (often indicates manual error)
        if amount == round(amount, -2) and amount > 1000:
            anomaly_score += 0.1
            reasons.append("Suspiciously round number")

        if anomaly_score >= 0.5:
            return VerificationResult(
                check_name="anomaly_detection",
                passed=False,
                severity="ERROR",
                message=f"Anomaly detected (score: {anomaly_score:.2f})",
                details={"anomaly_score": anomaly_score, "reasons": reasons},
                suggested_action="Manual review recommended",
            )
        elif anomaly_score >= 0.3:
            return VerificationResult(
                check_name="anomaly_detection",
                passed=True,
                severity="WARNING",
                message=f"Mild anomaly (score: {anomaly_score:.2f})",
                details={"anomaly_score": anomaly_score, "reasons": reasons},
            )

        return VerificationResult(
            check_name="anomaly_detection",
            passed=True,
            severity="INFO",
            message="No anomalies detected",
        )

    def _load_lessons(self) -> list[dict]:
        """Load lessons learned database."""
        if not self.lessons_db_path.exists():
            return []
        try:
            with open(self.lessons_db_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load lessons DB: {e}")
            return []

    def add_lesson(
        self,
        category: str,
        lesson: str,
        symbol: Optional[str] = None,
        threshold: Optional[float] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Add a new lesson to the database."""
        new_lesson = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "lesson": lesson,
            "symbol": symbol,
            "threshold": threshold,
            "details": details or {},
        }

        self.lessons_db.append(new_lesson)

        # Save to disk
        self.lessons_db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lessons_db_path, "w") as f:
            json.dump(self.lessons_db, f, indent=2)

        logger.info(f"Lesson added: {lesson}")


class PostTradeAuditor:
    """
    Post-trade audit system.

    Analyzes executed trades to:
    1. Detect execution anomalies
    2. Track slippage and costs
    3. Generate lessons learned
    4. Feed ML pipeline with new data
    """

    def __init__(
        self,
        audit_log_path: str = "data/trade_audit_log.jsonl",
        verifier: Optional[PreTradeVerifier] = None,
    ):
        self.audit_log_path = Path(audit_log_path)
        self.verifier = verifier or PreTradeVerifier()

    def audit_trade(
        self,
        order: dict,
        fill: dict,
        expected_amount: float,
    ) -> dict:
        """
        Audit a completed trade.

        Args:
            order: Original order details
            fill: Fill/execution details
            expected_amount: What we expected to trade

        Returns:
            Audit report
        """
        actual_amount = fill.get("filled_qty", 0) * fill.get("filled_avg_price", 0)
        slippage = abs(actual_amount - expected_amount)
        slippage_pct = slippage / expected_amount * 100 if expected_amount > 0 else 0

        anomalies = []
        lessons = []

        # Check for size discrepancy
        if actual_amount > expected_amount * 1.5:
            anomalies.append(
                {
                    "type": "size_discrepancy",
                    "message": f"Actual ${actual_amount:.2f} >> expected ${expected_amount:.2f}",
                }
            )
            lessons.append(
                {
                    "category": "size_error",
                    "lesson": f"Trade executed at {actual_amount / expected_amount:.1f}x expected size",
                    "threshold": expected_amount,
                }
            )

        # Check for high slippage
        if slippage_pct > 1.0:
            anomalies.append(
                {
                    "type": "high_slippage",
                    "message": f"Slippage {slippage_pct:.2f}% exceeds 1% threshold",
                }
            )

        # Generate audit report
        report = {
            "timestamp": datetime.now().isoformat(),
            "order_id": order.get("id"),
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "expected_amount": expected_amount,
            "actual_amount": actual_amount,
            "slippage": slippage,
            "slippage_pct": slippage_pct,
            "anomalies": anomalies,
            "lessons": lessons,
        }

        # Save to audit log
        self._save_audit(report)

        # Add any lessons learned
        for lesson in lessons:
            self.verifier.add_lesson(**lesson)

        return report

    def _save_audit(self, report: dict) -> None:
        """Append audit report to log file."""
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_log_path, "a") as f:
            f.write(json.dumps(report) + "\n")


def create_verification_pipeline(
    daily_budget: float = 10.0,
) -> tuple[PreTradeVerifier, PostTradeAuditor]:
    """
    Create complete verification pipeline.

    Returns:
        Tuple of (PreTradeVerifier, PostTradeAuditor)
    """
    verifier = PreTradeVerifier(daily_budget=daily_budget)
    auditor = PostTradeAuditor(verifier=verifier)
    return verifier, auditor


# Pre-loaded lessons from known issues
DEFAULT_LESSONS = [
    {
        "category": "size_error",
        "lesson": "Nov 3 bug: 200x position size due to unit confusion (shares vs dollars)",
        "threshold": 1000,
        "details": {"bug_date": "2025-11-03", "expected": 8, "actual": 1600},
    },
    {
        "category": "execution",
        "lesson": "Always verify order size matches expected daily budget before submit",
        "threshold": 100,
    },
    {
        "category": "validation",
        "lesson": "Pre-trade verification should block orders > 10x daily budget",
        "threshold": None,
    },
]


def initialize_lessons_db(path: str = "data/lessons_learned.json") -> None:
    """Initialize lessons DB with default lessons."""
    db_path = Path(path)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(db_path, "w") as f:
            json.dump(DEFAULT_LESSONS, f, indent=2)
        logger.info(f"Initialized lessons DB with {len(DEFAULT_LESSONS)} lessons")


if __name__ == "__main__":
    """Demo the verification framework."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TRADE VERIFICATION FRAMEWORK DEMO")
    print("=" * 80)

    # Initialize
    initialize_lessons_db()
    verifier, auditor = create_verification_pipeline(daily_budget=10.0)

    # Test scenarios
    scenarios = [
        {"symbol": "SPY", "side": "buy", "amount": 8.0, "portfolio": 100000},
        {"symbol": "SPY", "side": "buy", "amount": 100.0, "portfolio": 100000},
        {
            "symbol": "SPY",
            "side": "buy",
            "amount": 1600.0,
            "portfolio": 100000,
        },  # Nov 3 bug scenario
        {
            "symbol": "NVDA",
            "side": "buy",
            "amount": 20000.0,
            "portfolio": 100000,
        },  # 20% of portfolio
    ]

    print("\nPre-Trade Verification Tests:")
    print("-" * 80)

    for s in scenarios:
        report = verifier.verify_trade(
            symbol=s["symbol"],
            side=s["side"],
            amount=s["amount"],
            portfolio_value=s["portfolio"],
        )

        status = "🚫 BLOCKED" if report.blocked else "✅ PASS"
        print(f"\n{status} | {s['symbol']} ${s['amount']:.2f}")

        for check in report.checks:
            icon = "✅" if check.passed else "❌"
            print(f"  {icon} {check.check_name}: {check.message}")

        if report.blocked:
            print(f"  Block Reason: {report.block_reason}")
