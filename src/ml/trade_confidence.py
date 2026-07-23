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
MIN_CONFIDENCE_SAMPLE_SIZE = 5


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
        """Return default model buckets.

        Historical note: this used Beta(86,14) from Tastytrade 15Δ IC research.
        Realized IC paper ledger (~17% WR) falsified that prior for *this* system.
        Iron condor remains as a diagnostic bucket only (family killed).

        Active successor `spy_put_credit` starts with a weak neutral prior — never
        inherits the IC research fantasy. Empirical updates come from
        `scripts/update_ml_from_trades.py`.
        """
        return {
            # Diagnostic-only: do not treat as entry authority for killed IC family
            "iron_condor": {
                "alpha": 1.0,
                "beta": 1.0,
                "wins": 0,
                "losses": 0,
                "note": "killed_family_diagnostic_bucket",
            },
            "spy_specific": {
                "alpha": 1.0,
                "beta": 1.0,
                "wins": 0,
                "losses": 0,
                "note": "legacy_spy_ic_bucket_not_put_credit",
            },
            "spy_put_credit": {
                "alpha": 1.0,
                "beta": 1.0,
                "wins": 0,
                "losses": 0,
                "prior_source": "weak_neutral_cold_start",
            },
            "active_family": "spy_put_credit",
            "regime_adjustments": {
                "calm": 1.1,  # Low VIX: slightly boost confidence
                "trending": 0.9,  # Trending market: reduce (short premium)
                "volatile": 0.8,  # High VIX: reduce
                "spike": 0.5,  # VIX spike: strongly reduce
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

    @staticmethod
    def _is_put_credit_strategy(strategy_key: str) -> bool:
        put_aliases = {
            "spy_put_credit",
            "put_credit",
            "bull_put",
            "bull_put_credit",
            "put_credit_spread",
        }
        if strategy_key in put_aliases:
            return True
        # Match put_credit family names without stealing unrelated buckets
        # like bull_put_spread used in unit tests / other underlyings.
        if "put_credit" in strategy_key:
            return True
        if strategy_key.startswith("bull_put_") and strategy_key.endswith("_credit"):
            return True
        return False

    def _resolve_params(self, strategy: str = "iron_condor", ticker: str = "SPY") -> dict:
        """Resolve the most relevant parameter bucket for the requested trade.

        Family isolation: put-credit strategies never fall through to IC /
        spy_specific buckets (that was poisoning successor confidence with
        the killed family's ~17% realized history or 86% research priors).
        """
        strategy_key = strategy.lower().replace(" ", "_").replace("-", "_")
        if self._is_put_credit_strategy(strategy_key):
            if "spy_put_credit" in self.model:
                return self.model["spy_put_credit"]
            return {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0}

        # Legacy SPY path: IC diagnostics use spy_specific when present
        if ticker.upper() == "SPY" and "spy_specific" in self.model and strategy_key in {
            "iron_condor",
            "ic_simple",
            "ic",
            "spy_specific",
            "",
        }:
            return self.model["spy_specific"]

        if strategy_key in self.model:
            return self.model[strategy_key]
        if strategy.lower() in self.model:
            return self.model[strategy.lower()]

        # Unknown non-put strategy on SPY still hits spy_specific for back-compat
        if ticker.upper() == "SPY" and "spy_specific" in self.model:
            return self.model["spy_specific"]

        return self.model.get("iron_condor", {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0})

    def get_posterior_mean(self, strategy: str = "iron_condor", ticker: str = "SPY") -> float:
        """
        Get posterior mean (expected probability of success).

        E[Beta(α, β)] = α / (α + β)
        """
        params = self._resolve_params(strategy, ticker)
        alpha = params.get("alpha", 1.0)
        beta = params.get("beta", 1.0)

        return alpha / (alpha + beta)

    def sample_confidence(
        self,
        strategy: str = "iron_condor",
        ticker: str = "SPY",
        regime: Optional[str] = None,
    ) -> float:
        """
        Sample confidence from Thompson Sampling posterior.

        Draws from Beta(α, β) distribution and applies regime adjustment.
        """
        params = self._resolve_params(strategy, ticker)
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
        self,
        strategy: str = "iron_condor",
        ticker: str = "SPY",
        regime: Optional[str] = None,
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

        params = self._resolve_params(strategy, ticker)
        wins = int(params.get("wins", 0))
        losses = int(params.get("losses", 0))
        total_trades = wins + losses
        sample_gate_passed = total_trades >= MIN_CONFIDENCE_SAMPLE_SIZE

        # Recommendation based on sampled confidence, but fail conservative when the
        # model has not yet seen enough closed trades to be reliable.
        if not sample_gate_passed:
            recommendation = "AVOID"
        elif sampled >= 0.7:
            recommendation = "ENTER"
        elif sampled >= 0.5:
            recommendation = "CONSIDER"
        elif sampled >= 0.3:
            recommendation = "CAUTIOUS"
        else:
            recommendation = "AVOID"

        return {
            "posterior_mean": round(posterior_mean, 3),
            "sampled_confidence": sampled,
            "regime_adjustment": regime_adj,
            "recommendation": recommendation,
            "wins": wins,
            "losses": losses,
            "total_trades": total_trades,
            "minimum_sample_size": MIN_CONFIDENCE_SAMPLE_SIZE,
            "sample_gate_passed": sample_gate_passed,
            "is_reliable": sample_gate_passed,
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

        # Update SPY IC diagnostic bucket only for IC-family outcomes
        is_put = self._is_put_credit_strategy(strategy_key)
        if ticker.upper() == "SPY" and "spy_specific" in self.model and not is_put:
            if success:
                self.model["spy_specific"]["alpha"] += 1.0
                self.model["spy_specific"]["wins"] += 1
            else:
                self.model["spy_specific"]["beta"] += 1.0
                self.model["spy_specific"]["losses"] += 1

        # Always keep put-credit bucket in sync when that family is recorded
        if is_put:
            if "spy_put_credit" not in self.model:
                self.model["spy_put_credit"] = {
                    "alpha": 1.0,
                    "beta": 1.0,
                    "wins": 0,
                    "losses": 0,
                }
            if strategy_key != "spy_put_credit":
                if success:
                    self.model["spy_put_credit"]["alpha"] += 1.0
                    self.model["spy_put_credit"]["wins"] += 1
                else:
                    self.model["spy_put_credit"]["beta"] += 1.0
                    self.model["spy_put_credit"]["losses"] += 1

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
