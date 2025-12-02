"""
Bogleheads Forum Integration for RL Engine

Integrates Bogleheads forum wisdom into RL trading decisions.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# Lazy import
_bogleheads_learner = None


def get_bogleheads_learner():
    """Get or create Bogleheads learner instance."""
    global _bogleheads_learner

    if _bogleheads_learner is None:
        try:
            # Add .claude/skills to path
            skills_path = project_root / ".claude" / "skills" / "bogleheads_learner" / "scripts"
            if str(skills_path) not in sys.path:
                sys.path.insert(0, str(skills_path))

            from bogleheads_learner import BogleheadsLearner

            _bogleheads_learner = BogleheadsLearner()
            logger.info("✅ Bogleheads learner initialized")
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize Bogleheads learner: {e}")
            _bogleheads_learner = None

    return _bogleheads_learner


def get_bogleheads_signal_for_symbol(
    symbol: str, market_context: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Get Bogleheads-based trading signal for a symbol.

    Args:
        symbol: Symbol to analyze
        market_context: Current market context

    Returns:
        Dict with signal, confidence, and reasoning
    """
    learner = get_bogleheads_learner()

    if not learner:
        return {
            "score": 0.0,
            "confidence": 0.0,
            "signal": "HOLD",
            "reasoning": "Bogleheads learner unavailable",
        }

    try:
        market_context = market_context or {}

        # Get signal from Bogleheads
        signal = learner.get_bogleheads_signal(symbol=symbol, market_context=market_context)

        # Convert signal to score (-100 to +100)
        signal_map = {"BUY": 50, "SELL": -50, "HOLD": 0}
        score = signal_map.get(signal.get("signal", "HOLD"), 0) * signal.get("confidence", 0.5)

        return {
            "score": score,
            "confidence": signal.get("confidence", 0.0),
            "signal": signal.get("signal", "HOLD"),
            "reasoning": signal.get("reasoning", ""),
            "insights_used": signal.get("insights_used", []),
        }

    except Exception as e:
        logger.error(f"Error getting Bogleheads signal: {e}")
        return {
            "score": 0.0,
            "confidence": 0.0,
            "signal": "HOLD",
            "reasoning": f"Error: {str(e)}",
        }


def get_bogleheads_regime() -> dict[str, Any]:
    """
    Get current market regime from Bogleheads analysis.

    Returns:
        Dict with regime, sentiment, themes, risk_level
    """
    learner = get_bogleheads_learner()

    if not learner:
        return {
            "regime": "unknown",
            "sentiment": "neutral",
            "key_themes": [],
            "risk_level": "medium",
        }

    try:
        return learner.analyze_market_regime_bogleheads()
    except Exception as e:
        logger.error(f"Error getting Bogleheads regime: {e}")
        return {
            "regime": "unknown",
            "sentiment": "neutral",
            "key_themes": [],
            "risk_level": "medium",
        }


def add_bogleheads_features_to_rl_state(
    rl_state: dict[str, Any],
    symbol: str,
    market_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Add Bogleheads features to RL state space.

    Args:
        rl_state: Current RL state dict
        symbol: Symbol being analyzed
        market_context: Market context

    Returns:
        Enhanced RL state with Bogleheads features
    """
    # Get Bogleheads signal
    signal = get_bogleheads_signal_for_symbol(symbol, market_context)

    # Get regime
    regime = get_bogleheads_regime()

    # Add features to state
    rl_state["bogleheads_sentiment"] = signal["score"] / 100.0  # Normalize to -1 to 1
    rl_state["bogleheads_confidence"] = signal["confidence"]
    rl_state["bogleheads_regime"] = regime.get("regime", "unknown")
    rl_state["bogleheads_risk_level"] = regime.get("risk_level", "medium")

    # Convert regime to numeric
    regime_map = {
        "bull": 1.0,
        "bear": -1.0,
        "choppy": 0.0,
        "uncertain": 0.0,
        "unknown": 0.0,
    }
    rl_state["bogleheads_regime_score"] = regime_map.get(regime.get("regime", "unknown"), 0.0)

    # Convert risk level to numeric
    risk_map = {"low": 0.0, "medium": 0.5, "high": 1.0}
    rl_state["bogleheads_risk_score"] = risk_map.get(regime.get("risk_level", "medium"), 0.5)

    return rl_state
