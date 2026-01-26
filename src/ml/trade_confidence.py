"""
Trade Confidence Model using Thompson Sampling (ML-IMP-3).

Uses Beta distribution to estimate probability of trade success.
Updated after each trade based on win/loss outcome.

References:
- LL-247: ML System Audit identified this improvement opportunity
- Thompson Sampling: https://en.wikipedia.org/wiki/Thompson_sampling
"""

import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "ml" / "trade_confidence_model.json"


class TradeConfidenceModel:
    """
    Thompson Sampling model for trade entry confidence.

    Uses Beta distribution posterior to estimate probability of successful trade.
    Posterior = Beta(alpha, beta) where:
    - alpha = prior_alpha + wins
    - beta = prior_beta + losses

    The model is updated after each trade based on outcome.
    """

    def __init__(self):
        self.model = self._load_model()

    def _load_model(self) -> dict:
        """Load model from JSON file."""
        try:
            if MODEL_PATH.exists():
                with open(MODEL_PATH) as f:
                    return json.load(f)
            else:
                logger.warning(f"Trade confidence model not found at {MODEL_PATH}")
                return self._default_model()
        except Exception as e:
            logger.error(f"Failed to load trade confidence model: {e}")
            return self._default_model()

    def _default_model(self) -> dict:
        """Return default model with uniform priors."""
        return {
            "iron_condor": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "spy_specific": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "regime_adjustments": {
                "calm": 1.1,
                "trending": 0.9,
                "volatile": 0.8,
                "spike": 0.0,
            },
        }

    def _save_model(self):
        """Save model to JSON file."""
        try:
            self.model["last_updated"] = datetime.now().isoformat()
            with open(MODEL_PATH, "w") as f:
                json.dump(self.model, f, indent=2)
            logger.info("Trade confidence model saved")
        except Exception as e:
            logger.error(f"Failed to save trade confidence model: {e}")

    def get_posterior_mean(self, strategy: str = "iron_condor", ticker: str = "SPY") -> float:
        """
        Get posterior mean (expected probability of success).

        E[Beta(α, β)] = α / (α + β)
        """
        # Get strategy-specific parameters
        if ticker.upper() == "SPY" and "spy_specific" in self.model:
            params = self.model["spy_specific"]
        elif strategy.lower() in self.model:
            params = self.model[strategy.lower()]
        else:
            params = self.model.get("iron_condor", {"alpha": 1.0, "beta": 1.0})

        alpha = params.get("alpha", 1.0)
        beta = params.get("beta", 1.0)

        return alpha / (alpha + beta)

    def sample_confidence(
        self, strategy: str = "iron_condor", ticker: str = "SPY", regime: Optional[str] = None
    ) -> float:
        """
        Sample confidence from Thompson Sampling posterior.

        Draws from Beta(α, β) distribution and applies regime adjustment.
        """
        # Get strategy-specific parameters
        if ticker.upper() == "SPY" and "spy_specific" in self.model:
            params = self.model["spy_specific"]
        elif strategy.lower() in self.model:
            params = self.model[strategy.lower()]
        else:
            params = self.model.get("iron_condor", {"alpha": 1.0, "beta": 1.0})

        alpha = params.get("alpha", 1.0)
        beta = params.get("beta", 1.0)

        # Sample from Beta distribution
        sampled = random.betavariate(alpha, beta)

        # Apply regime adjustment if provided
        if regime:
            regime_adj = self.model.get("regime_adjustments", {})
            adjustment = regime_adj.get(regime.lower(), 1.0)
            sampled = min(1.0, sampled * adjustment)

        return round(sampled, 3)

    def get_trade_confidence(
        self, strategy: str = "iron_condor", ticker: str = "SPY", regime: Optional[str] = None
    ) -> dict:
        """
        Get trade confidence with full details.

        Returns:
            dict with posterior_mean, sampled_confidence, regime_adjustment, recommendation
        """
        posterior_mean = self.get_posterior_mean(strategy, ticker)
        sampled = self.sample_confidence(strategy, ticker, regime)

        # Get regime adjustment
        regime_adj = 1.0
        if regime:
            regime_adj = self.model.get("regime_adjustments", {}).get(regime.lower(), 1.0)

        # Recommendation based on sampled confidence
        if sampled >= 0.7:
            recommendation = "ENTER"
        elif sampled >= 0.5:
            recommendation = "CONSIDER"
        elif sampled >= 0.3:
            recommendation = "CAUTIOUS"
        else:
            recommendation = "AVOID"

        # Get win/loss stats
        params = self.model.get("iron_condor", {})
        wins = params.get("wins", 0)
        losses = params.get("losses", 0)

        return {
            "posterior_mean": round(posterior_mean, 3),
            "sampled_confidence": sampled,
            "regime_adjustment": regime_adj,
            "recommendation": recommendation,
            "wins": wins,
            "losses": losses,
            "total_trades": wins + losses,
        }

    def record_trade_outcome(
        self, success: bool, strategy: str = "iron_condor", ticker: str = "SPY"
    ):
        """
        Update model with trade outcome.

        Args:
            success: True if trade was profitable, False otherwise
            strategy: Trading strategy used
            ticker: Ticker symbol
        """
        # Update strategy-specific model
        strategy_key = strategy.lower().replace(" ", "_")
        if strategy_key not in self.model:
            self.model[strategy_key] = {
                "alpha": 1.0,
                "beta": 1.0,
                "wins": 0,
                "losses": 0,
            }

        if success:
            self.model[strategy_key]["alpha"] += 1.0
            self.model[strategy_key]["wins"] += 1
        else:
            self.model[strategy_key]["beta"] += 1.0
            self.model[strategy_key]["losses"] += 1

        # Update SPY-specific if applicable
        if ticker.upper() == "SPY" and "spy_specific" in self.model:
            if success:
                self.model["spy_specific"]["alpha"] += 1.0
                self.model["spy_specific"]["wins"] += 1
            else:
                self.model["spy_specific"]["beta"] += 1.0
                self.model["spy_specific"]["losses"] += 1

        logger.info(
            f"Trade outcome recorded: {'WIN' if success else 'LOSS'} for {strategy} on {ticker}"
        )
        self._save_model()


# Singleton instance for easy access
_trade_confidence_model = None


def get_trade_confidence_model() -> TradeConfidenceModel:
    """Get singleton instance of TradeConfidenceModel."""
    global _trade_confidence_model
    if _trade_confidence_model is None:
        _trade_confidence_model = TradeConfidenceModel()
    return _trade_confidence_model


def sample_trade_confidence(
    strategy: str = "iron_condor", ticker: str = "SPY", regime: Optional[str] = None
) -> float:
    """Quick access to sample trade confidence."""
    model = get_trade_confidence_model()
    return model.sample_confidence(strategy, ticker, regime)
