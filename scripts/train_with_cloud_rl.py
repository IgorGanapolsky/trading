#!/usr/bin/env python3
"""
Train models using cloud RL service (Vertex AI RL).
This script demonstrates how to use the cloud RL integration.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
load_dotenv()

from src.ml.trainer import ModelTrainer


def main():
    """Train models with cloud RL service."""
    parser = argparse.ArgumentParser(description="Train models with cloud RL service")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["SPY", "QQQ"],
        help="Stock symbols to train (default: SPY QQQ)",
    )
    parser.add_argument(
        "--provider",
        default="vertex_ai",
        choices=["vertex_ai", "azure_ml", "aws_sagemaker", "paperspace"],
        help="RL service provider (default: vertex_ai)",
    )
    parser.add_argument(
        "--local", action="store_true", help="Use local training instead of cloud RL"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 CLOUD RL TRAINING")
    print("=" * 80)
    print()

    # Check RL_AGENT_KEY
    if not args.local and not os.getenv("RL_AGENT_KEY"):
        print("❌ RL_AGENT_KEY not found in environment")
        print("   Set it in your .env file or use --local flag for local training")
        return 1

    # Initialize trainer
    print("🔧 Initializing trainer...")
    print(f"   Mode: {'Cloud RL' if not args.local else 'Local'}")
    print(f"   Provider: {args.provider if not args.local else 'N/A'}")
    print()

    trainer = ModelTrainer(use_cloud_rl=not args.local, rl_provider=args.provider)

    # Train each symbol
    results = {}
    for symbol in args.symbols:
        print(f"📈 Training {symbol}...")
        print("-" * 80)

        try:
            result = trainer.train_supervised(symbol)
            results[symbol] = result

            if result.get("success"):
                if result.get("training_mode") == "cloud_rl":
                    print(f"✅ Cloud RL job submitted for {symbol}")
                    print(f"   Job ID: {result.get('job_id')}")
                    print(f"   Status: {result.get('status')}")
                    print(f"   Provider: {result.get('provider')}")
                else:
                    print(f"✅ Local training completed for {symbol}")
                    print(f"   Final validation loss: {result.get('final_val_loss', 'N/A'):.4f}")
            else:
                print(f"❌ Training failed for {symbol}: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")
            results[symbol] = {"success": False, "error": str(e)}

        print()

    # Summary
    print("=" * 80)
    print("📊 TRAINING SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results.values() if r.get("success"))
    total = len(results)

    print(f"Total symbols: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    print()

    for symbol, result in results.items():
        status = "✅" if result.get("success") else "❌"
        mode = result.get("training_mode", "local")
        print(f"{status} {symbol}: {mode}")
        if result.get("job_id"):
            print(f"   Job ID: {result['job_id']}")

    return 0 if successful == total else 1


if __name__ == "__main__":
    sys.exit(main())
