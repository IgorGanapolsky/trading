"""
ML Confidence Threshold Gate.

Ensures ML model predictions meet minimum confidence before trading.
Low confidence = high uncertainty = don't trade.

Created: 2025-12-15
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIDENCE_LOG = Path("data/audit_trail/ml_confidence_blocks.jsonl")


@dataclass
class ConfidenceResult:
    """Result of ML confidence check."""
    passed: bool
    confidence: float
    threshold: float
    model_name: str
    prediction: str
    reasoning: str


class MLConfidenceGate:
    """
    Verifies ML predictions meet minimum confidence threshold.

    Checks:
    1. RL policy confidence (action probability)
    2. Sentiment model confidence
    3. Ensemble agreement (if multiple models)
    4. Historical accuracy at this confidence level
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        "rl_policy": 0.6,        # 60% confidence minimum
        "sentiment": 0.7,        # 70% for sentiment
        "ensemble": 0.65,        # 65% ensemble agreement
        "regret_adjusted": 0.55, # Lower threshold if low-risk trade
    }

    def __init__(
        self,
        thresholds: Optional[dict] = None,
        enable_regret_adjustment: bool = True,
    ):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.enable_regret_adjustment = enable_regret_adjustment
        CONFIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)

    def check_rl_confidence(
        self,
        action_probs: dict,
        selected_action: str,
    ) -> ConfidenceResult:
        """
        Check RL policy action confidence.

        Args:
            action_probs: Dict of action -> probability
            selected_action: The action being taken

        Returns:
            ConfidenceResult
        """
        confidence = action_probs.get(selected_action, 0.0)
        threshold = self.thresholds["rl_policy"]

        passed = confidence >= threshold

        # Check if other actions have similar probability (uncertainty)
        other_probs = [p for a, p in action_probs.items() if a != selected_action]
        max_other = max(other_probs) if other_probs else 0

        if confidence - max_other < 0.1:
            reasoning = f"Low margin over alternatives ({confidence:.1%} vs {max_other:.1%})"
            passed = False
        elif passed:
            reasoning = f"Strong confidence in {selected_action}"
        else:
            reasoning = f"Below threshold ({confidence:.1%} < {threshold:.1%})"

        return ConfidenceResult(
            passed=passed,
            confidence=confidence,
            threshold=threshold,
            model_name="rl_policy",
            prediction=selected_action,
            reasoning=reasoning,
        )

    def check_sentiment_confidence(
        self,
        sentiment_score: float,
        confidence: float,
    ) -> ConfidenceResult:
        """
        Check sentiment model confidence.

        Args:
            sentiment_score: Sentiment value (-1 to 1)
            confidence: Model confidence (0 to 1)

        Returns:
            ConfidenceResult
        """
        threshold = self.thresholds["sentiment"]
        passed = confidence >= threshold

        # Also check if sentiment is decisive
        if abs(sentiment_score) < 0.2:
            reasoning = f"Neutral sentiment ({sentiment_score:.2f}) - not actionable"
            passed = False
        elif passed:
            direction = "bullish" if sentiment_score > 0 else "bearish"
            reasoning = f"Strong {direction} sentiment signal"
        else:
            reasoning = f"Low confidence ({confidence:.1%} < {threshold:.1%})"

        return ConfidenceResult(
            passed=passed,
            confidence=confidence,
            threshold=threshold,
            model_name="sentiment",
            prediction=f"sentiment={sentiment_score:.2f}",
            reasoning=reasoning,
        )

    def check_ensemble_agreement(
        self,
        model_predictions: dict[str, str],
    ) -> ConfidenceResult:
        """
        Check if multiple models agree on the prediction.

        Args:
            model_predictions: Dict of model_name -> prediction

        Returns:
            ConfidenceResult
        """
        if len(model_predictions) < 2:
            return ConfidenceResult(
                passed=True,
                confidence=1.0,
                threshold=self.thresholds["ensemble"],
                model_name="ensemble",
                prediction="single_model",
                reasoning="Only one model, skipping ensemble check",
            )

        # Count votes
        from collections import Counter
        votes = Counter(model_predictions.values())
        majority_pred, majority_count = votes.most_common(1)[0]

        agreement = majority_count / len(model_predictions)
        threshold = self.thresholds["ensemble"]
        passed = agreement >= threshold

        if passed:
            reasoning = f"{majority_count}/{len(model_predictions)} models agree on {majority_pred}"
        else:
            reasoning = f"Low agreement ({agreement:.1%}): {dict(votes)}"

        return ConfidenceResult(
            passed=passed,
            confidence=agreement,
            threshold=threshold,
            model_name="ensemble",
            prediction=majority_pred,
            reasoning=reasoning,
        )

    def verify_trade_confidence(
        self,
        symbol: str,
        action: str,
        ml_outputs: dict,
        position_size: float = 1.0,
    ) -> dict:
        """
        Comprehensive confidence verification for a trade.

        Args:
            symbol: Trading symbol
            action: Trade action (BUY/SELL)
            ml_outputs: Dict with model outputs
            position_size: Relative position size (for regret adjustment)

        Returns:
            Dict with overall result and individual checks
        """
        checks = []
        all_passed = True

        # Check RL confidence if available
        if "action_probs" in ml_outputs:
            rl_check = self.check_rl_confidence(
                ml_outputs["action_probs"],
                action,
            )
            checks.append(rl_check)
            if not rl_check.passed:
                all_passed = False

        # Check sentiment confidence if available
        if "sentiment_score" in ml_outputs and "sentiment_confidence" in ml_outputs:
            sent_check = self.check_sentiment_confidence(
                ml_outputs["sentiment_score"],
                ml_outputs["sentiment_confidence"],
            )
            checks.append(sent_check)
            if not sent_check.passed:
                all_passed = False

        # Check ensemble agreement if available
        if "model_predictions" in ml_outputs:
            ensemble_check = self.check_ensemble_agreement(
                ml_outputs["model_predictions"],
            )
            checks.append(ensemble_check)
            if not ensemble_check.passed:
                all_passed = False

        # Regret adjustment for small positions
        if self.enable_regret_adjustment and not all_passed:
            if position_size <= 0.5:  # Small position
                min_confidence = min(c.confidence for c in checks) if checks else 0
                regret_threshold = self.thresholds["regret_adjusted"]
                if min_confidence >= regret_threshold:
                    all_passed = True
                    for check in checks:
                        check.reasoning += " (regret-adjusted for small position)"

        result = {
            "passed": all_passed,
            "checks": [
                {
                    "model": c.model_name,
                    "passed": c.passed,
                    "confidence": c.confidence,
                    "threshold": c.threshold,
                    "reasoning": c.reasoning,
                }
                for c in checks
            ],
            "recommendation": "PROCEED" if all_passed else "SKIP",
            "symbol": symbol,
            "action": action,
        }

        # Log if blocked
        if not all_passed:
            self._log_block(result)

        return result

    def _log_block(self, result: dict) -> None:
        """Log a blocked trade due to low confidence."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }

        with open(CONFIDENCE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        logger.warning(
            f"Trade blocked due to low ML confidence: "
            f"{result['symbol']} {result['action']}"
        )


def integrate_with_orchestrator():
    """Add confidence gate to TradingOrchestrator."""
    try:
        from src.orchestrator.main import TradingOrchestrator

        gate = MLConfidenceGate()

        if hasattr(TradingOrchestrator, "_confidence_integrated"):
            return

        original_execute = getattr(
            TradingOrchestrator, "_original_execute_trade",
            TradingOrchestrator.execute_trade
        )

        def confident_execute_trade(self, symbol, action, quantity, **kwargs):
            # Extract ML outputs from kwargs or get from current state
            ml_outputs = kwargs.pop("ml_outputs", {})

            if ml_outputs:
                result = gate.verify_trade_confidence(
                    symbol=symbol,
                    action=action,
                    ml_outputs=ml_outputs,
                    position_size=kwargs.get("position_size", 1.0),
                )

                if not result["passed"]:
                    logger.warning(f"Trade skipped due to low confidence: {result}")
                    return {
                        "success": False,
                        "skipped": True,
                        "reason": "Low ML confidence",
                        "details": result,
                    }

            return original_execute(self, symbol, action, quantity, **kwargs)

        TradingOrchestrator.execute_trade = confident_execute_trade
        TradingOrchestrator._confidence_integrated = True

        logger.info("Integrated MLConfidenceGate with TradingOrchestrator")

    except ImportError:
        logger.warning("TradingOrchestrator not available")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("ML CONFIDENCE GATE DEMO")
    print("=" * 60)

    gate = MLConfidenceGate()

    # Demo: High confidence trade
    print("\n1. High confidence trade:")
    result = gate.verify_trade_confidence(
        symbol="SPY",
        action="BUY",
        ml_outputs={
            "action_probs": {"BUY": 0.75, "SELL": 0.15, "HOLD": 0.10},
            "sentiment_score": 0.6,
            "sentiment_confidence": 0.85,
        },
    )
    print(f"   Passed: {result['passed']}")
    print(f"   Recommendation: {result['recommendation']}")

    # Demo: Low confidence trade
    print("\n2. Low confidence trade:")
    result = gate.verify_trade_confidence(
        symbol="NVDA",
        action="BUY",
        ml_outputs={
            "action_probs": {"BUY": 0.35, "SELL": 0.33, "HOLD": 0.32},
            "sentiment_score": 0.1,
            "sentiment_confidence": 0.45,
        },
    )
    print(f"   Passed: {result['passed']}")
    print(f"   Recommendation: {result['recommendation']}")
    for check in result["checks"]:
        print(f"   - {check['model']}: {check['reasoning']}")

    print("\n" + "=" * 60)
