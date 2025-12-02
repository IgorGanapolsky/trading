#!/usr/bin/env python3
"""
Model Trainer Skill - Autonomous LSTM Model Training

This skill automates the training of deep learning models for the trading system.
It can be invoked by Claude agents or run autonomously via workflow orchestrator.

Usage:
    python .claude/skills/model_trainer/scripts/model_trainer.py train --symbols SPY,QQQ,VOO
    python .claude/skills/model_trainer/scripts/model_trainer.py check-data
    python .claude/skills/model_trainer/scripts/model_trainer.py schedule-retraining
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from scripts.train_lstm_features import (
    prepare_training_data,
    train_lstm_model,
)
from src.utils.data_collector import DataCollector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModelTrainerSkill:
    """Autonomous model training skill for Claude agents."""

    def __init__(self):
        self.data_dir = project_root / "data" / "historical"
        self.models_dir = project_root / "data" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.collector = DataCollector(data_dir=str(self.data_dir))

    def check_training_data_availability(
        self, symbols: list[str], min_days: int = 252
    ) -> dict[str, Any]:
        """
        Check if sufficient historical data exists for training.

        Args:
            symbols: List of symbols to check
            min_days: Minimum days required

        Returns:
            Dictionary with availability status and details
        """
        missing_symbols = []
        data_summary = {}

        for symbol in symbols:
            hist_data = self.collector.load_historical_data(symbol)

            if hist_data.empty:
                missing_symbols.append(symbol)
                data_summary[symbol] = {
                    "available": False,
                    "days": 0,
                    "status": "no_data",
                }
            elif len(hist_data) < min_days:
                missing_symbols.append(symbol)
                data_summary[symbol] = {
                    "available": False,
                    "days": len(hist_data),
                    "status": "insufficient",
                    "needed": min_days,
                }
            else:
                data_summary[symbol] = {
                    "available": True,
                    "days": len(hist_data),
                    "status": "sufficient",
                    "date_range": {
                        "start": (hist_data.index[0].isoformat() if not hist_data.empty else None),
                        "end": (hist_data.index[-1].isoformat() if not hist_data.empty else None),
                    },
                }

        available = len(missing_symbols) == 0

        return {
            "available": available,
            "missing_symbols": missing_symbols,
            "data_summary": data_summary,
            "checked_at": datetime.now().isoformat(),
        }

    def train_lstm_model(
        self,
        symbols: list[str],
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        seq_length: int = 60,
        output_path: Optional[str] = None,
        device: str = "cpu",
    ) -> dict[str, Any]:
        """
        Train LSTM feature extractor.

        Args:
            symbols: List of symbols to train on
            epochs: Number of training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            seq_length: Sequence length
            output_path: Output model path (default: auto-generated)
            device: Device to train on

        Returns:
            Dictionary with training results
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.models_dir / f"lstm_feature_extractor_{timestamp}.pt")

        logger.info(f"Starting LSTM training for symbols: {symbols}")

        # Check data availability
        data_check = self.check_training_data_availability(symbols, min_days=seq_length + 200)
        if not data_check["available"]:
            return {
                "success": False,
                "error": "Insufficient training data",
                "missing_symbols": data_check["missing_symbols"],
                "data_summary": data_check["data_summary"],
            }

        # Collect training data
        all_sequences = []
        all_labels = []

        for symbol in symbols:
            logger.info(f"Loading data for {symbol}...")
            hist_data = self.collector.load_historical_data(symbol)

            if hist_data.empty or len(hist_data) < seq_length + 10:
                logger.warning(f"Insufficient data for {symbol}, skipping")
                continue

            # Prepare training data
            sequences, labels = prepare_training_data(
                hist_data, seq_length=seq_length, prediction_horizon=5
            )

            if len(sequences) > 0:
                all_sequences.append(sequences)
                all_labels.append(labels)
                logger.info(f"{symbol}: {len(sequences)} sequences")

        if not all_sequences:
            return {"success": False, "error": "No training sequences created"}

        # Combine all symbols
        combined_sequences = np.concatenate(all_sequences, axis=0)
        combined_labels = np.concatenate(all_labels, axis=0)

        logger.info(f"Total training samples: {len(combined_sequences)}")

        # Train model
        try:
            model = train_lstm_model(
                combined_sequences,
                combined_labels,
                epochs=epochs,
                batch_size=batch_size,
                learning_rate=learning_rate,
                device=device,
            )

            # Save model
            from src.agents.lstm_feature_extractor import LSTMPPOWrapper

            wrapper = LSTMPPOWrapper()
            wrapper.feature_extractor = model
            wrapper.save_model(output_path)

            return {
                "success": True,
                "model_path": output_path,
                "training_metrics": {
                    "epochs": epochs,
                    "samples": len(combined_sequences),
                    "batch_size": batch_size,
                    "learning_rate": learning_rate,
                },
                "symbols_trained": symbols,
                "trained_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def schedule_retraining(
        self,
        check_interval_days: int = 7,
        performance_threshold: float = 0.9,
        auto_retrain: bool = True,
    ) -> dict[str, Any]:
        """
        Schedule automatic model retraining.

        Args:
            check_interval_days: How often to check if retraining needed
            performance_threshold: Minimum performance to avoid retraining
            auto_retrain: Whether to automatically retrain if needed

        Returns:
            Dictionary with scheduling information
        """
        # This would integrate with a scheduler (cron, APScheduler, etc.)
        # For now, return scheduling info

        next_check = datetime.now() + timedelta(days=check_interval_days)

        return {
            "scheduled": True,
            "check_interval_days": check_interval_days,
            "next_check": next_check.isoformat(),
            "auto_retrain": auto_retrain,
            "performance_threshold": performance_threshold,
        }


def main():
    """CLI interface for the skill"""
    parser = argparse.ArgumentParser(description="Model Trainer Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train LSTM model")
    train_parser.add_argument(
        "--symbols", type=str, default="SPY,QQQ,VOO", help="Comma-separated symbols"
    )
    train_parser.add_argument("--epochs", type=int, default=50)
    train_parser.add_argument("--batch-size", type=int, default=32)
    train_parser.add_argument("--learning-rate", type=float, default=0.001)
    train_parser.add_argument("--output", type=str, default=None)
    train_parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"])

    # Check data command
    check_parser = subparsers.add_parser("check-data", help="Check data availability")
    check_parser.add_argument("--symbols", type=str, default="SPY,QQQ,VOO")
    check_parser.add_argument("--min-days", type=int, default=252)

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule-retraining", help="Schedule retraining")
    schedule_parser.add_argument("--interval-days", type=int, default=7)
    schedule_parser.add_argument("--auto-retrain", action="store_true", default=True)

    args = parser.parse_args()

    skill = ModelTrainerSkill()

    if args.command == "train":
        symbols = [s.strip() for s in args.symbols.split(",")]
        result = skill.train_lstm_model(
            symbols=symbols,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            output_path=args.output,
            device=args.device,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "check-data":
        symbols = [s.strip() for s in args.symbols.split(",")]
        result = skill.check_training_data_availability(symbols, min_days=args.min_days)
        print(json.dumps(result, indent=2))

    elif args.command == "schedule-retraining":
        result = skill.schedule_retraining(
            check_interval_days=args.interval_days, auto_retrain=args.auto_retrain
        )
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
