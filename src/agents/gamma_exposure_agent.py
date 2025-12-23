import logging
from datetime import datetime
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GammaExposureAgent(BaseAgent):
    """
    Gamma Exposure (GEX) Agent: "The X-Ray Vision"

    Responsibilities:
    - Calculate Dealer Gamma Exposure (GEX)
    - Identify "Gamma Flip" levels (where volatility explodes)
    - Detect "Gamma Squeeze" conditions

    Theory:
    - Market Makers (Dealers) provide liquidity.
    - When they sell Calls, they are Short Gamma -> They must BUY as price rises (Accelerator).
    - When they buy Calls, they are Long Gamma -> They must SELL as price rises (Stabilizer).
    - We want to trade WITH the Dealers.
    """

    def __init__(self):
        super().__init__(
            name="GammaExposureAgent",
            role="Options flow and market maker positioning analysis",
            # model=None -> Uses BATS ModelSelector for budget-aware selection
        )

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze Gamma Exposure for a symbol.

        Args:
            data: Contains 'symbol' and 'options_chain' (if available)

        Returns:
            GEX analysis and trading implications
        """
        symbol = data.get("symbol")
        current_price = data.get("current_price")

        # In a real implementation, we would fetch the full options chain here.
        # For this prototype, we will simulate the GEX calculation logic
        # or use a simplified heuristic if real options data is missing.

        logger.info(f"🔮 Analyzing Gamma Exposure for {symbol} at ${current_price}")

        # 1. Calculate GEX Profile (Simulation for Prototype)
        # Real GEX = Sum(OpenInterest * Gamma * 100 * SpotPrice)
        gex_profile = self._estimate_gex_profile(symbol, current_price)

        # 2. Interpret GEX
        implication = self._interpret_gex(gex_profile)

        # 3. Generate LLM Insight
        prompt = self._build_gex_prompt(symbol, current_price, gex_profile, implication)
        llm_response = self.reason_with_llm(prompt)

        result = {
            "agent": self.name,
            "symbol": symbol,
            "gex_profile": gex_profile,
            "signal": implication["signal"],
            "confidence": implication["confidence"],
            "reasoning": llm_response.get("reasoning", "Analysis complete"),
            "timestamp": datetime.now().isoformat(),
        }

        self.log_decision(result)
        return result

    def _estimate_gex_profile(self, symbol: str, price: float) -> dict[str, Any]:
        """
        Estimate GEX profile.
        NOTE: In production, this requires a live Options Chain API (e.g., Polygon/ThetaData).
        """
        # Placeholder logic: Assume positive GEX (Stability) for major indices,
        # mixed for individual stocks.

        is_index = symbol in ["SPY", "QQQ", "IWM"]

        if is_index:
            # Indices usually have high Put OI (Hedges) -> Dealers Long Puts -> Short Gamma?
            # Actually, Dealers are usually Short Puts (selling insurance) -> Long Gamma.
            total_gex = 5000000000  # $5B Positive Gamma (Stabilizing)
            zero_gamma_level = price * 0.95  # Support level
        else:
            # Volatile stocks might be Short Gamma (Accelerator)
            total_gex = -100000000  # -$100M Negative Gamma (Volatile)
            zero_gamma_level = price * 1.02  # Resistance

        return {
            "total_gex_dollars": total_gex,
            "regime": "POSITIVE_GAMMA" if total_gex > 0 else "NEGATIVE_GAMMA",
            "zero_gamma_level": zero_gamma_level,
            "volatility_implication": "LOW_VOL" if total_gex > 0 else "HIGH_VOL",
        }

    def _interpret_gex(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Interpret the GEX numbers into a trading signal."""
        if profile["regime"] == "POSITIVE_GAMMA":
            return {
                "signal": "MEAN_REVERSION",
                "confidence": 0.7,
                "description": "Dealers are Long Gamma. They will sell rips and buy dips. Expect low volatility.",
            }
        else:
            return {
                "signal": "MOMENTUM",
                "confidence": 0.8,
                "description": "Dealers are Short Gamma. They must chase the price. Expect explosive moves.",
            }

    def _build_gex_prompt(self, symbol: str, price: float, profile: dict, implication: dict) -> str:
        return f"""You are the Gamma Exposure Agent.

        ANALYSIS FOR {symbol}:
        Current Price: ${price}
        GEX Regime: {profile["regime"]} ({profile["volatility_implication"]})
        Total GEX: ${profile["total_gex_dollars"]:,.0f}
        Zero Gamma Level: ${profile["zero_gamma_level"]:.2f}

        IMPLICATION:
        {implication["description"]}
        Signal: {implication["signal"]}

        Task:
        Explain how this Gamma positioning affects price action today.
        Should we trade Mean Reversion (Buy Low/Sell High) or Momentum (Buy Breakouts)?
        """
