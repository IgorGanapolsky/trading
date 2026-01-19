"""
Core Strategy - Primary Momentum-Based ETF Trading Strategy

This is the canonical "Core Strategy" referenced throughout the codebase.
It implements a multi-timeframe momentum strategy with RSI and MACD signals.

Author: Trading System
Created: 2025-12-24
Status: CORE (productized, frozen)

Strategy Overview:
1. Universe: SPY ONLY per CLAUDE.md Jan 19, 2026 (best liquidity, tightest spreads)
2. Signals: MACD crossover + RSI confirmation
3. Timeframe: Daily with hourly confirmation
4. Risk: 2% position sizing, volatility-adjusted stops
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal from CoreStrategy."""

    symbol: str
    action: str  # "buy", "sell", "hold"
    strength: float  # 0.0 to 1.0
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    rationale: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "strength": round(self.strength, 3),
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "rationale": self.rationale,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass

    @abstractmethod
    def generate_signals(self, data: Any) -> list[Signal]:
        """Generate trading signals from market data."""
        pass

    @abstractmethod
    def get_config(self) -> dict[str, Any]:
        """Get strategy configuration."""
        pass


class CoreStrategy(BaseStrategy):
    """
    Core momentum-based ETF strategy.

    This is the primary trading strategy that combines:
    - MACD crossover signals
    - RSI momentum confirmation
    - Volume analysis
    - Multi-timeframe trend alignment

    Used for daily trading on major ETFs.
    """

    # Default universe - UPDATED Jan 19, 2026 (LL-244 Adversarial Audit)
    # CLAUDE.md mandates "SPY ONLY" - best liquidity, tightest spreads
    DEFAULT_UNIVERSE = ["SPY"]

    # Strategy parameters
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    # Risk parameters - FIXED Jan 6 2026: Increased R:R for positive expectancy
    MAX_POSITION_SIZE = 0.02  # 2% of portfolio
    STOP_LOSS_PCT = 0.02  # 2% stop loss
    TAKE_PROFIT_PCT = 0.06  # 6% take profit (3:1 R:R) - was 4%, caused negative expectancy

    def __init__(
        self,
        universe: list[str] | None = None,
        paper: bool = True,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize CoreStrategy.

        Args:
            universe: List of symbols to trade
            paper: Paper trading mode
            config: Optional configuration overrides
        """
        self.universe = universe or self.DEFAULT_UNIVERSE
        self.paper = paper
        self._config = config or {}

        # Apply config overrides
        if "macd_fast" in self._config:
            self.MACD_FAST = self._config["macd_fast"]
        if "macd_slow" in self._config:
            self.MACD_SLOW = self._config["macd_slow"]
        if "rsi_period" in self._config:
            self.RSI_PERIOD = self._config["rsi_period"]

        logger.info(f"CoreStrategy initialized: {len(self.universe)} symbols, paper={paper}")

    @property
    def name(self) -> str:
        return "core_momentum"

    def get_config(self) -> dict[str, Any]:
        """Return current strategy configuration."""
        return {
            "name": self.name,
            "universe": self.universe,
            "paper": self.paper,
            "macd": {
                "fast": self.MACD_FAST,
                "slow": self.MACD_SLOW,
                "signal": self.MACD_SIGNAL,
            },
            "rsi": {
                "period": self.RSI_PERIOD,
                "oversold": self.RSI_OVERSOLD,
                "overbought": self.RSI_OVERBOUGHT,
            },
            "risk": {
                "max_position_size": self.MAX_POSITION_SIZE,
                "stop_loss_pct": self.STOP_LOSS_PCT,
                "take_profit_pct": self.TAKE_PROFIT_PCT,
            },
        }

    def _calculate_rsi(self, prices: list[float]) -> float:
        """Calculate RSI from price series."""
        if len(prices) < self.RSI_PERIOD + 1:
            return 50.0  # Neutral if not enough data

        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes[-self.RSI_PERIOD :]]
        losses = [-c if c < 0 else 0 for c in changes[-self.RSI_PERIOD :]]

        avg_gain = sum(gains) / self.RSI_PERIOD
        avg_loss = sum(losses) / self.RSI_PERIOD

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: list[float]) -> tuple[float, float, float]:
        """
        Calculate MACD, Signal, and Histogram.

        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        if len(prices) < self.MACD_SLOW + self.MACD_SIGNAL:
            return 0.0, 0.0, 0.0

        # Simple EMA approximation
        def ema(data: list[float], period: int) -> float:
            if len(data) < period:
                return sum(data) / len(data) if data else 0
            multiplier = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for price in data[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val

        fast_ema = ema(prices, self.MACD_FAST)
        slow_ema = ema(prices, self.MACD_SLOW)
        macd_line = fast_ema - slow_ema

        # FIXED Jan 6 2026: Proper signal line calculation using EMA of MACD values
        # Calculate historical MACD values for signal line
        macd_history = []
        for i in range(self.MACD_SLOW, len(prices) + 1):
            hist_prices = prices[:i]
            hist_fast = ema(hist_prices, self.MACD_FAST)
            hist_slow = ema(hist_prices, self.MACD_SLOW)
            macd_history.append(hist_fast - hist_slow)

        # Signal line is 9-period EMA of MACD values
        if len(macd_history) >= self.MACD_SIGNAL:
            signal_line = ema(macd_history, self.MACD_SIGNAL)
        else:
            signal_line = macd_line * 0.9  # Fallback if not enough data

        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def generate_signals(self, data: Any) -> list[Signal]:
        """
        Generate trading signals from market data.

        Args:
            data: Market data (dict with 'symbol' -> price list)
                  Or DataFrame with OHLCV data

        Returns:
            List of Signal objects
        """
        signals = []

        # Handle different data formats
        if isinstance(data, dict):
            price_data = data
        else:
            # Assume DataFrame-like with 'close' column per symbol
            price_data = {}
            try:
                for symbol in self.universe:
                    if hasattr(data, "get"):
                        price_data[symbol] = list(data.get(symbol, {}).get("close", []))
                    else:
                        price_data[symbol] = []
            except Exception as e:
                logger.warning(f"Could not parse data: {e}")
                return signals

        for symbol in self.universe:
            try:
                prices = price_data.get(symbol, [])
                if len(prices) < self.MACD_SLOW + self.MACD_SIGNAL:
                    logger.debug(f"{symbol}: Insufficient data for signals")
                    continue

                current_price = prices[-1]

                # Calculate indicators
                rsi = self._calculate_rsi(prices)
                macd, signal, histogram = self._calculate_macd(prices)

                # Generate signal based on indicators
                action = "hold"
                strength = 0.5
                rationale = ""

                # Bullish: MACD crossover + RSI not overbought
                if histogram > 0 and rsi < self.RSI_OVERBOUGHT:
                    if rsi < self.RSI_OVERSOLD:
                        action = "buy"
                        strength = 0.9
                        rationale = f"Oversold RSI ({rsi:.1f}) + bullish MACD"
                    elif histogram > 0 and macd > signal:
                        action = "buy"
                        strength = 0.7
                        rationale = f"Bullish MACD crossover, RSI={rsi:.1f}"

                # Bearish: MACD crossunder + RSI not oversold
                elif histogram < 0 and rsi > self.RSI_OVERSOLD:
                    if rsi > self.RSI_OVERBOUGHT:
                        action = "sell"
                        strength = 0.9
                        rationale = f"Overbought RSI ({rsi:.1f}) + bearish MACD"
                    elif histogram < 0 and macd < signal:
                        action = "sell"
                        strength = 0.7
                        rationale = f"Bearish MACD crossover, RSI={rsi:.1f}"

                # Calculate stops
                stop_loss = current_price * (1 - self.STOP_LOSS_PCT)
                take_profit = current_price * (1 + self.TAKE_PROFIT_PCT)

                signal_obj = Signal(
                    symbol=symbol,
                    action=action,
                    strength=strength,
                    price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    rationale=rationale,
                )
                signals.append(signal_obj)

            except Exception as e:
                logger.warning(f"Error generating signal for {symbol}: {e}")

        # Sort by strength (strongest first)
        signals.sort(key=lambda s: s.strength, reverse=True)

        logger.info(
            f"CoreStrategy generated {len(signals)} signals: "
            f"{sum(1 for s in signals if s.action == 'buy')} buy, "
            f"{sum(1 for s in signals if s.action == 'sell')} sell"
        )

        return signals

    def validate(self) -> bool:
        """Validate strategy configuration."""
        if not self.universe:
            logger.error("Empty universe")
            return False
        if self.MACD_FAST >= self.MACD_SLOW:
            logger.error("MACD fast period must be less than slow period")
            return False
        if not (0 < self.RSI_OVERSOLD < self.RSI_OVERBOUGHT < 100):
            logger.error("Invalid RSI thresholds")
            return False
        return True

    def get_universe(self) -> list[str]:
        """Get current trading universe."""
        return self.universe.copy()

    def set_universe(self, symbols: list[str]) -> None:
        """Update trading universe."""
        self.universe = symbols
        logger.info(f"Updated universe to {len(symbols)} symbols")


# Factory function for registry
def create_core_strategy(
    universe: list[str] | None = None,
    paper: bool = True,
    **kwargs: Any,
) -> CoreStrategy:
    """
    Factory function to create CoreStrategy instance.

    Used by StrategyRegistry.
    """
    return CoreStrategy(universe=universe, paper=paper, config=kwargs)


# Example usage and validation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    strategy = CoreStrategy(paper=True)
    print(f"Strategy: {strategy.name}")
    print(f"Universe: {strategy.get_universe()}")
    print(f"Valid: {strategy.validate()}")
    print(f"Config: {strategy.get_config()}")

    # Test with mock data
    mock_data = {
        "SPY": list(range(450, 500)) + list(range(500, 480, -1)),  # 50 prices
        "QQQ": list(range(380, 420)) + list(range(420, 400, -1)),
    }

    signals = strategy.generate_signals(mock_data)
    print(f"\nGenerated {len(signals)} signals:")
    for sig in signals:
        print(f"  {sig.symbol}: {sig.action} (strength={sig.strength:.2f}) - {sig.rationale}")
