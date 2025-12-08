#!/usr/bin/env python3
"""
Train ML Models Using Medallion Architecture

This script retrains all trading models using the new Medallion
data pipeline for improved data quality and reproducibility.

Usage:
    python scripts/train_medallion_models.py
    python scripts/train_medallion_models.py --symbols SPY QQQ
    python scripts/train_medallion_models.py --lookback 730  # 2 years

Requirements:
    pip install numpy pandas torch
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Train ML models using Medallion Architecture")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["SPY", "QQQ", "VOO"],
        help="Symbols to train models for",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=365 * 2,
        help="Days of historical data to use",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Training epochs",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    print("=" * 70)
    print("MEDALLION ARCHITECTURE - ML MODEL TRAINING")
    print("=" * 70)
    print(f"Symbols: {args.symbols}")
    print(f"Lookback: {args.lookback} days")
    print(f"Epochs: {args.epochs}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    try:
        from src.ml.medallion_trainer import MedallionTrainer

        trainer = MedallionTrainer(epochs=args.epochs)

        results = {}
        for symbol in args.symbols:
            print(f"\n{'='*40}")
            print(f"Training {symbol}")
            print("=" * 40)

            result = trainer.train_from_raw(symbol, lookback_days=args.lookback)
            results[symbol] = result

            if result.get("success"):
                print(f"✅ {symbol}: accuracy={result['final_accuracy']:.2%}")
                print(f"   Data quality: {result.get('data_quality', 0):.2%}")
                print(f"   Epochs: {result.get('epochs_trained', 0)}")
            else:
                print(f"❌ {symbol}: {result.get('error', 'Unknown error')}")

        # Summary
        print("\n" + "=" * 70)
        print("TRAINING SUMMARY")
        print("=" * 70)

        successes = sum(1 for r in results.values() if r.get("success"))
        failures = len(results) - successes

        print(f"Total: {len(results)} | Success: {successes} | Failed: {failures}")
        print()

        for symbol, result in results.items():
            status = "✅" if result.get("success") else "❌"
            if result.get("success"):
                print(
                    f"  {status} {symbol}: "
                    f"accuracy={result['final_accuracy']:.2%}, "
                    f"quality={result.get('data_quality', 0):.2%}"
                )
            else:
                print(f"  {status} {symbol}: {result.get('error', 'Failed')}")

        print("\n" + "=" * 70)
        print(f"Completed: {datetime.now().isoformat()}")
        print("Models saved to: models/ml/")
        print("=" * 70)

        return 0 if failures == 0 else 1

    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all dependencies are installed:")
        logger.error("  pip install numpy pandas torch")
        return 1
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
