import logging
from typing import Any

import torch
from src.ml.data_processor import DataProcessor
from src.ml.trainer import ModelTrainer

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Inference engine for the LSTM-PPO model.
    Provides a clean API for the Orchestrator to get trading signals.
    """

    def __init__(self, models_dir: str = "models/ml"):
        self.trainer = ModelTrainer(models_dir=models_dir)
        self.data_processor = DataProcessor()
        self.models = {}  # Cache loaded models

    def get_signal(self, symbol: str) -> dict[str, Any]:
        """
        Get a trading signal for the given symbol.

        Returns:
            Dict containing:
            - action: "BUY", "SELL", or "HOLD"
            - confidence: float (probability of the action)
            - value_estimate: float (critic's valuation of current state)
        """
        # 1. Load Model (Lazy Loading)
        if symbol not in self.models:
            self.models[symbol] = self.trainer.load_model(symbol)
            self.models[symbol].eval()

        model = self.models[symbol]

        # 2. Prepare Data
        # We need the most recent sequence of data
        input_tensor = self.data_processor.prepare_inference_data(symbol)

        if input_tensor is None:
            logger.warning(f"Could not generate inference data for {symbol}")
            return {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}

        # 3. Inference
        with torch.no_grad():
            # action_probs: [1, 3] (Hold, Buy, Sell)
            # state_value: [1, 1]
            action_probs, state_value, _ = model(input_tensor)

        probs = action_probs.squeeze().tolist()  # [p_hold, p_buy, p_sell]
        value = state_value.item()

        # 4. Decode Action
        # Index 0: Hold, 1: Buy, 2: Sell
        actions = ["HOLD", "BUY", "SELL"]
        best_action_idx = action_probs.argmax().item()
        best_action = actions[best_action_idx]
        confidence = probs[best_action_idx]

        logger.info(f"ML Signal for {symbol}: {best_action} ({confidence:.2f}), Value: {value:.2f}")

        return {
            "action": best_action,
            "confidence": confidence,
            "value_estimate": value,
            "probs": {"HOLD": probs[0], "BUY": probs[1], "SELL": probs[2]},
        }
