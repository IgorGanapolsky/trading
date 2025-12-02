"""
Data Validator - Prevents false claims in reports and dashboards

This module validates all financial claims against actual data sources
to ensure accuracy and prevent false reporting.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
PERF_LOG_FILE = DATA_DIR / "performance_log.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    claim: str
    actual_value: float
    claimed_value: Optional[float] = None
    error_message: Optional[str] = None
    source: Optional[str] = None


class DataValidator:
    """
    Validates financial claims against actual data sources.

    Prevents false claims by:
    1. Checking all profit/loss claims against performance_log.json
    2. Validating date-specific claims (e.g., "yesterday's profit")
    3. Ensuring consistency across data sources
    4. Flagging discrepancies for manual review
    """

    def __init__(self):
        self.perf_log = self._load_perf_log()
        self.system_state = self._load_system_state()

    def _load_perf_log(self) -> list[dict]:
        """Load performance log."""
        if not PERF_LOG_FILE.exists():
            logger.warning(f"Performance log not found: {PERF_LOG_FILE}")
            return []

        try:
            with open(PERF_LOG_FILE) as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error loading performance log: {e}")
            return []

    def _load_system_state(self) -> dict:
        """Load system state."""
        if not SYSTEM_STATE_FILE.exists():
            logger.warning(f"System state not found: {SYSTEM_STATE_FILE}")
            return {}

        try:
            with open(SYSTEM_STATE_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading system state: {e}")
            return {}

    def validate_profit_claim(
        self,
        claimed_profit: float,
        date: Optional[str] = None,
        description: str = "profit",
    ) -> ValidationResult:
        """
        Validate a profit claim against actual data.

        Args:
            claimed_profit: The claimed profit amount
            date: Optional date string (YYYY-MM-DD) for date-specific claims
            description: Description of what's being validated

        Returns:
            ValidationResult with validation status
        """
        if date:
            # Validate date-specific claim
            actual_profit = self.get_profit_for_date(date)
            if actual_profit is None:
                return ValidationResult(
                    is_valid=False,
                    claim=f"{description} on {date}",
                    actual_value=0.0,
                    claimed_value=claimed_profit,
                    error_message=f"Claimed {claimed_profit:.2f} but no data found for date {date}",
                    source="performance_log.json",
                )
        else:
            # Validate current total profit
            actual_profit = self.get_current_total_profit()

        # Allow small floating point differences (0.01)
        is_valid = abs(claimed_profit - actual_profit) < 0.01

        return ValidationResult(
            is_valid=is_valid,
            claim=description,
            actual_value=actual_profit,
            claimed_value=claimed_profit,
            error_message=(
                None
                if is_valid
                else f"Claimed {claimed_profit:.2f} but actual is {actual_profit:.2f}"
            ),
            source="performance_log.json",
        )

    def validate_yesterday_profit(self, claimed_profit: float) -> ValidationResult:
        """Validate yesterday's profit claim."""
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        return self.validate_profit_claim(
            claimed_profit=claimed_profit,
            date=yesterday,
            description="yesterday's profit",
        )

    def get_profit_for_date(self, date: str) -> Optional[float]:
        """Get profit for a specific date."""
        if not self.perf_log:
            return None

        # Find entries for the date
        date_entries = [entry for entry in self.perf_log if entry.get("date") == date]

        if not date_entries:
            return None

        # Return the latest entry's P/L for that date
        latest_entry = max(date_entries, key=lambda x: x.get("timestamp", ""))
        return latest_entry.get("pl", 0.0)

    def get_current_total_profit(self) -> float:
        """Get current total profit from latest entry."""
        if not self.perf_log:
            # Fallback to system_state.json
            account = self.system_state.get("account", {})
            return account.get("total_pl", 0.0)

        latest = self.perf_log[-1]
        return latest.get("pl", 0.0)

    def get_yesterday_profit(self) -> Optional[float]:
        """Get yesterday's profit."""
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        return self.get_profit_for_date(yesterday)

    def validate_daily_profit_claim(
        self, claimed_daily_profit: float, date: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a daily profit claim (change from previous day).

        Args:
            claimed_daily_profit: Claimed daily profit change
            date: Optional date string (YYYY-MM-DD)

        Returns:
            ValidationResult
        """
        target_date = date or datetime.now().date().isoformat()

        # Get profit for target date and previous day
        target_profit = self.get_profit_for_date(target_date)
        if target_profit is None:
            return ValidationResult(
                is_valid=False,
                claim=f"daily profit on {target_date}",
                actual_value=0.0,
                claimed_value=claimed_daily_profit,
                error_message=f"No data found for date {target_date}",
                source="performance_log.json",
            )

        # Get previous day
        target_dt = datetime.fromisoformat(target_date).date()
        prev_date = (target_dt - timedelta(days=1)).isoformat()
        prev_profit = self.get_profit_for_date(prev_date)

        if prev_profit is None:
            # Can't calculate daily change without previous day
            return ValidationResult(
                is_valid=False,
                claim=f"daily profit change on {target_date}",
                actual_value=0.0,
                claimed_value=claimed_daily_profit,
                error_message=f"No data found for previous day {prev_date}",
                source="performance_log.json",
            )

        actual_daily_change = target_profit - prev_profit

        # Allow small floating point differences
        is_valid = abs(claimed_daily_profit - actual_daily_change) < 0.01

        return ValidationResult(
            is_valid=is_valid,
            claim=f"daily profit change on {target_date}",
            actual_value=actual_daily_change,
            claimed_value=claimed_daily_profit,
            error_message=(
                None
                if is_valid
                else f"Claimed {claimed_daily_profit:.2f} but actual change is {actual_daily_change:.2f}"
            ),
            source="performance_log.json",
        )

    def validate_all_claims(self, claims: dict[str, float]) -> list[ValidationResult]:
        """
        Validate multiple claims at once.

        Args:
            claims: Dictionary of claim descriptions to claimed values

        Returns:
            List of ValidationResult objects
        """
        results = []

        for description, value in claims.items():
            if "yesterday" in description.lower():
                result = self.validate_yesterday_profit(value)
            elif "daily" in description.lower() or "change" in description.lower():
                result = self.validate_daily_profit_claim(value)
            else:
                result = self.validate_profit_claim(value, description=description)

            results.append(result)

        return results

    def check_data_consistency(self) -> list[ValidationResult]:
        """
        Check consistency between performance_log.json and system_state.json.

        Returns:
            List of ValidationResult objects for any inconsistencies found
        """
        results = []

        # Get total P/L from both sources
        perf_log_pl = self.get_current_total_profit()

        account = self.system_state.get("account", {})
        system_state_pl = account.get("total_pl", 0.0)

        # Allow small differences (0.01)
        if abs(perf_log_pl - system_state_pl) >= 0.01:
            results.append(
                ValidationResult(
                    is_valid=False,
                    claim="Total P/L consistency",
                    actual_value=perf_log_pl,
                    claimed_value=system_state_pl,
                    error_message=f"performance_log.json shows {perf_log_pl:.2f} but system_state.json shows {system_state_pl:.2f}",
                    source="Both files",
                )
            )

        return results


def validate_report_claims(report_text: str) -> list[ValidationResult]:
    """
    Extract and validate profit claims from report text.

    This is a simple pattern matcher - for production, use NLP or structured extraction.

    Args:
        report_text: Text of the report to validate

    Returns:
        List of ValidationResult objects
    """
    validator = DataValidator()
    results = []

    # Simple pattern matching for common claim formats
    import re

    # Pattern: "$+14.01 yesterday" or "+$14.01 yesterday"
    yesterday_pattern = r"[\+\$]?(\d+\.\d+).*yesterday"
    matches = re.findall(yesterday_pattern, report_text, re.IGNORECASE)

    for match in matches:
        claimed_value = float(match)
        result = validator.validate_yesterday_profit(claimed_value)
        results.append(result)

    # Pattern: "profit of $X" or "P/L: $X"
    profit_pattern = r"(?:profit|P/L|P&L).*?[\+\$]?(\d+\.\d+)"
    matches = re.findall(profit_pattern, report_text, re.IGNORECASE)

    for match in matches:
        claimed_value = float(match)
        result = validator.validate_profit_claim(claimed_value, description="profit claim")
        results.append(result)

    return results


if __name__ == "__main__":
    # Test the validator
    validator = DataValidator()

    print("=" * 80)
    print("DATA VALIDATOR TEST")
    print("=" * 80)

    # Test current profit
    current_profit = validator.get_current_total_profit()
    print(f"\nCurrent Total P/L: ${current_profit:+.2f}")

    # Test yesterday's profit
    yesterday_profit = validator.get_yesterday_profit()
    if yesterday_profit is not None:
        print(f"Yesterday's P/L: ${yesterday_profit:+.2f}")

        # Test validation
        print("\n" + "=" * 80)
        print("VALIDATION TESTS")
        print("=" * 80)

        # Test false claim
        false_claim = 14.01
        result = validator.validate_yesterday_profit(false_claim)
        print(f"\nClaim: ${false_claim:.2f} yesterday")
        print(f"Actual: ${result.actual_value:.2f}")
        print(f"Valid: {result.is_valid}")
        if not result.is_valid:
            print(f"Error: {result.error_message}")

        # Test true claim
        true_claim = yesterday_profit
        result = validator.validate_yesterday_profit(true_claim)
        print(f"\nClaim: ${true_claim:.2f} yesterday")
        print(f"Actual: ${result.actual_value:.2f}")
        print(f"Valid: {result.is_valid}")

    # Check consistency
    print("\n" + "=" * 80)
    print("DATA CONSISTENCY CHECK")
    print("=" * 80)
    consistency_results = validator.check_data_consistency()
    if consistency_results:
        for result in consistency_results:
            print("\n⚠️  Inconsistency found:")
            print(f"   {result.error_message}")
    else:
        print("\n✅ Data is consistent between sources")
