"""
Medallion-Based ML Trainer

Uses Medallion Architecture for clean, validated data in ML training.
Replaces deprecated ModelTrainer with working implementation.

Key Features:
- Bronze → Silver → Gold data flow for quality assurance
- Proper train/test normalization (no data leakage)
- Simple but effective LSTM model
- Integration with RLPolicyLearner for decision-making
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.optim as optim
from src.medallion.gold import DEFAULT_CONTRACT
from src.medallion.pipeline import get_medallion_pipeline

logger = logging.getLogger(__name__)


class SimpleLSTM(nn.Module):
    """
    Simple LSTM network for trading signal prediction.

    Outputs action probabilities for [HOLD, BUY, SELL].
    """

    def __init__(
        self,
        input_dim: int = 11,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_actions: int = 3,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # LSTM encoder
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

        # Policy head (actor)
        self.policy = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_actions),
            nn.Softmax(dim=-1),
        )

        # Value head (critic)
        self.value = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: Input tensor (batch, seq_len, features)

        Returns:
            action_probs: Action probabilities (batch, 3)
            state_value: State value estimate (batch, 1)
            hidden: Final hidden state
        """
        # LSTM forward
        lstm_out, (h_n, c_n) = self.lstm(x)

        # Use last hidden state
        last_hidden = lstm_out[:, -1, :]  # (batch, hidden_dim)

        # Policy and value outputs
        action_probs = self.policy(last_hidden)
        state_value = self.value(last_hidden)

        return action_probs, state_value, h_n


class MedallionTrainer:
    """
    ML Trainer using Medallion Architecture for data quality.

    Ensures clean, validated data flows through training pipeline.
    """

    def __init__(
        self,
        models_dir: str = "models/ml",
        device: str = "cpu",
        hidden_dim: int = 64,
        num_layers: int = 2,
        learning_rate: float = 0.001,
        epochs: int = 100,
        batch_size: int = 32,
    ):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.device = torch.device(device)
        self.pipeline = get_medallion_pipeline()

        # Model hyperparameters
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size

        # Feature contract defines input dimensions
        self.input_dim = len(DEFAULT_CONTRACT.features)

        logger.info(
            f"MedallionTrainer initialized: "
            f"hidden={hidden_dim}, layers={num_layers}, lr={learning_rate}"
        )

    def train(
        self,
        symbol: str,
        train_tensor: torch.Tensor,
        test_tensor: torch.Tensor | None = None,
        patience: int = 10,
    ) -> dict[str, Any]:
        """
        Train LSTM model on Medallion-processed data.

        Args:
            symbol: Stock symbol
            train_tensor: Training data from Gold layer
            test_tensor: Optional test data for validation
            patience: Early stopping patience

        Returns:
            Training results dictionary
        """
        logger.info(f"Training model for {symbol} with {len(train_tensor)} samples")

        # Create model
        model = SimpleLSTM(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
        ).to(self.device)

        # Create labels from price movement in sequences
        # Label = 1 (BUY) if next-day Close > current Close, else 2 (SELL)
        # We infer this from the Close feature (index 0 in DEFAULT_CONTRACT)
        train_labels = self._create_labels(train_tensor)

        optimizer = optim.Adam(model.parameters(), lr=self.learning_rate)
        criterion = nn.CrossEntropyLoss()

        best_loss = float("inf")
        best_epoch = 0
        patience_counter = 0

        train_losses = []
        val_losses = []

        for epoch in range(self.epochs):
            # Training
            model.train()
            total_loss = 0.0

            # Mini-batch training
            indices = torch.randperm(len(train_tensor))

            for i in range(0, len(train_tensor), self.batch_size):
                batch_idx = indices[i : i + self.batch_size]
                batch_x = train_tensor[batch_idx].to(self.device)
                batch_y = train_labels[batch_idx].to(self.device)

                optimizer.zero_grad()
                action_probs, _, _ = model(batch_x)
                loss = criterion(action_probs, batch_y)
                loss.backward()
                optimizer.step()

                total_loss += loss.item() * len(batch_idx)

            avg_train_loss = total_loss / len(train_tensor)
            train_losses.append(avg_train_loss)

            # Validation
            if test_tensor is not None:
                model.eval()
                with torch.no_grad():
                    test_labels = self._create_labels(test_tensor)
                    action_probs, _, _ = model(test_tensor.to(self.device))
                    val_loss = criterion(action_probs, test_labels.to(self.device)).item()
                    val_losses.append(val_loss)

                    # Early stopping check
                    if val_loss < best_loss:
                        best_loss = val_loss
                        best_epoch = epoch
                        patience_counter = 0
                        self._save_model(model, symbol)
                    else:
                        patience_counter += 1
                        if patience_counter >= patience:
                            logger.info(f"Early stopping at epoch {epoch}")
                            break
            else:
                # No validation, save best training loss
                if avg_train_loss < best_loss:
                    best_loss = avg_train_loss
                    best_epoch = epoch
                    self._save_model(model, symbol)

            # Log progress
            if epoch % 10 == 0:
                val_str = f", Val: {val_losses[-1]:.4f}" if val_losses else ""
                logger.info(f"Epoch {epoch}: Train Loss {avg_train_loss:.4f}{val_str}")

        # Calculate final accuracy
        model.eval()
        with torch.no_grad():
            action_probs, _, _ = model(train_tensor.to(self.device))
            predictions = action_probs.argmax(dim=1)
            accuracy = (predictions == train_labels.to(self.device)).float().mean().item()

        results = {
            "success": True,
            "symbol": symbol,
            "epochs_trained": epoch + 1,
            "best_epoch": best_epoch,
            "best_loss": best_loss,
            "final_accuracy": accuracy,
            "train_samples": len(train_tensor),
            "test_samples": len(test_tensor) if test_tensor is not None else 0,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"Training complete for {symbol}: accuracy={accuracy:.2%}, best_loss={best_loss:.4f}"
        )

        return results

    def train_from_raw(
        self,
        symbol: str,
        lookback_days: int = 365 * 2,
        train_ratio: float = 0.8,
    ) -> dict[str, Any]:
        """
        End-to-end training from raw market data using Medallion pipeline.

        Args:
            symbol: Stock symbol
            lookback_days: Days of historical data
            train_ratio: Train/test split ratio

        Returns:
            Training results
        """
        logger.info(f"Fetching {lookback_days} days of data for {symbol}")

        # Fetch raw data
        try:
            from src.utils.market_data import get_market_data_provider

            provider = get_market_data_provider()
            result = provider.get_daily_bars(symbol, lookback_days=lookback_days)
            raw_data = result.data

            if raw_data.empty or len(raw_data) < 100:
                return {"success": False, "error": "Insufficient data"}

            logger.info(f"Fetched {len(raw_data)} rows for {symbol} from {result.source.value}")

        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return {"success": False, "error": str(e)}

        # Process through Medallion pipeline
        try:
            train_tensor, test_tensor, lineage = self.pipeline.get_training_ready(
                symbol,
                raw_data,
                source=f"training_{datetime.now().strftime('%Y%m%d')}",
                train_ratio=train_ratio,
            )

            logger.info(
                f"Medallion pipeline complete: "
                f"train={train_tensor.shape}, test={test_tensor.shape}, "
                f"quality={lineage.silver_quality_score:.2%}"
            )

        except Exception as e:
            logger.error(f"Medallion pipeline failed: {e}")
            return {"success": False, "error": str(e)}

        # Train model
        results = self.train(symbol, train_tensor, test_tensor)
        results["data_quality"] = lineage.silver_quality_score
        results["bronze_batch"] = lineage.bronze_batch_id
        results["silver_batch"] = lineage.silver_batch_id

        return results

    def train_all(
        self,
        symbols: list[str] | None = None,
        lookback_days: int = 365 * 2,
    ) -> dict[str, Any]:
        """
        Train models for all trading symbols.

        Args:
            symbols: List of symbols (default: SPY, QQQ, VOO)
            lookback_days: Historical data lookback

        Returns:
            Results for all symbols
        """
        if symbols is None:
            symbols = ["SPY", "QQQ", "VOO"]

        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.train_from_raw(symbol, lookback_days)
            except Exception as e:
                logger.error(f"Failed to train {symbol}: {e}")
                results[symbol] = {"success": False, "error": str(e)}

        return results

    def _create_labels(self, tensor: torch.Tensor) -> torch.Tensor:
        """
        Create training labels from price sequences.

        Label logic:
        - Compare last Close in sequence vs previous Close
        - If increase > 0.5%: BUY (1)
        - If decrease > 0.5%: SELL (2)
        - Otherwise: HOLD (0)
        """
        # Close is first feature in DEFAULT_CONTRACT
        close_idx = 0

        # Get Close values: last vs second-to-last in each sequence
        last_close = tensor[:, -1, close_idx]
        prev_close = tensor[:, -2, close_idx]

        # Calculate percentage change (already normalized, so use raw diff)
        pct_change = last_close - prev_close

        # Create labels with threshold
        threshold = 0.1  # Threshold on normalized values
        labels = torch.zeros(len(tensor), dtype=torch.long)
        labels[pct_change > threshold] = 1  # BUY
        labels[pct_change < -threshold] = 2  # SELL
        # Rest stays 0 = HOLD

        return labels

    def _save_model(self, model: nn.Module, symbol: str) -> None:
        """Save model weights."""
        path = self.models_dir / f"{symbol}_medallion_lstm.pt"
        torch.save(model.state_dict(), path)
        logger.debug(f"Saved model checkpoint for {symbol}")

    def load_model(self, symbol: str) -> SimpleLSTM | None:
        """Load trained model."""
        path = self.models_dir / f"{symbol}_medallion_lstm.pt"

        model = SimpleLSTM(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
        )

        if path.exists():
            model.load_state_dict(torch.load(path, map_location=self.device))
            model.to(self.device)
            model.eval()
            logger.info(f"Loaded Medallion model for {symbol}")
            return model
        else:
            logger.warning(f"No model found for {symbol}")
            return None


class MedallionMLPredictor:
    """
    ML Predictor using Medallion Architecture.

    Drop-in replacement for MLPredictor with data quality guarantees.
    """

    def __init__(self, models_dir: str = "models/ml"):
        self.models_dir = Path(models_dir)
        self.pipeline = get_medallion_pipeline()
        self.trainer = MedallionTrainer(models_dir=models_dir)
        self.models: dict[str, SimpleLSTM] = {}

        logger.info("MedallionMLPredictor initialized")

    def get_signal(self, symbol: str) -> dict[str, Any]:
        """
        Get trading signal for a symbol using Medallion-processed data.

        Returns:
            Dict with action, confidence, and metadata
        """
        # Load model (lazy loading)
        if symbol not in self.models:
            model = self.trainer.load_model(symbol)
            if model is None:
                logger.warning(f"No trained model for {symbol}, returning HOLD")
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "No trained model",
                }
            self.models[symbol] = model

        model = self.models[symbol]

        # Fetch and process data through Medallion
        try:
            from src.utils.market_data import get_market_data_provider

            provider = get_market_data_provider()
            result = provider.get_daily_bars(symbol, lookback_days=90)
            raw_data = result.data

            if raw_data.empty:
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "No market data",
                }

            # Get inference tensor through Medallion pipeline
            tensor = self.pipeline.get_inference_ready(symbol, raw_data)

            if tensor is None:
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "Insufficient data for inference",
                }

        except Exception as e:
            logger.error(f"Data fetch failed for {symbol}: {e}")
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"Data error: {e}",
            }

        # Run inference
        with torch.no_grad():
            action_probs, state_value, _ = model(tensor)

        probs = action_probs.squeeze().tolist()
        value = state_value.item()

        actions = ["HOLD", "BUY", "SELL"]
        best_action_idx = action_probs.argmax().item()
        best_action = actions[best_action_idx]
        confidence = probs[best_action_idx]

        logger.info(
            f"Medallion ML Signal for {symbol}: "
            f"{best_action} ({confidence:.2%}), Value: {value:.2f}"
        )

        return {
            "action": best_action,
            "confidence": confidence,
            "value_estimate": value,
            "probs": {"HOLD": probs[0], "BUY": probs[1], "SELL": probs[2]},
            "source": "medallion_lstm",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("MEDALLION TRAINER - TRAINING ALL SYMBOLS")
    print("=" * 80)

    trainer = MedallionTrainer()
    results = trainer.train_all(["SPY", "QQQ", "VOO"])

    print("\n" + "=" * 80)
    print("TRAINING RESULTS")
    print("=" * 80)

    for symbol, result in results.items():
        if result.get("success"):
            print(
                f"  {symbol}: ✅ accuracy={result['final_accuracy']:.2%}, "
                f"quality={result.get('data_quality', 0):.2%}"
            )
        else:
            print(f"  {symbol}: ❌ {result.get('error', 'Unknown error')}")
