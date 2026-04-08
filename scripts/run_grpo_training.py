"""
GRPO Training Script.

Loads trade history from data/system_state.json, trains the GRPO policy
network, saves the model, and prints results.

Usage:
    python3 scripts/run_grpo_training.py

Exit codes:
    0 — success (including graceful skip when data is insufficient)
    1 — unexpected error (import failure, file corruption, etc.)
"""

import json
import sys
from pathlib import Path

# Ensure project root is importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> int:
    """Run GRPO training. Returns exit code."""
    print("=" * 60)
    print("GRPO TRADE LEARNER")
    print("=" * 60)

    # --- Import guard -------------------------------------------------------
    try:
        from src.ml.grpo_trade_learner import (
            TORCH_AVAILABLE,
            GRPOTradeLearner,
            get_optimal_trade_params,
        )
    except ImportError as exc:
        print(f"ERROR: Could not import GRPOTradeLearner: {exc}")
        print("Ensure you are running from the project root or that src/ is on PYTHONPATH.")
        return 1

    print(f"PyTorch Available: {TORCH_AVAILABLE}")
    print()

    # --- Initialise learner -------------------------------------------------
    try:
        learner = GRPOTradeLearner()
    except Exception as exc:
        print(f"ERROR: Failed to initialise GRPOTradeLearner: {exc}")
        return 1

    # --- Load trade history -------------------------------------------------
    try:
        n_trades = learner.load_trade_history()
    except Exception as exc:
        print(f"ERROR: Failed to load trade history: {exc}")
        return 1

    print(f"Trades loaded: {n_trades}")

    if n_trades == 0:
        print("No trade history found. Skipping training (nothing to learn from).")
        print("\nOptimal Parameters (defaults — no training data):")
        params = get_optimal_trade_params()
        print(json.dumps(params.to_dict(), indent=2))
        print("\nDone. Exit 0 (no training performed).")
        return 0

    # batch_size default is 16; reflect that gracefully.
    if n_trades < learner.batch_size:
        print(
            f"Insufficient trades for training: {n_trades} loaded, "
            f"{learner.batch_size} required (batch_size)."
        )
        print("Skipping training. Accumulate more closed trades and re-run.")
        print("\nOptimal Parameters (defaults — insufficient data):")
        params = get_optimal_trade_params()
        print(json.dumps(params.to_dict(), indent=2))
        print("\nDone. Exit 0 (no training performed).")
        return 0

    # --- Train policy -------------------------------------------------------
    print(f"\nTraining GRPO policy on {n_trades} trades …")
    try:
        training_results = learner.train_policy(epochs=100)
    except Exception as exc:
        print(f"ERROR: Training failed: {exc}")
        return 1

    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    print(json.dumps(training_results, indent=2, default=str))

    # --- Save model ---------------------------------------------------------
    if "error" not in training_results:
        try:
            model_path = learner.save_model()
            print(f"\nModel saved: {model_path}")
        except Exception as exc:
            print(f"WARNING: Could not save model: {exc}")
            # Non-fatal — training succeeded even if save failed.

    # --- Learning summary ---------------------------------------------------
    try:
        summary = learner.get_learning_summary()
        print("\n" + "=" * 60)
        print("LEARNING SUMMARY")
        print("=" * 60)
        print(json.dumps(summary, indent=2, default=str))
    except Exception as exc:
        print(f"WARNING: Could not retrieve learning summary: {exc}")

    # --- Optimal parameters -------------------------------------------------
    print("\n" + "=" * 60)
    print("OPTIMAL PARAMETERS")
    print("=" * 60)
    try:
        params = get_optimal_trade_params()
        print(json.dumps(params.to_dict(), indent=2))
    except Exception as exc:
        print(f"WARNING: Could not compute optimal parameters: {exc}")

    print("\nDone. Exit 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
