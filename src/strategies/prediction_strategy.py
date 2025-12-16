"""
Prediction Markets Trading Strategy - Kalshi Integration

This module implements a trading strategy for CFTC-regulated prediction markets
on Kalshi, which offers binary outcome contracts for events like elections,
economic indicators, weather, and more.

Strategy Overview:
- Analyzes open markets for edge opportunities
- Targets markets where implied probability differs from our estimate
- Uses Kelly Criterion for position sizing
- Implements risk limits per market and category
- Focuses on high-liquidity markets with tight spreads

Key Features:
- Markets pay $1 if outcome occurs, $0 otherwise
- Prices quoted in cents (0-100) representing probability
- Extended trading hours on Kalshi platform
- Lower correlation to equity markets (alpha source)

Target: Uncorrelated returns from event-driven opportunities
Risk Level: MODERATE (regulated, binary outcomes)

Author: Trading System
Created: 2025-12-09
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import Kalshi client
try:
    from src.brokers.kalshi_client import (
        KalshiClient,
        KalshiMarket,
        KalshiPosition,
        get_kalshi_client,
    )

    KALSHI_AVAILABLE = True
except ImportError:
    KALSHI_AVAILABLE = False
    logger.warning("KalshiClient not available - prediction strategy disabled")


class MarketCategory(Enum):
    """Prediction market categories on Kalshi."""

    ELECTIONS = "elections"
    ECONOMICS = "economics"  # Fed rates, CPI, GDP
    WEATHER = "weather"
    CRYPTO = "crypto"  # BTC price targets
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    TECH = "tech"  # Company earnings, product launches


class SignalStrength(Enum):
    """Signal strength classification."""

    STRONG_YES = "strong_yes"  # >70% probability edge
    MODERATE_YES = "moderate_yes"  # 55-70% probability edge
    NEUTRAL = "neutral"
    MODERATE_NO = "moderate_no"
    STRONG_NO = "strong_no"


@dataclass
class PredictionSignal:
    """Trading signal for a prediction market."""

    market_ticker: str
    market_title: str
    side: str  # "yes" or "no"
    current_price: float  # Current market price (cents)
    fair_value: float  # Our estimated fair value (cents)
    edge: float  # Expected edge (fair_value - current_price)
    strength: SignalStrength
    confidence: float  # 0-100 confidence in our estimate
    recommended_size: int  # Recommended position size in contracts
    reasoning: str
    timestamp: datetime


@dataclass
class PredictionTrade:
    """Executed prediction market trade."""

    market_ticker: str
    side: str
    quantity: int
    price: float  # Entry price in cents
    amount_usd: float  # Total cost
    order_id: str
    timestamp: datetime
    reasoning: str
    attribution: Optional[dict] = None


class PredictionStrategy:
    """
    Prediction markets trading strategy for Kalshi.

    This strategy:
    - Scans open markets for edge opportunities
    - Compares market prices to estimated fair values
    - Uses Kelly Criterion for position sizing
    - Implements category-level and total portfolio limits
    - Focuses on liquid markets with sufficient volume

    Edge Sources:
    - Information advantage (news analysis, data aggregation)
    - Statistical models (polling, economic indicators)
    - Contrarian plays (overreaction to news)
    - Arbitrage (related markets mispriced)

    Attributes:
        daily_budget: Maximum daily allocation in USD
        max_position_per_market: Maximum position per single market
        min_edge: Minimum edge (in cents) to trigger trade
        categories: Categories to trade
    """

    # Default parameters
    DEFAULT_DAILY_BUDGET = 50.0  # $50/day max
    DEFAULT_MAX_POSITION_PER_MARKET = 100.0  # $100 max per market
    DEFAULT_MIN_EDGE = 5  # 5 cents minimum edge (5% probability difference)
    DEFAULT_MIN_VOLUME = 1000  # Minimum market volume
    DEFAULT_MIN_CONFIDENCE = 60  # Minimum confidence score

    # Kelly fraction (fractional Kelly for safety)
    KELLY_FRACTION = 0.25  # Use 25% of full Kelly

    def __init__(
        self,
        client: Optional[KalshiClient] = None,
        daily_budget: float = DEFAULT_DAILY_BUDGET,
        max_position_per_market: float = DEFAULT_MAX_POSITION_PER_MARKET,
        min_edge: float = DEFAULT_MIN_EDGE,
        categories: Optional[list[str]] = None,
    ):
        """
        Initialize prediction markets strategy.

        Args:
            client: KalshiClient instance (or creates one)
            daily_budget: Maximum daily allocation in USD
            max_position_per_market: Max position per market in USD
            min_edge: Minimum edge in cents to trigger trade
            categories: Categories to trade (default: all)
        """
        if not KALSHI_AVAILABLE:
            raise ImportError("KalshiClient not available")

        # Get daily budget from env or use default
        daily_budget = float(os.getenv("PREDICTION_DAILY_BUDGET", daily_budget))

        self.client = client or get_kalshi_client(paper=True)
        self.daily_budget = daily_budget
        self.max_position_per_market = max_position_per_market
        self.min_edge = min_edge
        self.categories = categories or [c.value for c in MarketCategory]

        # Strategy state
        self.current_positions: dict[str, KalshiPosition] = {}
        self.today_spent: float = 0.0
        self.trades_today: list[PredictionTrade] = []
        self.signals_history: list[PredictionSignal] = []

        logger.info(
            f"PredictionStrategy initialized: daily_budget=${daily_budget}, "
            f"max_per_market=${max_position_per_market}, min_edge={min_edge}c"
        )

    def execute(self) -> dict[str, Any]:
        """
        Execute the prediction markets trading routine.

        Returns:
            Dict with execution results including trades and signals
        """
        logger.info("=" * 70)
        logger.info("PREDICTION MARKETS STRATEGY - Daily Execution")
        logger.info("=" * 70)

        try:
            if not self.client.is_configured():
                logger.warning("Kalshi client not configured - skipping execution")
                return {"success": False, "reason": "not_configured"}

            # Step 1: Load current positions
            self._load_positions()

            # Step 2: Check for exit signals on existing positions
            exit_trades = self._check_exits()

            # Step 3: Scan for new opportunities
            signals = self.scan_markets()

            # Step 4: Execute on actionable signals
            entry_trades = self._execute_signals(signals)

            return {
                "success": True,
                "exit_trades": exit_trades,
                "entry_trades": entry_trades,
                "signals": signals,
                "positions": list(self.current_positions.values()),
                "today_spent": self.today_spent,
                "remaining_budget": self.daily_budget - self.today_spent,
            }

        except Exception as e:
            logger.error(f"Prediction strategy execution failed: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "reason": "error", "error": str(e)}

    def scan_markets(self) -> list[PredictionSignal]:
        """
        Scan prediction markets for trading opportunities.

        Returns:
            List of PredictionSignal objects for actionable markets
        """
        logger.info("Scanning prediction markets for opportunities...")

        signals = []

        try:
            # Get open markets
            markets = self.client.get_markets(status="open", limit=100)
            logger.info(f"Fetched {len(markets)} open markets")

            for market in markets:
                signal = self._analyze_market(market)
                if signal and signal.strength != SignalStrength.NEUTRAL:
                    signals.append(signal)
                    self.signals_history.append(signal)

            # Sort by edge (best opportunities first)
            signals.sort(key=lambda s: abs(s.edge), reverse=True)

            logger.info(f"Found {len(signals)} actionable signals")
            for signal in signals[:5]:  # Log top 5
                logger.info(
                    f"  {signal.market_ticker}: {signal.side.upper()} @ {signal.current_price}c "
                    f"(edge: {signal.edge:+.1f}c, strength: {signal.strength.value})"
                )

            return signals

        except Exception as e:
            logger.error(f"Error scanning markets: {e}")
            return []

    def _analyze_market(self, market: KalshiMarket) -> Optional[PredictionSignal]:
        """
        Analyze a single market for trading opportunity.

        Args:
            market: KalshiMarket to analyze

        Returns:
            PredictionSignal if opportunity exists, None otherwise
        """
        try:
            # Skip low-volume markets
            if market.volume < self.DEFAULT_MIN_VOLUME:
                return None

            # Get current market price
            yes_price = market.yes_price
            no_price = market.no_price

            # Calculate our fair value estimate
            # For now, use simple heuristics - in production, would use models
            fair_value = self._estimate_fair_value(market)

            if fair_value is None:
                return None

            # Calculate edge
            yes_edge = fair_value - yes_price
            no_edge = (100 - fair_value) - no_price

            # Determine best side and edge
            if abs(yes_edge) > abs(no_edge):
                side = "yes"
                edge = yes_edge
                current_price = yes_price
            else:
                side = "no"
                edge = no_edge
                current_price = no_price

            # Check minimum edge threshold
            if abs(edge) < self.min_edge:
                return None

            # Determine signal strength
            if edge > 15:
                strength = SignalStrength.STRONG_YES
            elif edge > 8:
                strength = SignalStrength.MODERATE_YES
            elif edge < -15:
                strength = SignalStrength.STRONG_NO
            elif edge < -8:
                strength = SignalStrength.MODERATE_NO
            else:
                strength = SignalStrength.NEUTRAL

            if strength == SignalStrength.NEUTRAL:
                return None

            # Calculate confidence based on volume and spread
            confidence = self._calculate_confidence(market)

            if confidence < self.DEFAULT_MIN_CONFIDENCE:
                return None

            # Calculate recommended position size using Kelly Criterion
            recommended_size = self._calculate_kelly_size(
                price=current_price,
                fair_value=fair_value,
                confidence=confidence,
            )

            return PredictionSignal(
                market_ticker=market.ticker,
                market_title=market.title,
                side=side,
                current_price=current_price,
                fair_value=fair_value,
                edge=edge,
                strength=strength,
                confidence=confidence,
                recommended_size=recommended_size,
                reasoning=self._generate_reasoning(market, side, edge),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.debug(f"Error analyzing market {market.ticker}: {e}")
            return None

    def _estimate_fair_value(self, market: KalshiMarket) -> Optional[float]:
        """
        Estimate fair value probability for a market.

        This is a placeholder for more sophisticated estimation.
        In production, would use:
        - Polling data for elections
        - Economic models for Fed/inflation
        - Weather forecasts for weather markets
        - Historical patterns and seasonality

        Returns:
            Estimated fair value in cents (0-100), or None if can't estimate
        """
        # For now, use simple contrarian approach:
        # If market is extreme (>85 or <15), lean slightly toward mean reversion
        yes_price = market.yes_price

        # Very high probability - slight contrarian lean
        if yes_price > 85:
            return yes_price - 3  # Slightly lower fair value
        elif yes_price < 15:
            return yes_price + 3  # Slightly higher fair value

        # Markets near 50% - trust market more
        if 40 < yes_price < 60:
            return yes_price  # No edge

        # Moderate extremes - slight contrarian lean
        if yes_price > 70:
            return yes_price - 2
        elif yes_price < 30:
            return yes_price + 2

        return yes_price  # No edge identified

    def _calculate_confidence(self, market: KalshiMarket) -> float:
        """
        Calculate confidence score for our estimate.

        Based on:
        - Market volume (higher = more reliable pricing)
        - Open interest
        - Bid-ask spread (tighter = more reliable)

        Returns:
            Confidence score 0-100
        """
        confidence = 50.0  # Base confidence

        # Volume confidence (up to +20)
        if market.volume > 10000:
            confidence += 20
        elif market.volume > 5000:
            confidence += 15
        elif market.volume > 2000:
            confidence += 10
        elif market.volume > 1000:
            confidence += 5

        # Open interest confidence (up to +15)
        if market.open_interest > 5000:
            confidence += 15
        elif market.open_interest > 2000:
            confidence += 10
        elif market.open_interest > 500:
            confidence += 5

        # Spread confidence (up to +15)
        spread = abs(market.yes_price - (100 - market.no_price))
        if spread < 2:
            confidence += 15
        elif spread < 5:
            confidence += 10
        elif spread < 10:
            confidence += 5

        return min(100, confidence)

    def _calculate_kelly_size(
        self,
        price: float,
        fair_value: float,
        confidence: float,
    ) -> int:
        """
        Calculate position size using fractional Kelly Criterion.

        Kelly formula for binary outcomes:
        f = (bp - q) / b
        where:
        - b = odds (payout per dollar risked)
        - p = probability of winning
        - q = probability of losing (1 - p)

        Returns:
            Recommended number of contracts
        """
        # Convert to probabilities
        p = fair_value / 100  # Our estimated win probability
        price / 100  # Market implied probability

        # For prediction markets: pay $1 if win, lose stake if lose
        # Odds are (100 - price) / price
        b = (100 - price) / price if price > 0 else 0

        if b <= 0:
            return 0

        q = 1 - p

        # Kelly fraction
        kelly = (b * p - q) / b if b > 0 else 0

        # Apply fractional Kelly and confidence adjustment
        adjusted_kelly = kelly * self.KELLY_FRACTION * (confidence / 100)

        if adjusted_kelly <= 0:
            return 0

        # Convert to dollar amount and then contracts
        # Each contract costs (price) cents
        max_investment = min(
            self.max_position_per_market,
            self.daily_budget - self.today_spent,
        )

        if max_investment <= 0:
            return 0

        investment = adjusted_kelly * max_investment
        contracts = int(investment / (price / 100))  # price in cents, so divide by 100 for USD

        return max(0, min(contracts, 100))  # Cap at 100 contracts

    def _generate_reasoning(
        self,
        market: KalshiMarket,
        side: str,
        edge: float,
    ) -> str:
        """Generate human-readable reasoning for the signal."""
        direction = "higher" if edge > 0 else "lower"
        abs_edge = abs(edge)

        return (
            f"Market priced at {market.yes_price}c for YES. "
            f"Our estimate is {abs_edge:.1f}c {direction}. "
            f"Volume: {market.volume:,}, Open Interest: {market.open_interest:,}. "
            f"Recommendation: {side.upper()} contracts."
        )

    def _load_positions(self) -> None:
        """Load current positions from Kalshi."""
        try:
            positions = self.client.get_positions()
            self.current_positions = {p.market_ticker: p for p in positions}
            logger.info(f"Loaded {len(self.current_positions)} existing positions")
        except Exception as e:
            logger.error(f"Error loading positions: {e}")

    def _check_exits(self) -> list[PredictionTrade]:
        """
        Check existing positions for exit signals.

        Exit triggers:
        - Target profit reached (>50% of max payout)
        - Stop loss triggered (>30% loss)
        - Market close approaching
        - Edge reversed

        Returns:
            List of exit trades executed
        """
        exit_trades = []

        for ticker, position in list(self.current_positions.items()):
            try:
                # Get current market state
                market = self.client.get_market(ticker)

                if market.status != "open":
                    continue

                # Check P/L
                current_price = market.yes_price if position.side == "yes" else market.no_price
                entry_price = position.avg_price
                pl_pct = ((current_price - entry_price) / entry_price) if entry_price > 0 else 0

                # Exit on 50% profit
                if pl_pct >= 0.50:
                    logger.info(f"Taking profit on {ticker}: {pl_pct * 100:.1f}% gain")
                    trade = self._execute_exit(position, "take_profit")
                    if trade:
                        exit_trades.append(trade)

                # Exit on 30% loss
                elif pl_pct <= -0.30:
                    logger.info(f"Stopping out of {ticker}: {pl_pct * 100:.1f}% loss")
                    trade = self._execute_exit(position, "stop_loss")
                    if trade:
                        exit_trades.append(trade)

            except Exception as e:
                logger.error(f"Error checking exit for {ticker}: {e}")

        return exit_trades

    def _execute_exit(
        self,
        position: KalshiPosition,
        reason: str,
    ) -> Optional[PredictionTrade]:
        """Execute exit trade for a position."""
        try:
            order = self.client.sell_position(
                ticker=position.market_ticker,
                side=position.side,
                quantity=position.quantity,
            )

            if order.status in ("filled", "pending", "active"):
                trade = PredictionTrade(
                    market_ticker=position.market_ticker,
                    side=position.side,
                    quantity=position.quantity,
                    price=order.avg_fill_price or position.avg_price,
                    amount_usd=position.market_value,
                    order_id=order.id,
                    timestamp=datetime.now(),
                    reasoning=f"Exit: {reason}",
                    attribution={"action": reason},
                )

                # Remove from current positions
                del self.current_positions[position.market_ticker]

                return trade

        except Exception as e:
            logger.error(f"Error executing exit for {position.market_ticker}: {e}")

        return None

    def _execute_signals(self, signals: list[PredictionSignal]) -> list[PredictionTrade]:
        """
        Execute trades on actionable signals.

        Args:
            signals: List of signals to potentially execute

        Returns:
            List of executed trades
        """
        trades = []

        for signal in signals:
            # Check budget
            remaining = self.daily_budget - self.today_spent
            if remaining < 1:
                logger.info("Daily budget exhausted")
                break

            # Skip if already have position in this market
            if signal.market_ticker in self.current_positions:
                continue

            # Skip weak signals
            if signal.strength == SignalStrength.NEUTRAL:
                continue

            try:
                # Calculate order size
                contracts = min(
                    signal.recommended_size, int(remaining / (signal.current_price / 100))
                )

                if contracts < 1:
                    continue

                cost = contracts * (signal.current_price / 100)

                if cost > remaining:
                    contracts = int(remaining / (signal.current_price / 100))
                    cost = contracts * (signal.current_price / 100)

                if contracts < 1:
                    continue

                # Place order
                order = self.client.place_order(
                    ticker=signal.market_ticker,
                    side=signal.side,
                    quantity=contracts,
                    limit_price=signal.current_price + 1,  # 1 cent buffer for limit
                )

                if order.status in ("filled", "pending", "active"):
                    trade = PredictionTrade(
                        market_ticker=signal.market_ticker,
                        side=signal.side,
                        quantity=contracts,
                        price=signal.current_price,
                        amount_usd=cost,
                        order_id=order.id,
                        timestamp=datetime.now(),
                        reasoning=signal.reasoning,
                        attribution={
                            "signal_strength": signal.strength.value,
                            "edge": signal.edge,
                            "confidence": signal.confidence,
                        },
                    )

                    trades.append(trade)
                    self.trades_today.append(trade)
                    self.today_spent += cost

                    logger.info(
                        f"Executed: {signal.side.upper()} {contracts}x {signal.market_ticker} "
                        f"@ {signal.current_price}c (${cost:.2f})"
                    )

            except Exception as e:
                logger.error(f"Error executing signal for {signal.market_ticker}: {e}")

        return trades

    def get_performance_metrics(self) -> dict[str, Any]:
        """
        Calculate performance metrics for the strategy.

        Returns:
            Dictionary of performance statistics
        """
        try:
            # Load current positions
            self._load_positions()

            # Calculate P/L
            total_cost = sum(p.cost_basis for p in self.current_positions.values())
            total_value = sum(p.market_value for p in self.current_positions.values())
            unrealized_pl = total_value - total_cost
            unrealized_pl_pct = (unrealized_pl / total_cost * 100) if total_cost > 0 else 0

            # Trade statistics
            num_trades = len(self.trades_today)
            today_volume = sum(t.amount_usd for t in self.trades_today)

            return {
                "total_cost_basis": total_cost,
                "total_market_value": total_value,
                "unrealized_pl": unrealized_pl,
                "unrealized_pl_pct": unrealized_pl_pct,
                "num_positions": len(self.current_positions),
                "num_trades_today": num_trades,
                "today_volume": today_volume,
                "today_spent": self.today_spent,
                "remaining_budget": self.daily_budget - self.today_spent,
                "positions": [
                    {
                        "ticker": p.market_ticker,
                        "side": p.side,
                        "quantity": p.quantity,
                        "cost_basis": p.cost_basis,
                        "market_value": p.market_value,
                        "unrealized_pl": p.unrealized_pl,
                    }
                    for p in self.current_positions.values()
                ],
            }

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        strategy = PredictionStrategy(daily_budget=50.0)

        # Execute strategy
        result = strategy.execute()

        if result["success"]:
            print("\nExecution successful!")
            print(f"Entry trades: {len(result.get('entry_trades', []))}")
            print(f"Exit trades: {len(result.get('exit_trades', []))}")
            print(f"Signals found: {len(result.get('signals', []))}")
            print(f"Remaining budget: ${result.get('remaining_budget', 0):.2f}")

            # Get metrics
            metrics = strategy.get_performance_metrics()
            print(f"\nPortfolio Value: ${metrics.get('total_market_value', 0):.2f}")
            print(f"Unrealized P/L: ${metrics.get('unrealized_pl', 0):.2f}")
        else:
            print(f"\nExecution failed: {result.get('reason', 'unknown')}")

    except ImportError as e:
        print(f"Kalshi client not available: {e}")
        print("Configure KALSHI_EMAIL and KALSHI_PASSWORD in .env")
