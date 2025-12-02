#!/usr/bin/env python3
"""
Continuous Training System - Automated RL Model Training
Runs both local and cloud RL training on a schedule.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

from src.ml.trainer import ModelTrainer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/continuous_training.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Training configuration
TRAINING_SYMBOLS = ["SPY", "QQQ", "NVDA", "GOOGL", "AMZN"]
TRAINING_STATUS_FILE = Path("data/training_status.json")


class ContinuousTrainer:
    """Manages continuous training of RL models (local + cloud)."""

    def __init__(
        self,
        symbols: list[str] = None,
        train_local: bool = True,
        train_cloud: bool = True,
        retrain_interval_days: int = 7,
    ):
        """
        Initialize continuous trainer.

        Args:
            symbols: List of symbols to train
            train_local: Enable local training
            train_cloud: Enable cloud RL training
            retrain_interval_days: Days between retraining
        """
        self.symbols = symbols or TRAINING_SYMBOLS
        self.train_local = train_local
        self.train_cloud = train_cloud
        self.retrain_interval_days = retrain_interval_days

        # Initialize trainers
        self.local_trainer = None
        self.cloud_trainer = None

        if self.train_local:
            self.local_trainer = ModelTrainer(use_cloud_rl=False)
            logger.info("✅ Local trainer initialized")

        if self.train_cloud:
            try:
                self.cloud_trainer = ModelTrainer(use_cloud_rl=True, rl_provider="vertex_ai")
                logger.info("✅ Cloud trainer initialized")
            except Exception as e:
                logger.warning(f"⚠️  Cloud trainer initialization failed: {e}")
                self.train_cloud = False

        # Load training status
        self.status = self._load_status()

    def _load_status(self) -> dict[str, Any]:
        """Load training status from file."""
        if TRAINING_STATUS_FILE.exists():
            try:
                with open(TRAINING_STATUS_FILE) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load training status: {e}")

        return {"last_training": {}, "training_history": [], "cloud_jobs": {}}

    def _save_status(self):
        """Save training status to file."""
        TRAINING_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRAINING_STATUS_FILE, "w") as f:
            json.dump(self.status, f, indent=2, default=str)

    def _should_retrain(self, symbol: str) -> bool:
        """Check if symbol should be retrained."""
        last_training = self.status.get("last_training", {}).get(symbol)

        if not last_training:
            return True

        try:
            last_date = datetime.fromisoformat(last_training)
            days_since = (datetime.now() - last_date).days
            return days_since >= self.retrain_interval_days
        except Exception:
            return True

    def train_symbol_local(self, symbol: str) -> dict[str, Any]:
        """Train symbol locally."""
        if not self.local_trainer:
            return {"success": False, "error": "Local trainer not initialized"}

        logger.info(f"🏠 Training {symbol} locally...")

        try:
            result = self.local_trainer.train_supervised(symbol, use_cloud_rl=False)

            if result.get("success"):
                logger.info(f"✅ Local training completed for {symbol}")
                logger.info(f"   Validation loss: {result.get('final_val_loss', 'N/A'):.4f}")
            else:
                logger.error(f"❌ Local training failed for {symbol}: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"❌ Error in local training for {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol}

    def train_symbol_cloud(self, symbol: str) -> dict[str, Any]:
        """Train symbol in cloud RL service."""
        if not self.cloud_trainer:
            return {"success": False, "error": "Cloud trainer not initialized"}

        logger.info(f"☁️  Training {symbol} in cloud RL...")

        try:
            result = self.cloud_trainer.train_supervised(symbol, use_cloud_rl=True)

            if result.get("success"):
                job_id = result.get("job_id")
                logger.info(f"✅ Cloud RL job submitted for {symbol}")
                logger.info(f"   Job ID: {job_id}")
                logger.info(f"   Provider: {result.get('provider')}")

                # Track cloud job
                self.status["cloud_jobs"][job_id] = {
                    "symbol": symbol,
                    "submitted_at": datetime.now().isoformat(),
                    "status": result.get("status", "submitted"),
                    "provider": result.get("provider"),
                }
            else:
                logger.error(f"❌ Cloud training failed for {symbol}: {result.get('error')}")

            return result

        except Exception as e:
            logger.error(f"❌ Error in cloud training for {symbol}: {e}")
            return {"success": False, "error": str(e), "symbol": symbol}

    def train_all(self, force: bool = False) -> dict[str, Any]:
        """
        Train all symbols (local + cloud).

        Args:
            force: Force retraining even if not due

        Returns:
            Training results summary
        """
        logger.info("=" * 80)
        logger.info("🚀 STARTING CONTINUOUS TRAINING")
        logger.info("=" * 80)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Local training: {'✅' if self.train_local else '❌'}")
        logger.info(f"Cloud training: {'✅' if self.train_cloud else '❌'}")
        logger.info("")

        results = {
            "timestamp": datetime.now().isoformat(),
            "symbols": {},
            "summary": {
                "total": len(self.symbols),
                "local_success": 0,
                "cloud_success": 0,
                "local_failed": 0,
                "cloud_failed": 0,
            },
        }

        for symbol in self.symbols:
            logger.info(f"📈 Processing {symbol}...")
            logger.info("-" * 80)

            symbol_results = {"symbol": symbol}

            # Check if retraining needed
            if not force and not self._should_retrain(symbol):
                last_training = self.status.get("last_training", {}).get(symbol)
                logger.info(f"⏭️  Skipping {symbol} - last trained: {last_training}")
                symbol_results["skipped"] = True
                symbol_results["reason"] = f"Last trained: {last_training}"
                results["symbols"][symbol] = symbol_results
                continue

            # Local training
            if self.train_local:
                local_result = self.train_symbol_local(symbol)
                symbol_results["local"] = local_result

                if local_result.get("success"):
                    results["summary"]["local_success"] += 1
                else:
                    results["summary"]["local_failed"] += 1

            # Cloud training
            if self.train_cloud:
                cloud_result = self.train_symbol_cloud(symbol)
                symbol_results["cloud"] = cloud_result

                if cloud_result.get("success"):
                    results["summary"]["cloud_success"] += 1
                else:
                    results["summary"]["cloud_failed"] += 1

            # Update last training time
            if symbol_results.get("local", {}).get("success") or symbol_results.get(
                "cloud", {}
            ).get("success"):
                self.status["last_training"][symbol] = datetime.now().isoformat()

            results["symbols"][symbol] = symbol_results
            logger.info("")

        # Save status
        self.status["training_history"].append(results)
        # Keep only last 100 training runs
        if len(self.status["training_history"]) > 100:
            self.status["training_history"] = self.status["training_history"][-100:]
        self._save_status()

        # Print summary
        logger.info("=" * 80)
        logger.info("📊 TRAINING SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total symbols: {results['summary']['total']}")
        logger.info(
            f"Local: {results['summary']['local_success']} success, {results['summary']['local_failed']} failed"
        )
        logger.info(
            f"Cloud: {results['summary']['cloud_success']} success, {results['summary']['cloud_failed']} failed"
        )
        logger.info("")

        return results

    def get_status(self) -> dict[str, Any]:
        """Get current training status."""
        return {
            "last_training": self.status.get("last_training", {}),
            "cloud_jobs": self.status.get("cloud_jobs", {}),
            "next_retrain": {
                symbol: (
                    (
                        datetime.fromisoformat(self.status["last_training"][symbol])
                        + timedelta(days=self.retrain_interval_days)
                    ).isoformat()
                    if symbol in self.status.get("last_training", {})
                    else "immediately"
                )
                for symbol in self.symbols
            },
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Continuous RL Model Training")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=TRAINING_SYMBOLS,
        help="Symbols to train (default: SPY QQQ NVDA GOOGL AMZN)",
    )
    parser.add_argument("--local-only", action="store_true", help="Train only locally (skip cloud)")
    parser.add_argument(
        "--cloud-only", action="store_true", help="Train only in cloud (skip local)"
    )
    parser.add_argument("--force", action="store_true", help="Force retraining even if not due")
    parser.add_argument("--status", action="store_true", help="Show training status and exit")
    parser.add_argument(
        "--interval", type=int, default=7, help="Days between retraining (default: 7)"
    )

    args = parser.parse_args()

    # Determine training modes
    train_local = not args.cloud_only
    train_cloud = not args.local_only and os.getenv("RL_AGENT_KEY") is not None

    # Initialize trainer
    trainer = ContinuousTrainer(
        symbols=args.symbols,
        train_local=train_local,
        train_cloud=train_cloud,
        retrain_interval_days=args.interval,
    )

    # Show status if requested
    if args.status:
        status = trainer.get_status()
        print(json.dumps(status, indent=2))
        return 0

    # Run training
    try:
        results = trainer.train_all(force=args.force)

        # Save results summary
        results_file = Path("data/training_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"✅ Training complete - results saved to {results_file}")

        return (
            0
            if results["summary"]["local_success"] + results["summary"]["cloud_success"] > 0
            else 1
        )

    except Exception as e:
        logger.error(f"❌ Training failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
