#!/usr/bin/env python3
"""
Autonomous Model Training Orchestrator

This script automates the training of deep learning models for the trading system.
It can be run manually or scheduled via cron/GitHub Actions.

Features:
- Automatic data collection verification
- Model training with best practices
- Performance monitoring
- Automatic retraining when needed
- Integration with workflow orchestrator

Usage:
    python scripts/autonomous_model_training.py
    python scripts/autonomous_model_training.py --check-only  # Just check data
    python scripts/autonomous_model_training.py --force-retrain  # Force retrain even if model exists
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / ".claude" / "skills" / "model_trainer" / "scripts"))

from model_trainer import ModelTrainerSkill
from src.utils.data_collector import DataCollector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Autonomous model training main function."""
    parser = argparse.ArgumentParser(description="Autonomous Model Training")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check data availability, don't train",
    )
    parser.add_argument(
        "--force-retrain",
        action="store_true",
        help="Force retraining even if model exists",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ,VOO",
        help="Comma-separated symbols (default: SPY,QQQ,VOO)",
    )
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs (default: 50)")

    args = parser.parse_args()

    print("=" * 70)
    print("Autonomous Model Training Orchestrator")
    print("=" * 70)
    print(f"Symbols: {args.symbols}")
    print(f"Mode: {'CHECK ONLY' if args.check_only else 'TRAIN'}")
    print("=" * 70)

    skill = ModelTrainerSkill()
    symbols = [s.strip() for s in args.symbols.split(",")]

    # Step 1: Check data availability
    print("\n[Step 1] Checking training data availability...")
    data_check = skill.check_training_data_availability(symbols, min_days=252)

    if not data_check["available"]:
        print("\n❌ Insufficient data for training:")
        print(f"   Missing symbols: {data_check['missing_symbols']}")
        print("\n   Collecting data automatically...")

        # Automatically collect data
        collector = DataCollector(data_dir="data/historical")
        collector.collect_daily_data(symbols, lookback_days=252)

        # Re-check
        data_check = skill.check_training_data_availability(symbols, min_days=252)
        if not data_check["available"]:
            print("\n❌ Still insufficient data after collection")
            print("   Please ensure API keys are configured")
            sys.exit(1)

    print("✅ Data available for all symbols")
    for symbol, info in data_check["data_summary"].items():
        print(f"   {symbol}: {info['days']} days")

    if args.check_only:
        print("\n✅ Data check complete (--check-only mode)")
        return

    # Step 2: Check if model exists
    models_dir = project_root / "data" / "models"
    existing_model = list(models_dir.glob("lstm_feature_extractor*.pt"))

    if existing_model and not args.force_retrain:
        model_age = datetime.now() - datetime.fromtimestamp(existing_model[0].stat().st_mtime)
        print(f"\n[Step 2] Existing model found: {existing_model[0].name}")
        print(f"   Age: {model_age.days} days")

        # Only retrain if model is >7 days old
        if model_age.days < 7:
            print("   ✅ Model is fresh (<7 days old), skipping retraining")
            print("   Use --force-retrain to override")
            return

    # Step 3: Train model
    print("\n[Step 3] Training LSTM model...")
    result = skill.train_lstm_model(
        symbols=symbols,
        epochs=args.epochs,
        batch_size=32,
        learning_rate=0.001,
        device="cpu",
    )

    if result["success"]:
        print("\n✅ Model training complete!")
        print(f"   Model saved to: {result['model_path']}")
        print(f"   Training metrics: {result['training_metrics']}")
        print("\nNext steps:")
        print("1. Integrate with OptimizedRLPolicyLearner")
        print("2. Test on live market data")
        print("3. A/B test against current strategy")
    else:
        print(f"\n❌ Training failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
