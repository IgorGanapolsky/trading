#!/usr/bin/env python3
"""
Data Integrity Validator

Validates all financial claims and data consistency across the system.
Run this before generating reports to catch false claims.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.data_validator import DataValidator

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Run data integrity validation."""
    print("=" * 80)
    print("DATA INTEGRITY VALIDATION")
    print("=" * 80)
    print()

    validator = DataValidator()

    # 1. Check data consistency
    print("1. Checking data consistency...")
    consistency_results = validator.check_data_consistency()
    if consistency_results:
        print("   ❌ INCONSISTENCIES FOUND:")
        for result in consistency_results:
            print(f"      {result.error_message}")
        return 1
    else:
        print("   ✅ Data is consistent between sources")

    print()

    # 2. Validate current profit
    print("2. Validating current profit...")
    current_profit = validator.get_current_total_profit()
    print(f"   Current Total P/L: ${current_profit:+.2f}")

    # 3. Validate yesterday's profit
    print()
    print("3. Validating yesterday's profit...")
    yesterday_profit = validator.get_yesterday_profit()
    if yesterday_profit is not None:
        print(f"   Yesterday's P/L: ${yesterday_profit:+.2f}")

        # Test common false claims
        test_claims = [14.01, 10.00, 20.00]
        print()
        print("   Testing common false claims:")
        for claim in test_claims:
            result = validator.validate_yesterday_profit(claim)
            status = "✅" if result.is_valid else "❌"
            print(f"   {status} Claim: ${claim:.2f} → Actual: ${result.actual_value:.2f}")
            if not result.is_valid:
                print(f"      Error: {result.error_message}")
    else:
        print("   ⚠️  No data for yesterday")

    print()
    print("=" * 80)
    print("✅ DATA INTEGRITY VALIDATION COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
