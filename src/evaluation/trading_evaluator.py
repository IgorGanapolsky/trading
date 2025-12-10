"""
Trading System Evaluator - Week 1 Implementation

Multi-dimensional evaluation of trading system performance.
FREE - Uses local processing, no API costs.

Evaluates:
- Accuracy: Did trades execute correctly?
- Compliance: Did we follow procedures?
- Reliability: Did system work as expected?
- Errors: What went wrong?
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """
    Result of a single evaluation dimension.

    Attributes:
        dimension: Evaluation dimension name ("accuracy", "compliance", "reliability", "errors")
        score: Score from 0.0 to 1.0 (1.0 = perfect)
        passed: Whether this dimension passed (score >= 0.7)
        issues: List of issues found in this dimension
        metadata: Additional metadata about the evaluation
        timestamp: ISO format timestamp of when evaluation was performed
    """

    dimension: str  # "accuracy", "compliance", "reliability", "errors"
    score: float  # 0.0 to 1.0 (1.0 = perfect)
    passed: bool
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TradeEvaluation:
    """
    Complete evaluation of a single trade execution.

    Attributes:
        trade_id: Unique identifier for the trade
        symbol: Stock symbol that was traded
        timestamp: ISO format timestamp of when trade was executed
        evaluation: Dictionary of evaluation results by dimension
        overall_score: Average score across all dimensions (0.0 to 1.0)
        passed: Whether trade passed all critical checks
        critical_issues: List of critical issues that caused failure
    """

    trade_id: str
    symbol: str
    timestamp: str
    evaluation: dict[str, EvaluationResult] = field(default_factory=dict)
    overall_score: float = 0.0
    passed: bool = True
    critical_issues: list[str] = field(default_factory=list)


class TradingSystemEvaluator:
    """
    Multi-dimensional evaluator for trading system.

    FREE - No API costs, local processing only.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """
        Initialize evaluator.

        Args:
            data_dir: Directory for storing evaluation data (default: "data")
        """
        self.data_dir = Path(data_dir) if data_dir else Path("data")
        self.data_dir.mkdir(exist_ok=True)

        # Evaluation history storage
        self.eval_dir = self.data_dir / "evaluations"
        self.eval_dir.mkdir(exist_ok=True)

        # Configuration thresholds
        self.MAX_ORDER_MULTIPLIER = 10.0  # Reject orders >10x expected
        self.MAX_STALENESS_HOURS = 24  # System state must be <24h old
        self.MIN_DAILY_ALLOCATION = 1.0  # Minimum $1/day
        self.MAX_DAILY_ALLOCATION = 100.0  # Maximum $100/day (safety)

        logger.info(
            "TradingSystemEvaluator initialized",
            extra={
                "component": "evaluation",
                "action": "init",
                "data_dir": str(self.data_dir),
                "eval_dir": str(self.eval_dir),
            },
        )

    def evaluate_trade_execution(
        self,
        trade_result: dict[str, Any],
        expected_amount: float,
        daily_allocation: float,
    ) -> TradeEvaluation:
        """
        Evaluate a single trade execution.

        Args:
            trade_result: Trade execution result from autonomous_trader.py
            expected_amount: Expected trade amount (e.g., $6 for Tier 1)
            daily_allocation: Total daily allocation (e.g., $10/day)

        Returns:
            TradeEvaluation with all dimensions evaluated
        """
        trade_id = trade_result.get("order_id", f"trade_{datetime.now().isoformat()}")
        symbol = trade_result.get("symbol", "UNKNOWN")
        timestamp = trade_result.get("timestamp", datetime.now().isoformat())

        logger.info(
            f"Evaluating trade: {symbol}",
            extra={
                "component": "evaluation",
                "action": "evaluate_trade",
                "trade_id": trade_id,
                "symbol": symbol,
                "expected_amount": expected_amount,
                "daily_allocation": daily_allocation,
            },
        )

        evaluation = TradeEvaluation(trade_id=trade_id, symbol=symbol, timestamp=timestamp)

        # 1. ACCURACY EVALUATION
        accuracy = self._evaluate_accuracy(trade_result, expected_amount)
        evaluation.evaluation["accuracy"] = accuracy

        # 2. COMPLIANCE EVALUATION
        compliance = self._evaluate_compliance(trade_result, daily_allocation)
        evaluation.evaluation["compliance"] = compliance

        # 3. RELIABILITY EVALUATION
        reliability = self._evaluate_reliability(trade_result)
        evaluation.evaluation["reliability"] = reliability

        # 4. ERROR DETECTION
        errors = self._detect_errors(trade_result, expected_amount)
        evaluation.evaluation["errors"] = errors

        # Calculate overall score
        scores = [e.score for e in evaluation.evaluation.values()]
        evaluation.overall_score = sum(scores) / len(scores) if scores else 0.0

        # Determine if passed (all critical checks must pass)
        evaluation.passed = all(
            e.passed
            for e in evaluation.evaluation.values()
            if e.dimension != "errors"  # Errors are warnings, not failures
        )

        # Collect critical issues
        for eval_result in evaluation.evaluation.values():
            if not eval_result.passed:
                evaluation.critical_issues.extend(eval_result.issues)

        return evaluation

    def _evaluate_accuracy(
        self, trade_result: dict[str, Any], expected_amount: float
    ) -> EvaluationResult:
        """Evaluate trade execution accuracy."""
        issues = []
        score = 1.0

        # Check order size
        actual_amount = trade_result.get("amount", 0.0)
        logger.debug(
            f"Accuracy check: actual=${actual_amount:.2f}, "
            f"expected=${expected_amount:.2f}, "
            f"multiplier={actual_amount / expected_amount if expected_amount > 0 else 0:.2f}x"
        )

        if actual_amount == 0:
            issues.append("Order amount is zero")
            score = 0.0
            logger.error(
                f"CRITICAL: Order amount is zero for {trade_result.get('symbol', 'UNKNOWN')}"
            )
        elif actual_amount > expected_amount * self.MAX_ORDER_MULTIPLIER:
            error_msg = (
                f"Order size {actual_amount} is >{self.MAX_ORDER_MULTIPLIER}x expected "
                f"({expected_amount}) - CRITICAL ERROR"
            )
            issues.append(error_msg)
            score = 0.0
            logger.error(
                f"CRITICAL ERROR PATTERN #1: {error_msg} | "
                f"Symbol: {trade_result.get('symbol', 'UNKNOWN')} | "
                f"Order ID: {trade_result.get('order_id', 'unknown')}"
            )
        elif abs(actual_amount - expected_amount) > expected_amount * 0.1:
            # Allow 10% variance
            issues.append(
                f"Order size {actual_amount} differs from expected {expected_amount} by >10%"
            )
            score = 0.7

        # Check order status
        order_status = trade_result.get("status", "unknown")
        if order_status not in ["filled", "accepted", "pending_new"]:
            issues.append(f"Order status is {order_status} (not filled/accepted)")
            score = min(score, 0.5)

        return EvaluationResult(
            dimension="accuracy",
            score=score,
            passed=score >= 0.7,
            issues=issues,
            metadata={
                "expected_amount": expected_amount,
                "actual_amount": actual_amount,
                "order_status": order_status,
            },
        )

    def _evaluate_compliance(
        self, trade_result: dict[str, Any], daily_allocation: float
    ) -> EvaluationResult:
        """
        Evaluate procedure compliance.

        Checks:
        - Daily allocation within limits ($1-$100)
        - Order was validated before execution
        - Pre-flight checks passed

        Args:
            trade_result: Trade execution result dictionary
            daily_allocation: Total daily allocation in dollars

        Returns:
            EvaluationResult with compliance score and issues
        """
        issues = []
        score = 1.0

        # Check daily allocation limits
        if daily_allocation < self.MIN_DAILY_ALLOCATION:
            issues.append(
                f"Daily allocation {daily_allocation} below minimum ${self.MIN_DAILY_ALLOCATION}"
            )
            score = 0.5

        if daily_allocation > self.MAX_DAILY_ALLOCATION:
            issues.append(
                f"Daily allocation {daily_allocation} exceeds maximum "
                f"${self.MAX_DAILY_ALLOCATION} - CRITICAL ERROR"
            )
            score = 0.0

        # Check if order was validated before execution
        validated = trade_result.get("validated", False)
        if not validated:
            issues.append("Order was not validated before execution")
            score = min(score, 0.8)

        # Check if pre-flight checks passed
        preflight_passed = trade_result.get("preflight_passed", True)
        if not preflight_passed:
            issues.append("Pre-flight checks failed")
            score = min(score, 0.5)

        return EvaluationResult(
            dimension="compliance",
            score=score,
            passed=score >= 0.7,
            issues=issues,
            metadata={
                "daily_allocation": daily_allocation,
                "validated": validated,
                "preflight_passed": preflight_passed,
            },
        )

    def _evaluate_reliability(self, trade_result: dict[str, Any]) -> EvaluationResult:
        """
        Evaluate system reliability.

        Checks:
        - System state freshness (<24h old)
        - Data source reliability (prefer Alpaca/Polygon over Alpha Vantage)
        - API errors present
        - Execution time reasonable (<30s)

        Args:
            trade_result: Trade execution result dictionary

        Returns:
            EvaluationResult with reliability score and issues
        """
        issues = []
        score = 1.0

        # Check system state freshness
        system_state_age_hours = trade_result.get("system_state_age_hours")
        if system_state_age_hours is not None:
            logger.debug(f"System state age: {system_state_age_hours:.1f} hours")
            if system_state_age_hours > self.MAX_STALENESS_HOURS:
                error_msg = (
                    f"System state is {system_state_age_hours:.1f} hours old "
                    f"(max: {self.MAX_STALENESS_HOURS}h) - CRITICAL ERROR"
                )
                issues.append(error_msg)
                score = 0.0
                logger.error(
                    f"CRITICAL ERROR PATTERN #2: {error_msg} | "
                    f"Symbol: {trade_result.get('symbol', 'UNKNOWN')}"
                )

        # Check data source reliability
        data_source = trade_result.get("data_source", "unknown")
        if data_source == "alpha_vantage":
            # Alpha Vantage is unreliable, should use Alpaca/Polygon first
            issues.append("Used Alpha Vantage (unreliable source)")
            score = min(score, 0.6)

        # Check for API errors
        api_errors = trade_result.get("api_errors", [])
        if api_errors:
            issues.append(f"API errors encountered: {api_errors}")
            score = min(score, 0.5)

        # Check execution time
        execution_time_ms = trade_result.get("execution_time_ms")
        if execution_time_ms and execution_time_ms > 30000:  # 30 seconds
            issues.append(f"Execution took {execution_time_ms}ms (slow)")
            score = min(score, 0.8)

        return EvaluationResult(
            dimension="reliability",
            score=score,
            passed=score >= 0.7,
            issues=issues,
            metadata={
                "system_state_age_hours": system_state_age_hours,
                "data_source": data_source,
                "api_errors": api_errors,
                "execution_time_ms": execution_time_ms,
            },
        )

    def _detect_errors(
        self, trade_result: dict[str, Any], expected_amount: float
    ) -> EvaluationResult:
        """
        Detect known error patterns from documented mistakes.

        Patterns detected:
        - Pattern #1: Order size >10x expected (Mistake #1)
        - Pattern #2: System state stale (Mistake #2)
        - Pattern #3: Network/DNS errors (Mistake #3)
        - Pattern #4: Wrong script executed (Mistake #1)
        - Pattern #5: Calendar errors - weekend trades (Mistake #5)

        Args:
            trade_result: Trade execution result dictionary
            expected_amount: Expected trade amount in dollars

        Returns:
            EvaluationResult with detected error patterns
        """
        errors = []
        score = 1.0

        # Check for known error patterns
        actual_amount = trade_result.get("amount", 0.0)

        # Pattern 1: Order size >10x expected (Mistake #1)
        if actual_amount > expected_amount * self.MAX_ORDER_MULTIPLIER:
            errors.append(
                f"ERROR PATTERN #1: Order size {actual_amount} is "
                f">{self.MAX_ORDER_MULTIPLIER}x expected ({expected_amount})"
            )
            score = 0.0

        # Pattern 2: System state stale (Mistake #2)
        system_state_age_hours = trade_result.get("system_state_age_hours")
        if system_state_age_hours and system_state_age_hours > self.MAX_STALENESS_HOURS:
            errors.append(
                f"ERROR PATTERN #2: System state stale ({system_state_age_hours:.1f}h old)"
            )
            score = min(score, 0.0)

        # Pattern 3: Network/DNS errors (Mistake #3)
        api_errors = trade_result.get("api_errors", [])
        if any("network" in str(e).lower() or "dns" in str(e).lower() for e in api_errors):
            errors.append("ERROR PATTERN #3: Network/DNS errors detected")
            score = min(score, 0.3)
            logger.warning(
                f"ERROR PATTERN #3 detected: Network/DNS errors | "
                f"Symbol: {trade_result.get('symbol', 'UNKNOWN')} | "
                f"Errors: {api_errors}"
            )

        # Pattern 4: Wrong script executed (Mistake #1)
        script_name = trade_result.get("script_name", "")
        if (
            script_name
            and "main.py" not in script_name
            and "autonomous_trader.py" not in script_name
        ):
            errors.append(f"ERROR PATTERN #4: Wrong script executed ({script_name})")
            score = min(score, 0.5)

        # Pattern 5: Calendar/date errors (Mistake #5)
        trade_date = trade_result.get("date", "")
        if trade_date:
            try:
                trade_dt = datetime.fromisoformat(trade_date.replace("Z", "+00:00"))
                if trade_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    errors.append(f"ERROR PATTERN #5: Trade on weekend ({trade_date})")
                    score = min(score, 0.5)
            except Exception:
                pass

        return EvaluationResult(
            dimension="errors",
            score=score,
            passed=len(errors) == 0,
            issues=errors,
            metadata={"error_count": len(errors)},
        )

    def save_evaluation(self, evaluation: TradeEvaluation) -> Path:
        """
        Save evaluation to disk (JSON format).

        Saves to: data/evaluations/evaluations_YYYY-MM-DD.json

        Args:
            evaluation: TradeEvaluation object to save

        Returns:
            Path to saved evaluation file
        """
        """
        Save evaluation to disk (JSON format).

        Saves to: data/evaluations/evaluations_YYYY-MM-DD.json

        Args:
            evaluation: TradeEvaluation object to save

        Returns:
            Path to saved evaluation file
        """
        today = date.today().isoformat()
        eval_file = self.eval_dir / f"evaluations_{today}.json"

        # Load existing evaluations
        evaluations = []
        if eval_file.exists():
            try:
                with open(eval_file) as f:
                    evaluations = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading existing evaluations: {e}")

        # Add new evaluation
        evaluations.append(asdict(evaluation))

        # Save
        with open(eval_file, "w") as f:
            json.dump(evaluations, f, indent=2)

        logger.info(f"Saved evaluation to {eval_file}")
        return eval_file

    def get_evaluation_summary(self, days: int = 7) -> dict[str, Any]:
        """
        Get summary of recent evaluations.

        Aggregates evaluation results from last N days and provides:
        - Total evaluations count
        - Pass/fail statistics
        - Average score
        - Critical issues list
        - Error pattern counts

        Args:
            days: Number of days to look back (default: 7)

        Returns:
            Dictionary with summary statistics and aggregated data
        """
        summary = {
            "period_days": days,
            "total_evaluations": 0,
            "passed": 0,
            "failed": 0,
            "avg_score": 0.0,
            "critical_issues": [],
            "error_patterns": {},
        }

        # Load evaluations from last N days
        cutoff_date = date.today() - timedelta(days=days)
        evaluations = []

        logger.debug(f"Loading evaluations from last {days} days (since {cutoff_date})")

        for eval_file in self.eval_dir.glob("evaluations_*.json"):
            try:
                file_date_str = eval_file.stem.replace("evaluations_", "")
                file_date = datetime.fromisoformat(file_date_str).date()
                if file_date >= cutoff_date:
                    with open(eval_file) as f:
                        file_evaluations = json.load(f)
                        evaluations.extend(file_evaluations)
                        logger.debug(
                            f"Loaded {len(file_evaluations)} evaluations from {eval_file.name}"
                        )
            except Exception as e:
                logger.warning(f"Error loading {eval_file}: {e}", exc_info=True)

        if not evaluations:
            return summary

        summary["total_evaluations"] = len(evaluations)
        summary["passed"] = sum(1 for e in evaluations if e.get("passed", False))
        summary["failed"] = summary["total_evaluations"] - summary["passed"]

        scores = [e.get("overall_score", 0.0) for e in evaluations]
        summary["avg_score"] = sum(scores) / len(scores) if scores else 0.0

        # Collect critical issues
        for eval_data in evaluations:
            summary["critical_issues"].extend(eval_data.get("critical_issues", []))

        # Count error patterns
        for eval_data in evaluations:
            errors = eval_data.get("evaluation", {}).get("errors", {})
            error_issues = errors.get("issues", [])
            for issue in error_issues:
                if "ERROR PATTERN" in issue:
                    pattern_num = issue.split("#")[1].split(":")[0] if "#" in issue else "unknown"
                    summary["error_patterns"][pattern_num] = (
                        summary["error_patterns"].get(pattern_num, 0) + 1
                    )

        return summary
