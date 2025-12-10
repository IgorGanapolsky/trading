"""
Crypto Weekend Agent - Mean Reversion Strategy for Weekend Trading

WHY THIS EXISTS:
- Crypto trades 24/7, unlike stocks (9:30 AM - 4:00 PM ET)
- Weekend liquidity is lower, causing more volatile price swings
- These swings create mean-reversion opportunities

STRATEGY:
- Buy when RSI < 30 (oversold) on Saturday/Sunday
- Sell when RSI > 50 or +2% profit (whichever comes first)
- Max position: 5% of portfolio (defined risk)

RATIONALE (from trading-bot-roadmap.md):
- Low liquidity on weekends causes "fake dumps"
- Institutions aren't active, creating retail-driven volatility
- Mean reversion works when fundamentals haven't changed (just liquidity)

Usage:
    from src.agents.crypto_weekend_agent import CryptoWeekendAgent

    agent = CryptoWeekendAgent()
    signal = agent.analyze("BTC/USD")

    if signal.is_buy:
        execute_crypto_buy(signal.symbol, signal.position_size)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CryptoWeekendSignal:
    """Signal from the crypto weekend agent."""

    symbol: str
    is_buy: bool
    is_sell: bool
    confidence: float  # 0.0 to 1.0
    rsi: float
    current_price: float
    entry_target: float | None = None
    exit_target: float | None = None
    position_size_pct: float = 0.05  # 5% of portfolio by default
    rationale: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CryptoWeekendAgent:
    """
    Mean reversion agent for weekend crypto trading.

    The strategy exploits low-liquidity weekend moves by buying oversold
    conditions and selling when RSI normalizes or profit target is hit.
    """

    # Strategy parameters
    RSI_OVERSOLD = 30  # Buy when RSI below this
    RSI_NEUTRAL = 50  # Sell when RSI above this
    RSI_OVERBOUGHT = 70  # Strong sell signal
    PROFIT_TARGET = 0.02  # 2% take profit
    STOP_LOSS = 0.03  # 3% stop loss
    MAX_POSITION_PCT = 0.05  # Max 5% of portfolio per position

    # Weekend definition (UTC)
    WEEKEND_DAYS = {5, 6}  # Saturday (5) and Sunday (6)

    # Supported crypto pairs (Alpaca supports these)
    SUPPORTED_PAIRS = [
        "BTC/USD",
        "ETH/USD",
        "BTCUSD",
        "ETHUSD",
    ]

    def __init__(self, rsi_period: int = 14):
        """
        Initialize the crypto weekend agent.

        Args:
            rsi_period: Period for RSI calculation (default: 14)
        """
        self.rsi_period = rsi_period
        logger.info("CryptoWeekendAgent initialized with RSI period %d", rsi_period)

    def is_weekend(self) -> bool:
        """Check if today is a weekend (Saturday or Sunday)."""
        return datetime.utcnow().weekday() in self.WEEKEND_DAYS

    def _calculate_rsi(self, prices: list[float]) -> float:
        """
        Calculate RSI from a list of closing prices.

        Args:
            prices: List of closing prices (oldest first)

        Returns:
            RSI value (0-100)
        """
        if len(prices) < self.rsi_period + 1:
            logger.warning("Insufficient data for RSI calculation")
            return 50.0  # Neutral if insufficient data

        # Calculate price changes
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Calculate average gains and losses
        avg_gain = sum(gains[-self.rsi_period :]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period :]) / self.rsi_period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _get_crypto_data(self, symbol: str, lookback_hours: int = 72) -> dict[str, Any]:
        """
        Fetch crypto price data from Alpaca.

        Args:
            symbol: Crypto pair (e.g., "BTC/USD")
            lookback_hours: Hours of data to fetch

        Returns:
            Dict with price data and current price
        """
        try:
            import os

            from alpaca.data.historical import CryptoHistoricalDataClient
            from alpaca.data.requests import CryptoBarsRequest
            from alpaca.data.timeframe import TimeFrame

            # Initialize client
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")

            if not api_key or not secret_key:
                logger.error("Alpaca credentials not found")
                return {}

            client = CryptoHistoricalDataClient(api_key, secret_key)

            # Normalize symbol
            normalized_symbol = symbol.replace("/", "").upper()
            if normalized_symbol not in ["BTCUSD", "ETHUSD"]:
                normalized_symbol = "BTCUSD"  # Default

            # Fetch hourly bars
            from datetime import timedelta

            end = datetime.utcnow()
            start = end - timedelta(hours=lookback_hours)

            request = CryptoBarsRequest(
                symbol_or_symbols=normalized_symbol,
                timeframe=TimeFrame.Hour,
                start=start,
                end=end,
            )

            bars = client.get_crypto_bars(request)

            if normalized_symbol not in bars:
                logger.warning(f"No data returned for {normalized_symbol}")
                return {}

            symbol_bars = bars[normalized_symbol]
            closes = [float(bar.close) for bar in symbol_bars]

            if not closes:
                return {}

            return {
                "symbol": symbol,
                "closes": closes,
                "current_price": closes[-1],
                "high_24h": max(closes[-24:]) if len(closes) >= 24 else max(closes),
                "low_24h": min(closes[-24:]) if len(closes) >= 24 else min(closes),
            }

        except ImportError:
            logger.warning("Alpaca SDK not available, using mock data")
            return self._get_mock_data(symbol)
        except Exception as e:
            logger.error(f"Error fetching crypto data: {e}")
            return self._get_mock_data(symbol)

    def _get_mock_data(self, symbol: str) -> dict[str, Any]:
        """
        Return mock data for testing when API is unavailable.
        """
        import random

        base_price = 95000 if "BTC" in symbol.upper() else 3500
        # Generate mock hourly closes with some volatility
        closes = [base_price * (1 + random.uniform(-0.02, 0.02)) for _ in range(72)]

        return {
            "symbol": symbol,
            "closes": closes,
            "current_price": closes[-1],
            "high_24h": max(closes[-24:]),
            "low_24h": min(closes[-24:]),
            "mock": True,
        }

    def analyze(self, symbol: str) -> CryptoWeekendSignal:
        """
        Analyze a crypto pair for weekend mean-reversion opportunity.

        Args:
            symbol: Crypto pair (e.g., "BTC/USD", "ETH/USD")

        Returns:
            CryptoWeekendSignal with buy/sell recommendation
        """
        logger.info(f"Analyzing {symbol} for weekend mean-reversion")

        # Get market data
        data = self._get_crypto_data(symbol)

        if not data or not data.get("closes"):
            logger.warning(f"No data available for {symbol}")
            return CryptoWeekendSignal(
                symbol=symbol,
                is_buy=False,
                is_sell=False,
                confidence=0.0,
                rsi=50.0,
                current_price=0.0,
                rationale="No data available",
            )

        closes = data["closes"]
        current_price = data["current_price"]

        # Calculate RSI
        rsi = self._calculate_rsi(closes)

        # Determine signal
        is_weekend = self.is_weekend()
        is_buy = False
        is_sell = False
        confidence = 0.0
        rationale = ""

        if rsi < self.RSI_OVERSOLD:
            # Oversold - potential buy
            is_buy = True
            confidence = min(0.9, (self.RSI_OVERSOLD - rsi) / self.RSI_OVERSOLD + 0.5)
            rationale = f"RSI {rsi:.1f} < {self.RSI_OVERSOLD} (oversold), weekend mean-reversion opportunity"

            # Boost confidence on weekends (our edge)
            if is_weekend:
                confidence = min(0.95, confidence + 0.1)
                rationale += " [WEEKEND BOOST]"

        elif rsi > self.RSI_OVERBOUGHT:
            # Overbought - sell signal
            is_sell = True
            confidence = min(0.9, (rsi - self.RSI_OVERBOUGHT) / 30 + 0.5)
            rationale = f"RSI {rsi:.1f} > {self.RSI_OVERBOUGHT} (overbought), take profits"

        elif rsi > self.RSI_NEUTRAL:
            # Neutral-to-high RSI - consider closing long positions
            is_sell = True
            confidence = 0.6
            rationale = f"RSI {rsi:.1f} > {self.RSI_NEUTRAL}, exiting mean-reversion trade"

        else:
            # RSI between 30-50: hold/wait
            confidence = 0.3
            rationale = f"RSI {rsi:.1f} in neutral zone, no action"

        # Calculate targets
        entry_target = current_price if is_buy else None
        exit_target = current_price * (1 + self.PROFIT_TARGET) if is_buy else None

        signal = CryptoWeekendSignal(
            symbol=symbol,
            is_buy=is_buy,
            is_sell=is_sell,
            confidence=confidence,
            rsi=rsi,
            current_price=current_price,
            entry_target=entry_target,
            exit_target=exit_target,
            position_size_pct=self.MAX_POSITION_PCT if is_buy else 0.0,
            rationale=rationale,
        )

        logger.info(
            f"CryptoWeekendAgent signal for {symbol}: "
            f"RSI={rsi:.1f}, Buy={is_buy}, Sell={is_sell}, "
            f"Confidence={confidence:.2f}"
        )

        return signal

    def scan_opportunities(self) -> list[CryptoWeekendSignal]:
        """
        Scan all supported crypto pairs for opportunities.

        Returns:
            List of signals sorted by confidence
        """
        signals = []

        for pair in ["BTC/USD", "ETH/USD"]:
            signal = self.analyze(pair)
            if signal.is_buy or signal.is_sell:
                signals.append(signal)

        # Sort by confidence (highest first)
        signals.sort(key=lambda s: s.confidence, reverse=True)

        logger.info(f"CryptoWeekendAgent found {len(signals)} opportunities")
        return signals


def main():
    """CLI interface for testing the agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Crypto Weekend Agent")
    parser.add_argument(
        "--symbol", default="BTC/USD", help="Crypto pair to analyze (default: BTC/USD)"
    )
    parser.add_argument("--scan", action="store_true", help="Scan all supported pairs")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    agent = CryptoWeekendAgent()

    if args.scan:
        print("\n=== CRYPTO WEEKEND AGENT - FULL SCAN ===")
        signals = agent.scan_opportunities()

        if not signals:
            print("No opportunities found.")
        else:
            for signal in signals:
                print(f"\n{signal.symbol}:")
                print(f"  RSI: {signal.rsi:.1f}")
                print(f"  Buy: {signal.is_buy}, Sell: {signal.is_sell}")
                print(f"  Confidence: {signal.confidence:.1%}")
                print(f"  Price: ${signal.current_price:,.2f}")
                print(f"  Rationale: {signal.rationale}")
    else:
        print(f"\n=== CRYPTO WEEKEND AGENT - {args.symbol} ===")
        signal = agent.analyze(args.symbol)

        print(f"Symbol: {signal.symbol}")
        print(f"RSI: {signal.rsi:.1f}")
        print(f"Current Price: ${signal.current_price:,.2f}")
        print(f"Buy Signal: {signal.is_buy}")
        print(f"Sell Signal: {signal.is_sell}")
        print(f"Confidence: {signal.confidence:.1%}")
        print(f"Rationale: {signal.rationale}")

        if signal.is_buy:
            print(f"\nEntry Target: ${signal.entry_target:,.2f}")
            print(f"Exit Target: ${signal.exit_target:,.2f}")
            print(f"Position Size: {signal.position_size_pct:.1%} of portfolio")


if __name__ == "__main__":
    main()
