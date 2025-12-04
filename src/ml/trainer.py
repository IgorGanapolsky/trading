import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import torch
import torch.nn as nn
import torch.optim as optim
from src.ml.data_processor import DataProcessor
# NOTE: LSTMPPO networks have been removed - this trainer is for offline use only
# from src.ml.networks import LSTMPPO

logger = logging.getLogger(__name__)

# WARNING: This trainer module is for OFFLINE model training only
# The production system uses RLFilter (Gate 2) and TransformerRLPolicy
# LSTM-PPO models and ensemble RL have been removed from production


class ModelTrainer:
    """
    DEPRECATED: Handles training and retraining of the LSTM-PPO model.

    WARNING: This class is BROKEN and for OFFLINE use only.
    The LSTM-PPO networks have been removed from production.

    Production system uses:
    - RLFilter (Gate 2) with TransformerRLPolicy
    - RLPolicyLearner (simple Q-learning)

    DO NOT USE THIS CLASS unless you restore the LSTM-PPO networks.
    """

    def __init__(
        self,
        models_dir: str = "models/ml",
        device: str = "cpu",
        use_cloud_rl: bool = False,
        rl_provider: str = "vertex_ai",
    ):
        raise NotImplementedError(
            "ModelTrainer is DEPRECATED. LSTM-PPO networks have been removed. "
            "Use RLFilter or TransformerRLPolicy instead."
        )
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.device = torch.device(device)
        self.data_processor = DataProcessor()

        # Cloud RL service integration
        self.use_cloud_rl = use_cloud_rl and os.getenv("RL_AGENT_KEY") is not None
        self.rl_client = None

        if self.use_cloud_rl:
            try:
                from src.ml.rl_service_client import RLServiceClient

                self.rl_client = RLServiceClient(provider=rl_provider)
                logger.info(f"✅ Cloud RL service enabled ({rl_provider})")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize cloud RL service: {e}")
                logger.warning("   Falling back to local training only")
                self.use_cloud_rl = False

        # Hyperparameters (can be overridden by hyperparameter optimization)
        self.input_dim = len(self.data_processor.feature_columns)
        self.hidden_dim = 128
        self.num_layers = 2
        self.learning_rate = 0.001
        self.batch_size = 32
        self.epochs = 50

        # Load optimized hyperparameters if available
        self._load_optimized_hyperparameters()

    def train_supervised(self, symbol: str, use_cloud_rl: Optional[bool] = None) -> dict[str, Any]:
        """
        Pre-train the model using supervised learning (predicting price direction).
        This stabilizes the LSTM features before RL fine-tuning.

        Args:
            symbol: Stock symbol to train on
            use_cloud_rl: Override instance setting for cloud RL (None = use instance default)

        Returns:
            Training results dictionary
        """
        use_cloud = use_cloud_rl if use_cloud_rl is not None else self.use_cloud_rl

        if use_cloud and self.rl_client:
            return self._train_with_cloud_rl(symbol)

        logger.info(f"Starting supervised training for {symbol} (local mode)")

        # 1. Prepare Data
        df = self.data_processor.fetch_data(symbol, period="5y")
        if df.empty:
            return {"success": False, "error": "No data"}

        df = self.data_processor.add_technical_indicators(df)

        # Ensure all feature columns exist before normalization
        for col in self.data_processor.feature_columns:
            if col not in df.columns:
                logger.warning(f"Feature column {col} missing, filling with 0.0")
                df[col] = 0.0

        df = self.data_processor.normalize_data(df)

        # Create targets: 1 if next Close > current Close, else 0
        # We shift returns back by 1 to align 'current features' with 'next return'
        targets = (df["Returns"].shift(-1) > 0).astype(int).values

        # Create sequences
        X_tensor = self.data_processor.create_sequences(df)

        # Align targets with sequences (drop last row as it has no target, and align with sequence end)
        # X has length N - seq_len
        # targets should correspond to the day AFTER the sequence ends
        valid_len = len(X_tensor)
        # We need targets starting from index (seq_len - 1) up to end-1
        # Actually, create_sequences returns X[i : i+seq_len]. The target for this sequence is target[i + seq_len - 1] (next day return)
        # Let's simplify: just take the last valid_len targets
        y_tensor = torch.LongTensor(
            targets[
                self.data_processor.sequence_length : self.data_processor.sequence_length
                + valid_len
            ]
        )

        if len(X_tensor) == 0 or len(y_tensor) == 0:
            return {"success": False, "error": "Insufficient data for sequences"}

        # Split Train/Val
        train_size = int(0.8 * len(X_tensor))
        X_train, X_val = X_tensor[:train_size], X_tensor[train_size:]
        y_train, y_val = y_tensor[:train_size], y_tensor[train_size:]

        # 2. Initialize Model (use ensemble if enabled)
        use_ensemble = os.getenv("USE_ENSEMBLE_RL", "false").lower() == "true"
        ensemble_model = None

        if use_ensemble:
            # NOTE: Ensemble RL has been removed from production
            logger.warning("⚠️ Ensemble RL has been removed. Falling back to single model.")
            use_ensemble = False
            ensemble_model = None

        if not use_ensemble:
            model_to_train = LSTMPPO(
                input_dim=self.input_dim,
                hidden_dim=self.hidden_dim,
                num_layers=self.num_layers,
            ).to(self.device)

        optimizer = optim.Adam(model_to_train.parameters(), lr=self.learning_rate)
        criterion = nn.CrossEntropyLoss()  # For classification (Up/Down)

        # 3. Training Loop
        best_val_loss = float("inf")

        for epoch in range(self.epochs):
            model_to_train.train()
            optimizer.zero_grad()

            # Forward pass (using only Actor head for classification pre-training)
            # We ignore the Critic head for now
            action_probs, _, _ = model_to_train(X_train.to(self.device))

            # We map 3 actions (0:Hold, 1:Buy, 2:Sell) to 2 targets (0:Down, 1:Up)
            # For pre-training, let's just use a separate linear layer or project action_probs
            # Simplified: We treat Action 1 (Buy) as Up, Action 2 (Sell) as Down. Action 0 (Hold) is ignored or mapped.
            # Better approach for pre-training: Add a temporary classification head or just train the LSTM + Actor
            # Let's assume: Index 1 is Buy (Up), Index 2 is Sell (Down). We ignore Hold (0) for binary targets?
            # Or simpler: Just train it to output 2 classes.
            # To keep architecture consistent, let's just use the first 2 outputs of Actor for Up/Down?
            # No, let's stick to the architecture. We want the Actor to learn "Buy" when price goes up.
            # So Target 1 (Up) -> Action 1 (Buy). Target 0 (Down) -> Action 2 (Sell).

            # Map binary targets to Action indices: 0->2 (Sell), 1->1 (Buy)
            y_train_mapped = torch.where(y_train == 1, torch.tensor(1), torch.tensor(2)).to(
                self.device
            )
            y_val_mapped = torch.where(y_val == 1, torch.tensor(1), torch.tensor(2)).to(self.device)

            loss = criterion(action_probs, y_train_mapped)
            loss.backward()
            optimizer.step()

            # Validation
            model_to_train.eval()
            with torch.no_grad():
                val_probs, _, _ = model_to_train(X_val.to(self.device))
                val_loss = criterion(val_probs, y_val_mapped)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                if use_ensemble and ensemble_model:
                    ensemble_model.save(symbol)  # Ensemble saves all models
                else:
                    self.save_model(model_to_train, symbol)

            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}: Train Loss {loss.item():.4f}, Val Loss {val_loss.item():.4f}"
                )

        return {
            "success": True,
            "symbol": symbol,
            "final_val_loss": best_val_loss.item(),
            "timestamp": datetime.now().isoformat(),
        }

    def save_model(self, model: nn.Module, symbol: str):
        """Save model weights."""
        path = self.models_dir / f"{symbol}_lstm_ppo.pt"
        torch.save(model.state_dict(), path)
        logger.info(f"Saved best model for {symbol} to {path}")

    def load_model(self, symbol: str) -> LSTMPPO:
        """Load model weights."""
        path = self.models_dir / f"{symbol}_lstm_ppo.pt"
        model = LSTMPPO(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
        )
        if path.exists():
            model.load_state_dict(torch.load(path, map_location=self.device))
            model.to(self.device)
            logger.info(f"Loaded model for {symbol}")
        else:
            logger.warning(f"No existing model found for {symbol}, returning initialized model")
        return model

    def retrain_all(self, symbols: list) -> dict[str, Any]:
        """
        Retrain models for all symbols.
        This is the entry point for the 'Dynamic Retraining' pipeline.
        """
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.train_supervised(symbol)
            except Exception as e:
                logger.error(f"Failed to retrain {symbol}: {e}")
                results[symbol] = {"success": False, "error": str(e)}
        return results

    def _train_with_cloud_rl(self, symbol: str) -> dict[str, Any]:
        """
        Train model using cloud RL service (Vertex AI RL).

        Args:
            symbol: Stock symbol to train on

        Returns:
            Training results dictionary
        """
        logger.info(f"Starting cloud RL training for {symbol}")

        # Prepare environment specification for RL service
        env_spec = {
            "name": f"trading_env_{symbol.lower()}",
            "state_space": "continuous",
            "action_space": "discrete",
            "actions": ["BUY", "SELL", "HOLD"],
            "state_dim": self.input_dim,
            "reward_function": "risk_adjusted",  # Use world-class risk-adjusted reward
            "symbol": symbol,
            "features": self.data_processor.feature_columns,
        }

        # Submit training job to cloud RL service
        try:
            job_info = self.rl_client.start_training(
                env_spec=env_spec,
                algorithm="PPO",  # Use PPO for LSTM-PPO architecture
                job_name=f"lstm_ppo_{symbol.lower()}",
            )

            logger.info(f"✅ Cloud RL training job submitted: {job_info['job_id']}")

            return {
                "success": True,
                "symbol": symbol,
                "training_mode": "cloud_rl",
                "job_id": job_info["job_id"],
                "provider": job_info.get("provider", "unknown"),
                "status": job_info.get("status", "submitted"),
                "timestamp": datetime.now().isoformat(),
                "message": f"Training job submitted to {job_info.get('provider', 'cloud')} RL service",
            }

        except Exception as e:
            logger.error(f"❌ Cloud RL training failed: {e}")
            logger.info("   Falling back to local training...")

            # Fallback to local training
            return self.train_supervised(symbol, use_cloud_rl=False)

    def _load_optimized_hyperparameters(self):
        """Load optimized hyperparameters if available."""
        try:
            from src.ml.hyperparameter_optimizer import HyperparameterOptimizer

            optimizer = HyperparameterOptimizer()
            # Try to load for a generic symbol (can be made symbol-specific)
            best_params = optimizer.get_best_params()
            if best_params:
                self.hidden_dim = best_params.get("hidden_dim", self.hidden_dim)
                self.num_layers = best_params.get("num_layers", self.num_layers)
                self.learning_rate = best_params.get("learning_rate", self.learning_rate)
                self.batch_size = best_params.get("batch_size", self.batch_size)
                logger.info(f"✅ Loaded optimized hyperparameters: {best_params}")
        except Exception as e:
            logger.debug(f"Could not load optimized hyperparameters: {e}")
