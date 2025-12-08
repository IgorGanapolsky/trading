"""
ML Inference Engine

Uses Medallion Architecture by default for data quality guarantees.
Falls back to legacy DataProcessor if Medallion is disabled.
"""

import logging
import os
from typing import Any

import torch

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    Inference engine for ML models.
    Provides a clean API for the Orchestrator to get trading signals.

    Uses Medallion Architecture by default for data quality guarantees.
    """

    def __init__(self, models_dir: str = "models/ml"):
        self.models_dir = models_dir
        self.models = {}  # Cache loaded models

        # Use Medallion by default
        self.use_medallion = os.getenv("USE_MEDALLION_ARCHITECTURE", "true").lower() == "true"

        if self.use_medallion:
            try:
                from src.ml.medallion_trainer import MedallionMLPredictor
                self._medallion_predictor = MedallionMLPredictor(models_dir=models_dir)
                logger.info("MLPredictor using Medallion Architecture for data quality")
            except Exception as e:
                logger.warning(f"Failed to init Medallion predictor: {e}, using legacy")
                self.use_medallion = False
                self._init_legacy()
        else:
            self._init_legacy()

    def _init_legacy(self):
        """Initialize legacy components."""
        from src.ml.data_processor import DataProcessor
        self.data_processor = DataProcessor()
        logger.info("MLPredictor using legacy DataProcessor")

    def get_signal(self, symbol: str) -> dict[str, Any]:
        """
        Get a trading signal for the given symbol.

        Returns:
            Dict containing:
            - action: "BUY", "SELL", or "HOLD"
            - confidence: float (probability of the action)
            - value_estimate: float (critic's valuation of current state)
        """
        # Use Medallion predictor if available
        if self.use_medallion and hasattr(self, '_medallion_predictor'):
            try:
                return self._medallion_predictor.get_signal(symbol)
            except Exception as e:
                logger.warning(f"Medallion inference failed for {symbol}: {e}")
                # Fall through to legacy

        # Legacy path (fallback)
        return self._get_signal_legacy(symbol)

    def _get_signal_legacy(self, symbol: str) -> dict[str, Any]:
        """Legacy signal generation using old DataProcessor."""
        # 1. Load Model (Lazy Loading)
        if symbol not in self.models:
            try:
                # Try to load medallion model first
                from src.ml.medallion_trainer import MedallionTrainer
                trainer = MedallionTrainer(models_dir=self.models_dir)
                model = trainer.load_model(symbol)
                if model is not None:
                    self.models[symbol] = model
                    logger.info(f"Loaded Medallion model for {symbol}")
            except Exception:
                pass

            if symbol not in self.models:
                logger.warning(f"No model available for {symbol}")
                return {"action": "HOLD", "confidence": 0.0, "reason": "No model"}

        model = self.models[symbol]

        # 2. Prepare Data
        if not hasattr(self, 'data_processor'):
            self._init_legacy()

        input_tensor = self.data_processor.prepare_inference_data(symbol)

        if input_tensor is None:
            logger.warning(f"Could not generate inference data for {symbol}")
            return {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}

        # 3. Inference
        with torch.no_grad():
            action_probs, state_value, _ = model(input_tensor)

        probs = action_probs.squeeze().tolist()
        value = state_value.item()

        # 4. Decode Action
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
