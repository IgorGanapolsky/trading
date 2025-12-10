#!/usr/bin/env python3
"""
Check Stock Lending Income Status

Usage:
    python scripts/check_lending_income.py
    python scripts/check_lending_income.py --enroll
    python scripts/check_lending_income.py --record-payment 5.50
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.income.stock_lending import StockLendingTracker, get_lending_income_for_report


def main():
    parser = argparse.ArgumentParser(description="Check stock lending income status")
    parser.add_argument("--enroll", action="store_true", help="Enroll in stock lending program")
    parser.add_argument("--record-payment", type=float, help="Record a lending payment amount")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--elite", action="store_true", help="Use Elite revenue share (50%)")
    parser.add_argument("--live", action="store_true", help="Use live trading account")
    args = parser.parse_args()

    paper_trading = not args.live
    tracker = StockLendingTracker(is_elite=args.elite, paper_trading=paper_trading)

    if args.enroll:
        tracker.enroll_in_program()
        return

    if args.record_payment:
        tracker.record_payment(args.record_payment)
        return

    if args.json:
        import json
        data = get_lending_income_for_report()
        print(json.dumps(data, indent=2))
    else:
        print(tracker.generate_report())


if __name__ == "__main__":
    main()
