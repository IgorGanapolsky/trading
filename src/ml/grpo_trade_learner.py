"""
Group Relative Policy Optimization (GRPO) for Trading.

Implements GRPO with verifiable rewards based on Sebastian Raschka's work.
Key insight: Eliminates the critic model by using verifiable rewards.

For trading:
- Verifiable reward = trade P/L (profit = positive, loss = negative)
- Policy outputs optimal trade parameters (delta, DTE, entry timing)
- Self-improves without human feedback (the market is the feedback)

Reference: https://magazine.sebastianraschka.com/p/llm-training-rlhf-and-its-alternatives

Architecture:
    Input Features -> Policy Network -> Trade Parameters -> Trade -> P/L Reward -> Policy Update

The key GRPO formula:
    L(theta) = E[A(s,a) * log(pi(a|s))]

Where:
    - A(s,a) = R(s,a) - mean(R) (group-relative advantage)
    - R(s,a) = normalized P/L (verifiable reward)
    - pi(a|s) = policy network output
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Optional PyTorch import for neural network
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
MODELS_DIR = PROJECT_DIR / "models" / "ml"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "grpo_trade_policy.pt"
METADATA_PATH = MODELS_DIR / "grpo_trade_metadata.json"


@dataclass
class TradeFeatures:
    """Input features for trade decision."""

    vix_level: float  # Current VIX
    vix_percentile: float  # VIX percentile (0-1)
    vix_term_structure: float  # VIX/VXV ratio (>1.0 = Backwardation/Danger)
    spy_20d_return: float  # 20-day momentum
    spy_5d_return: float  # 5-day momentum
    hour_of_day: float  # Normalized 0-1 (9:30=0, 16:00=1)
    day_of_week: float  # Normalized 0-1 (Mon=0, Fri=1)
    days_to_expiry: float  # Current option DTE
    put_call_ratio: float  # Market sentiment

    def to_tensor(self) -> "torch.Tensor":
        """Convert to PyTorch tensor."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        return torch.tensor(
            [
                self.vix_level / 50.0,  # Normalize VIX
                self.vix_percentile,
                self.vix_term_structure,
                self.spy_20d_return * 10,  # Scale returns
                self.spy_5d_return * 10,
                self.hour_of_day,
                self.day_of_week,
                self.days_to_expiry / 60.0,  # Normalize DTE
                self.put_call_ratio,
            ],
            dtype=torch.float32,
        )

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(
            [
                self.vix_level / 50.0,
                self.vix_percentile,
                self.vix_term_structure,
                self.spy_20d_return * 10,
                self.spy_5d_return * 10,
                self.hour_of_day,
                self.day_of_week,
                self.days_to_expiry / 60.0,
                self.put_call_ratio,
            ],
            dtype=np.float32,
        )


@dataclass
class TradeParams:
    """Output trade parameters from policy."""

    delta: float  # Short strike delta (0.10-0.25)
    dte: int  # Days to expiration (21-60)
    entry_hour: float  # Optimal entry time (0-1 normalized)
    exit_profit_pct: float  # Exit at X% of max profit (0.25-0.75)
    confidence: float  # Model confidence in recommendation

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 3),
            "dte": self.dte,
            "entry_hour": round(self.entry_hour, 2),
            "exit_profit_pct": round(self.exit_profit_pct, 2),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class TradeRecord:
    """Record of a trade for learning."""

    features: TradeFeatures
    params: TradeParams
    pnl: float  # P/L in dollars
    pnl_pct: float  # P/L as percentage of credit
    outcome: str  # "win" or "loss"
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "features": {
                "vix_level": self.features.vix_level,
                "vix_percentile": self.features.vix_percentile,
                "spy_20d_return": self.features.spy_20d_return,
                "spy_5d_return": self.features.spy_5d_return,
                "hour_of_day": self.features.hour_of_day,
                "day_of_week": self.features.day_of_week,
                "days_to_expiry": self.features.days_to_expiry,
                "put_call_ratio": self.features.put_call_ratio,
            },
            "params": self.params.to_dict(),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
        }


if TORCH_AVAILABLE:

    class TradePolicyNetwork(nn.Module):
        """
        Policy network that outputs trade parameters.

        Architecture:
        - Input: 9 market features (vix, percentile, term_structure, returns, etc.)
        - Hidden: 2 layers with ReLU
        - Output: 4 parameters (delta, dte, entry_hour, exit_pct)
        """

        def __init__(self, input_dim: int = 9, hidden_dim: int = 32):
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, 4),  # delta, dte, entry_hour, exit_pct
            )

            # Output bounds
            self.delta_bounds = (0.10, 0.25)
            self.dte_bounds = (21, 60)
            self.entry_bounds = (0.0, 1.0)
            self.exit_bounds = (0.25, 0.75)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            Forward pass through policy network.

            Returns raw outputs before bounding.
            """
            return self.network(x)

        def get_params(self, x: torch.Tensor) -> tuple[torch.Tensor, TradeParams]:
            """
            Get trade parameters with proper bounds applied.

            Returns both raw tensor and structured TradeParams.
            """
            raw = self.forward(x)

            # Apply sigmoid and scale to bounds
            delta = (
                torch.sigmoid(raw[0]) * (self.delta_bounds[1] - self.delta_bounds[0])
                + self.delta_bounds[0]
            )
            dte = (
                torch.sigmoid(raw[1]) * (self.dte_bounds[1] - self.dte_bounds[0])
                + self.dte_bounds[0]
            )
            entry = torch.sigmoid(raw[2])
            exit_pct = (
                torch.sigmoid(raw[3]) * (self.exit_bounds[1] - self.exit_bounds[0])
                + self.exit_bounds[0]
            )

            # Confidence from average certainty
            confidence = torch.sigmoid(raw).mean().item()

            params = TradeParams(
                delta=delta.item(),
                dte=int(dte.item()),
                entry_hour=entry.item(),
                exit_profit_pct=exit_pct.item(),
                confidence=confidence,
            )

            return raw, params


class GRPOTradeLearner:
    """
    GRPO-based trade parameter optimizer.

    Uses Group Relative Policy Optimization to learn optimal trade parameters
    from historical trade outcomes. The key innovation is using verifiable
    rewards (actual P/L) instead of a learned critic model.

    Usage:
        learner = GRPOTradeLearner()
        learner.load_trade_history()
        learner.train_policy(epochs=100)
        params = learner.predict_optimal_params(current_features)
    """

    def __init__(
        self,
        learning_rate: float = 0.001,
        batch_size: int = 16,
        gamma: float = 0.99,
        group_size: int = 8,
    ):
        """
        Initialize GRPO learner.

        Args:
            learning_rate: Learning rate for policy optimizer
            batch_size: Batch size for training
            gamma: Discount factor for rewards
            group_size: Number of samples for group-relative comparison
        """
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.gamma = gamma
        self.group_size = group_size

        self.trade_history: list[TradeRecord] = []
        self.training_stats: dict[str, list] = {
            "epoch": [],
            "loss": [],
            "avg_reward": [],
            "win_rate": [],
        }

        if TORCH_AVAILABLE:
            self.policy = TradePolicyNetwork()
            self.optimizer = optim.Adam(self.policy.parameters(), lr=learning_rate)
        else:
            self.policy = None
            self.optimizer = None
            logger.warning("PyTorch not available. Using fallback mode.")

        # Fallback parameters when no model available
        self._fallback_params = TradeParams(
            delta=0.15,
            dte=30,
            entry_hour=0.5,
            exit_profit_pct=0.50,
            confidence=0.5,
        )

        self._load_model()

    def load_trade_history(self, file_path: Optional[Path] = None) -> int:
        """
        Load trade history from system_state.json.

        Args:
            file_path: Optional override path. Defaults to data/system_state.json

        Returns:
            Number of trades loaded
        """
        if file_path is None:
            file_path = DATA_DIR / "system_state.json"

        if not file_path.exists():
            logger.warning(f"Trade history file not found: {file_path}")
            return 0

        try:
            with open(file_path) as f:
                state = json.load(f)

            raw_trades = state.get("trade_history", [])
            self.trade_history = self._process_raw_trades(raw_trades)

            logger.info(
                f"Loaded {len(self.trade_history)} processed trades from {len(raw_trades)} raw trades"
            )
            return len(self.trade_history)

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load trade history: {e}")
            return 0

    def _process_raw_trades(self, raw_trades: list[dict]) -> list[TradeRecord]:
        """
        Process raw trade records into TradeRecord objects.

        Groups related option trades (iron condor legs) and calculates net P/L.
        """
        processed = []

        # Group trades by date (approximation for iron condors)
        trades_by_date: dict[str, list[dict]] = {}
        for trade in raw_trades:
            if trade.get("symbol") is None:
                continue  # Skip null symbol trades

            filled_at = trade.get("filled_at", "")
            if not filled_at:
                continue

            # Extract date
            date_key = filled_at[:10]
            if date_key not in trades_by_date:
                trades_by_date[date_key] = []
            trades_by_date[date_key].append(trade)

        # Process each day's trades
        for date_key, day_trades in trades_by_date.items():
            # Calculate net P/L for the day's option trades
            option_trades = [
                t
                for t in day_trades
                if "P0" in str(t.get("symbol", "")) or "C0" in str(t.get("symbol", ""))
            ]

            if not option_trades:
                continue

            # Sum up P/L (positive = credit received, negative = debit paid)
            net_pnl = 0.0
            for trade in option_trades:
                price = float(trade.get("price", 0))
                qty = float(trade.get("qty", 0))
                side = str(trade.get("side", ""))

                # SELL = credit (positive), BUY = debit (negative)
                if "SELL" in side.upper():
                    net_pnl += price * qty * 100  # Options are 100 shares
                elif "BUY" in side.upper():
                    net_pnl -= price * qty * 100

            # Extract features (estimated from limited data)
            features = self._estimate_features_from_trade(option_trades[0], date_key)

            # Estimate parameters from the trade symbols
            params = self._estimate_params_from_trades(option_trades)

            # Determine outcome
            outcome = "win" if net_pnl > 0 else "loss"
            pnl_pct = (
                net_pnl / (params.delta * 500 * 100) if params.delta > 0 else 0
            )  # Rough credit estimate

            try:
                timestamp = datetime.fromisoformat(date_key)
            except ValueError:
                timestamp = datetime.now()

            record = TradeRecord(
                features=features,
                params=params,
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                outcome=outcome,
                timestamp=timestamp,
            )
            processed.append(record)

        return processed

    def _estimate_features_from_trade(self, trade: dict, date_key: str) -> TradeFeatures:
        """Estimate market features at time of trade."""
        # Default features
        filled_at = trade.get("filled_at", "")

        # Check for embedded indicators (new regime-aware format)
        indicators = trade.get("indicators", {})
        vix_level = float(indicators.get("vix", 18.0))

        # Extract hour from timestamp
        hour = 0.5  # Default to mid-day
        if len(filled_at) > 11:
            try:
                hour_str = filled_at[11:13]
                hour_int = int(hour_str)
                # Normalize: 9:30 = 0, 16:00 = 1
                hour = (hour_int - 9.5) / 6.5
                hour = max(0, min(1, hour))
            except ValueError:
                pass

        # Estimate day of week
        try:
            dt = datetime.fromisoformat(date_key)
            day_of_week = dt.weekday() / 4  # 0=Mon, 4=Fri -> 0-1
        except ValueError:
            day_of_week = 0.5

        # Extract DTE from symbol if possible
        symbol = str(trade.get("symbol", ""))
        dte = 30  # Default
        if len(symbol) > 12:
            # SPY260227P00655000 -> 260227 is expiry
            try:
                exp_str = symbol[3:9]
                exp_year = 2000 + int(exp_str[:2])
                exp_month = int(exp_str[2:4])
                exp_day = int(exp_str[4:6])
                exp_date = datetime(exp_year, exp_month, exp_day)
                trade_date = datetime.fromisoformat(date_key)
                dte = (exp_date - trade_date).days
            except (ValueError, IndexError):
                pass

        return TradeFeatures(
            vix_level=18.0,  # Default - would query historical VIX
            vix_percentile=0.5,
            vix_term_structure=0.9,  # Default Contango
            spy_20d_return=0.0,
            spy_5d_return=0.0,
            hour_of_day=hour,
            day_of_week=day_of_week,
            days_to_expiry=float(dte),
            put_call_ratio=1.0,
        )

    def _estimate_params_from_trades(self, trades: list[dict]) -> TradeParams:
        """Estimate trade parameters from trade symbols."""
        # Extract strike info from symbols
        delta = 0.15  # Default
        dte = 30

        for trade in trades:
            symbol = str(trade.get("symbol", ""))
            if len(symbol) > 12:
                try:
                    # SPY260227P00655000 -> strike = 655.0
                    strike_str = symbol[10:18]
                    strike = float(strike_str) / 1000

                    # Estimate delta from strike distance
                    # Rough approximation: SPY ~690, so 655 strike is ~35 points OTM
                    # At 0.15 delta, that's roughly 5% OTM
                    spy_price = 690  # Approximate current price
                    otm_pct = abs(strike - spy_price) / spy_price
                    # Map OTM% to delta (very rough)
                    if otm_pct < 0.03:
                        delta = 0.25
                    elif otm_pct < 0.05:
                        delta = 0.20
                    elif otm_pct < 0.07:
                        delta = 0.15
                    else:
                        delta = 0.10

                    # Extract DTE
                    exp_str = symbol[3:9]
                    exp_year = 2000 + int(exp_str[:2])
                    exp_month = int(exp_str[2:4])
                    exp_day = int(exp_str[4:6])
                    exp_date = datetime(exp_year, exp_month, exp_day)
                    dte = (exp_date - datetime.now()).days
                    dte = max(1, min(60, dte))
                    break

                except (ValueError, IndexError):
                    continue

        return TradeParams(
            delta=delta,
            dte=dte,
            entry_hour=0.5,
            exit_profit_pct=0.50,
            confidence=0.5,
        )

    def calculate_rewards(self) -> np.ndarray:
        """
        Calculate normalized rewards from trade P/L with Phil Town Rule #1 Penalty.

        GRPO uses group-relative rewards. We enhance this by:
        1. Multiplied penalty for losses (Rule #1: Don't Lose Money).
        2. Normalized advantage.
        """
        if not self.trade_history:
            return np.array([])

        # Get raw P/L values and apply Rule #1 Weighting
        # Losses are 2x more 'impactful' than wins
        raw_pnls = np.array([t.pnl for t in self.trade_history])
        weighted_pnls = np.array(
            [p * 2.0 if p < 0 else p for p in raw_pnls]
        )

        if len(weighted_pnls) < 2:
            return weighted_pnls

        # Group-relative normalization
        mean_pnl = np.mean(weighted_pnls)
        std_pnl = np.std(weighted_pnls)

        if std_pnl > 0:
            rewards = (weighted_pnls - mean_pnl) / std_pnl
        else:
            rewards = weighted_pnls - mean_pnl

        # Clip extreme values
        rewards = np.clip(rewards, -3.0, 3.0)

        return rewards

    def train_policy(self, epochs: int = 100) -> dict[str, Any]:
        """
        Train the policy network using GRPO.

        GRPO loss:
            L = -E[A(s,a) * log(pi(a|s))]

        Where A(s,a) is the group-relative advantage.

        Args:
            epochs: Number of training epochs

        Returns:
            Training statistics
        """
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available. Cannot train policy.")
            return {"error": "PyTorch not available"}

        if len(self.trade_history) < self.batch_size:
            logger.warning(
                f"Insufficient trades ({len(self.trade_history)}) for training. Need at least {self.batch_size}."
            )
            return {"error": f"Need at least {self.batch_size} trades"}

        # Calculate rewards
        rewards = self.calculate_rewards()

        # Prepare training data
        features = [t.features.to_tensor() for t in self.trade_history]
        features_tensor = torch.stack(features)

        rewards_tensor = torch.tensor(rewards, dtype=torch.float32)

        logger.info(f"Training GRPO policy on {len(self.trade_history)} trades for {epochs} epochs")

        self.policy.train()
        best_loss = float("inf")

        for epoch in range(epochs):
            epoch_loss = 0.0

            # Mini-batch training
            n_batches = max(1, len(features) // self.batch_size)
            indices = np.random.permutation(len(features))

            for batch_idx in range(n_batches):
                start = batch_idx * self.batch_size
                end = min(start + self.batch_size, len(features))
                batch_indices = indices[start:end]

                if len(batch_indices) < 2:
                    continue

                batch_features = features_tensor[batch_indices]
                batch_rewards = rewards_tensor[batch_indices]

                # Group-relative advantage within batch
                batch_mean = batch_rewards.mean()
                batch_std = batch_rewards.std() + 1e-8
                advantages = (batch_rewards - batch_mean) / batch_std

                # Forward pass
                self.optimizer.zero_grad()
                outputs = self.policy(batch_features)

                # GRPO loss: negative advantage-weighted log probability
                # Using MSE proxy since we're predicting continuous params
                target_scaled = advantages.unsqueeze(1).expand_as(outputs)
                loss = -torch.mean(target_scaled * torch.log_softmax(outputs, dim=1))

                # Add regularization to keep params in valid ranges
                reg_loss = 0.01 * torch.mean(outputs**2)
                total_loss = loss + reg_loss

                # Backward pass
                total_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
                self.optimizer.step()

                epoch_loss += total_loss.item()

            avg_loss = epoch_loss / max(1, n_batches)

            # Log progress
            if epoch % 10 == 0 or epoch == epochs - 1:
                win_rate = sum(1 for t in self.trade_history if t.outcome == "win") / len(
                    self.trade_history
                )
                avg_reward = rewards.mean()

                self.training_stats["epoch"].append(epoch)
                self.training_stats["loss"].append(avg_loss)
                self.training_stats["avg_reward"].append(float(avg_reward))
                self.training_stats["win_rate"].append(win_rate)

                logger.info(
                    f"Epoch {epoch}: loss={avg_loss:.4f}, avg_reward={avg_reward:.3f}, win_rate={win_rate:.1%}"
                )

            # Save best model
            if avg_loss < best_loss:
                best_loss = avg_loss
                self.save_model()

        self.policy.eval()

        return {
            "epochs": epochs,
            "final_loss": float(avg_loss),
            "best_loss": float(best_loss),
            "trades_used": len(self.trade_history),
            "win_rate": sum(1 for t in self.trade_history if t.outcome == "win")
            / len(self.trade_history),
        }

    def predict_optimal_params(self, features: Optional[TradeFeatures] = None) -> TradeParams:
        """
        Predict optimal trade parameters given current market features.

        Args:
            features: Current market features. If None, uses defaults.

        Returns:
            Optimal trade parameters
        """
        if features is None:
            features = self._get_default_features()

        if not TORCH_AVAILABLE or self.policy is None:
            logger.warning("Using fallback parameters (PyTorch not available)")
            return self._fallback_params

        self.policy.eval()
        with torch.no_grad():
            input_tensor = features.to_tensor()
            _, params = self.policy.get_params(input_tensor)

        return params

    def _get_default_features(self) -> TradeFeatures:
        """Get default features from current market data."""
        # Try to load from system_state.json
        state_file = DATA_DIR / "system_state.json"

        now = datetime.now()
        hour = (now.hour - 9.5) / 6.5
        hour = max(0, min(1, hour))
        day_of_week = now.weekday() / 4

        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)
                market = state.get("market_context", {})
                return TradeFeatures(
                    vix_level=market.get("vix", 18.0),
                    vix_percentile=0.5,
                    vix_term_structure=0.9,
                    spy_20d_return=market.get("spy_20d_return", 0.0),
                    spy_5d_return=market.get("spy_5d_return", 0.0),
                    hour_of_day=hour,
                    day_of_week=day_of_week,
                    days_to_expiry=30.0,
                    put_call_ratio=1.0,
                )
            except (json.JSONDecodeError, KeyError):
                pass

        return TradeFeatures(
            vix_level=18.0,
            vix_percentile=0.5,
            vix_term_structure=0.9,
            spy_20d_return=0.0,
            spy_5d_return=0.0,
            hour_of_day=hour,
            day_of_week=day_of_week,
            days_to_expiry=30.0,
            put_call_ratio=1.0,
        )

    def save_model(self) -> Path:
        """
        Save trained model to disk.

        Returns:
            Path to saved model
        """
        if TORCH_AVAILABLE and self.policy is not None:
            torch.save(
                {
                    "model_state_dict": self.policy.state_dict(),
                    "optimizer_state_dict": self.optimizer.state_dict(),
                    "training_stats": self.training_stats,
                },
                MODEL_PATH,
            )

        # Save metadata
        metadata = {
            "updated_at": datetime.now().isoformat(),
            "torch_available": TORCH_AVAILABLE,
            "trades_trained_on": len(self.trade_history),
            "training_stats": self.training_stats,
            "fallback_params": self._fallback_params.to_dict(),
            "config": {
                "learning_rate": self.learning_rate,
                "batch_size": self.batch_size,
                "gamma": self.gamma,
                "group_size": self.group_size,
            },
        }
        METADATA_PATH.write_text(json.dumps(metadata, indent=2))

        logger.info(f"Model saved to {MODEL_PATH}")
        return MODEL_PATH

    def _load_model(self) -> bool:
        """
        Load trained model from disk.

        Returns:
            True if model loaded successfully
        """
        if not MODEL_PATH.exists():
            logger.info("No existing GRPO model found. Starting fresh.")
            return False

        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available. Cannot load model.")
            return False

        try:
            checkpoint = torch.load(MODEL_PATH, weights_only=True)
            self.policy.load_state_dict(checkpoint["model_state_dict"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            self.training_stats = checkpoint.get("training_stats", self.training_stats)
            logger.info(f"Loaded GRPO model from {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def load_model(self) -> bool:
        """Public method to load model."""
        return self._load_model()

    def get_learning_summary(self) -> dict[str, Any]:
        """
        Get summary of learned patterns and recommendations.

        Returns:
            Summary dict with learned insights
        """
        if not self.trade_history:
            return {"error": "No trade history loaded"}

        # Analyze winning vs losing trades
        wins = [t for t in self.trade_history if t.outcome == "win"]
        losses = [t for t in self.trade_history if t.outcome == "loss"]

        # Average features for wins vs losses
        win_features = {}
        loss_features = {}

        if wins:
            win_arrays = [w.features.to_array() for w in wins]
            win_mean = np.mean(win_arrays, axis=0)
            for i, name in enumerate(
                ["vix", "vix_pct", "20d_ret", "5d_ret", "hour", "dow", "dte", "pcr"]
            ):
                win_features[name] = float(win_mean[i])

        if losses:
            loss_arrays = [loss.features.to_array() for loss in losses]
            loss_mean = np.mean(loss_arrays, axis=0)
            for i, name in enumerate(
                ["vix", "vix_pct", "20d_ret", "5d_ret", "hour", "dow", "dte", "pcr"]
            ):
                loss_features[name] = float(loss_mean[i])

        # Calculate profit factor safely
        total_win_pnl = sum(w.pnl for w in wins) if wins else 0
        total_loss_pnl = sum(loss.pnl for loss in losses) if losses else 0
        profit_factor = abs(total_win_pnl / total_loss_pnl) if total_loss_pnl != 0 else 0

        return {
            "total_trades": len(self.trade_history),
            "win_rate": (len(wins) / len(self.trade_history) if self.trade_history else 0),
            "avg_win_pnl": np.mean([w.pnl for w in wins]) if wins else 0,
            "avg_loss_pnl": np.mean([loss.pnl for loss in losses]) if losses else 0,
            "profit_factor": profit_factor,
            "winning_conditions": win_features,
            "losing_conditions": loss_features,
            "model_status": "trained" if MODEL_PATH.exists() else "untrained",
            "torch_available": TORCH_AVAILABLE,
        }


def get_optimal_trade_params(features: Optional[TradeFeatures] = None) -> TradeParams:
    """
    Quick access to get optimal trade parameters.

    This is the main entry point for the trading workflow.
    """
    learner = GRPOTradeLearner()
    return learner.predict_optimal_params(features)


async def train_grpo_model() -> dict[str, Any]:
    """
    Train the GRPO model using historical trade data.

    Called by research agent or scheduled workflow.
    """
    learner = GRPOTradeLearner()

    # Load trade history
    n_trades = learner.load_trade_history()
    if n_trades == 0:
        return {"error": "No trades to learn from"}

    # Train policy
    results = learner.train_policy(epochs=100)

    # Get learning summary
    summary = learner.get_learning_summary()

    return {
        "training_results": results,
        "learning_summary": summary,
        "model_path": str(MODEL_PATH),
    }


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("GRPO TRADE LEARNER")
    print(f"PyTorch Available: {TORCH_AVAILABLE}")
    print("=" * 60)

    # Train and evaluate
    result = asyncio.run(train_grpo_model())

    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    # Get optimal params
    print("\n" + "=" * 60)
    print("OPTIMAL PARAMETERS")
    print("=" * 60)
    params = get_optimal_trade_params()
    print(json.dumps(params.to_dict(), indent=2))
