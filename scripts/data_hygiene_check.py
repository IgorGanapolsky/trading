#!/usr/bin/env python3
"""
Data Hygiene Check Script

Comprehensive data quality and staleness validation.
Can be run manually or integrated into CI/CD pipeline.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.data_collector import DataCollector
from src.utils.data_hygiene import DataHygieneChecker

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """CLI interface for data hygiene checks."""
    parser = argparse.ArgumentParser(description="Data Hygiene Check")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate data quality")
    validate_parser.add_argument(
        "--symbols", type=str, help="Comma-separated symbols (default: all)"
    )
    validate_parser.add_argument("--min-days", type=int, default=252, help="Minimum days required")

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate old historical data")
    rotate_parser.add_argument("--max-age-days", type=int, default=365, help="Maximum age in days")
    rotate_parser.add_argument("--dry-run", action="store_true", help="Preview changes")

    # Model check command
    model_parser = subparsers.add_parser("check-models", help="Check model staleness")
    model_parser.add_argument("--model-path", type=str, help="Specific model path")

    # Cleanup models command
    cleanup_parser = subparsers.add_parser("cleanup-models", help="Clean up stale models")
    cleanup_parser.add_argument("--max-age-days", type=int, help="Maximum age in days")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    cleanup_parser.add_argument(
        "--keep-latest", action="store_true", default=True, help="Keep latest model"
    )

    # Full check command
    full_parser = subparsers.add_parser("full-check", help="Run full hygiene check")
    full_parser.add_argument("--symbols", type=str, help="Comma-separated symbols (default: all)")
    full_parser.add_argument("--output", type=str, help="Output JSON report path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    checker = DataHygieneChecker()

    if args.command == "validate":
        symbols = args.symbols.split(",") if args.symbols else None

        if symbols:
            symbols = [s.strip() for s in symbols]
        else:
            # Find all symbols
            collector = DataCollector()
            csv_files = list(checker.data_dir.glob("*.csv"))
            symbols = list(set(f.name.split("_")[0] for f in csv_files))

        print(f"\n🔍 Validating data quality for {len(symbols)} symbols...")
        print("=" * 70)

        collector = DataCollector(data_dir=str(checker.data_dir))
        all_valid = True

        for symbol in symbols:
            hist_data = collector.load_historical_data(symbol)
            validation = checker.validate_historical_data_quality(symbol, hist_data, args.min_days)

            status = "✅" if validation["valid"] else "❌"
            print(f"\n{status} {symbol}")
            print(f"   Quality Score: {validation['quality_score']:.2%}")
            print(f"   Days: {validation['metrics']['days']}")
            print(f"   Completeness: {validation['metrics']['completeness']:.1%}")

            if validation["issues"]:
                print(f"   Issues: {', '.join(validation['issues'])}")
                all_valid = False

            if validation["warnings"]:
                for warning in validation["warnings"]:
                    print(f"   ⚠️  {warning}")

        print("\n" + "=" * 70)
        if all_valid:
            print("✅ All data validation passed")
            sys.exit(0)
        else:
            print("❌ Some data validation failed")
            sys.exit(1)

    elif args.command == "rotate":
        print(f"\n🔄 Rotating historical data older than {args.max_age_days} days...")
        result = checker.rotate_old_historical_data(
            max_age_days=args.max_age_days, dry_run=args.dry_run
        )

        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Rotation Results:")
        print(f"   Files deleted: {result['files_deleted']}")
        print(f"   Space freed: {result['space_freed_mb']} MB")
        print(f"   Cutoff date: {result['cutoff_date']}")

        if result["deleted_files"]:
            print("\n   Deleted files (showing first 10):")
            for file_info in result["deleted_files"][:10]:
                print(f"      - {file_info['file']} ({file_info['data_age_days']} days old)")

    elif args.command == "check-models":
        print("\n🔍 Checking model staleness...")
        result = checker.check_model_staleness(model_path=args.model_path)

        print(f"\nModel: {result['model_path']}")
        print(f"Age: {result['age_days']} days")
        print(f"Status: {'❌ STALE' if result['stale'] else '✅ FRESH'}")
        print(f"Reason: {result['reason']}")

        if result["stale"]:
            print(f"\n⚠️  Model needs retraining (max age: {result['max_age_days']} days)")
            sys.exit(1)
        else:
            sys.exit(0)

    elif args.command == "cleanup-models":
        print("\n🧹 Cleaning up stale models...")
        result = checker.cleanup_stale_models(
            max_age_days=args.max_age_days,
            keep_latest=args.keep_latest,
            dry_run=args.dry_run,
        )

        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Cleanup Results:")
        print(f"   Files deleted: {result['files_deleted']}")
        print(f"   Space freed: {result['space_freed_mb']} MB")

        if result["deleted_files"]:
            print("\n   Deleted models:")
            for file_info in result["deleted_files"]:
                print(f"      - {file_info['file']} ({file_info['age_days']} days old)")

    elif args.command == "full-check":
        symbols = args.symbols.split(",") if args.symbols else None
        if symbols:
            symbols = [s.strip() for s in symbols]

        print("\n🔍 Running full hygiene check...")
        report = checker.run_full_hygiene_check(symbols=symbols)

        # Print summary
        print("\n" + "=" * 70)
        print("DATA HYGIENE REPORT")
        print("=" * 70)

        # Data validation summary
        valid_count = sum(1 for v in report["data_validation"].values() if v["valid"])
        total_count = len(report["data_validation"])
        print(f"\n📊 Data Validation: {valid_count}/{total_count} symbols passed")

        for symbol, validation in report["data_validation"].items():
            status = "✅" if validation["valid"] else "❌"
            print(f"   {status} {symbol}: {validation['quality_score']:.1%} quality")
            if not validation["valid"]:
                print(f"      Issues: {', '.join(validation['issues'])}")

        # Model staleness
        print(
            f"\n🤖 Model Status: {'❌ STALE' if report['model_staleness']['stale'] else '✅ FRESH'}"
        )
        if report["model_staleness"]["age_days"] is not None:
            print(f"   Age: {report['model_staleness']['age_days']} days")

        # Recommendations
        if report["recommendations"]:
            print(f"\n💡 Recommendations ({len(report['recommendations'])}):")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"   {i}. {rec}")

        # Save report if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Full report saved to: {args.output}")

        # Exit code based on issues
        if report["recommendations"] or report["model_staleness"]["stale"]:
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
