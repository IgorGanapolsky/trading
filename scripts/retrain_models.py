#!/usr/bin/env python3
"""
Script to retrain ML models for all tracked symbols.
Intended to be run via GitHub Actions or manually.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.trainer import ModelTrainer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ModelRetraining")


def main():
    logger.info("Starting ML Model Retraining...")

    # Symbols to train
    # In a real scenario, this could be dynamic or loaded from config
    symbols = ["SPY", "QQQ", "VOO", "BND"]

    trainer = ModelTrainer()
    results = trainer.retrain_all(symbols)

    success_count = sum(1 for r in results.values() if r["success"])
    logger.info(f"Retraining complete. Success: {success_count}/{len(symbols)}")

    for symbol, result in results.items():
        if result["success"]:
            logger.info(f"✅ {symbol}: Loss {result['final_val_loss']:.4f}")
        else:
            logger.error(f"❌ {symbol}: {result.get('error')}")

    if success_count < len(symbols):
        sys.exit(1)


if __name__ == "__main__":
    main()
