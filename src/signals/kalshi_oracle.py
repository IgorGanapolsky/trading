"""
Kalshi Oracle - Cross-Asset Signal Generator from Prediction Markets

Uses Kalshi prediction market odds as leading indicators for correlated assets.
Based on insight: "Prediction markets tell you what is about to happen,
often faster than traditional media." - Kalshi CEO Tarek Mansour

Signal Mappings:
- Fed Rate odds → Bond/Treasury trades (TLT, SHY, BND)
- Election odds → Sector trades (XLE, XLF, XLV)
- Recession odds → Volatility trades (VIX, defensive sectors)

Author: Trading System
Created: 2025-12-09
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    """Direction of trading signal."""

    STRONG_BULLISH = "strong_bullish"  # High conviction buy
    BULLISH = "bullish"  # Moderate buy
    NEUTRAL = "neutral"  # No action
    BEARISH = "bearish"  # Moderate sell/avoid
    STRONG_BEARISH = "strong_bearish"  # High conviction sell


class AssetClass(Enum):
    """Target asset class for signal."""

    EQUITY = "equity"
    BOND = "bond"
    SECTOR = "sector"
    VOLATILITY = "volatility"


@dataclass
class KalshiSignal:
    """Signal generated from Kalshi prediction market data."""

    signal_type: str  # e.g., "fed_rate", "election", "recession"
    direction: SignalDirection
    asset_class: AssetClass
    target_symbols: list[str]  # Symbols to trade based on signal
    confidence: float  # 0-1 confidence score
    kalshi_odds: float  # The Kalshi market odds that triggered signal
    threshold_crossed: str  # Description of threshold
    reasoning: str  # Why this signal was generated
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None  # When signal becomes stale

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to act on."""
        return self.confidence >= 0.6 and self.direction != SignalDirection.NEUTRAL


@dataclass
class MarketOddsSnapshot:
    """Snapshot of Kalshi market odds for analysis."""

    ticker: str
    title: str
    yes_odds: float  # 0-100 cents
    volume: int
    category: str
    fetched_at: datetime


class KalshiOracle:
    """
    Oracle that converts Kalshi prediction market odds into trading signals
    for correlated traditional assets.

    Key insight: Prediction markets aggregate information faster than news,
    making them valuable leading indicators.
    """

    # Threshold configurations for signal generation
    SIGNAL_THRESHOLDS = {
        # Fed Rate signals
        "fed_rate_hike": {
            "pattern": ["KXFED", "FOMC", "RATE"],
            "thresholds": {
                "strong_bullish_bonds": 25,  # <25% hike odds = bullish bonds
                "bullish_bonds": 40,
                "bearish_bonds": 60,
                "strong_bearish_bonds": 75,  # >75% hike odds = bearish bonds
            },
            "targets": {
                "bullish": ["TLT", "BND", "SHY"],  # Long bonds
                "bearish": ["SHV"],  # Short duration only
            },
        },
        # Election signals (example for 2024/future)
        "election_gop": {
            "pattern": ["TRUMP", "GOP", "REPUBLICAN"],
            "thresholds": {
                "strong_signal": 65,  # >65% = strong conviction
                "moderate_signal": 55,
            },
            "targets": {
                "gop_win": ["XLE", "XLF", "ITA"],  # Energy, Financials, Defense
                "dem_win": ["XLV", "ICLN", "TAN"],  # Healthcare, Clean Energy
            },
        },
        # Recession signals
        "recession": {
            "pattern": ["RECESSION", "GDP"],
            "thresholds": {
                "high_risk": 50,  # >50% recession odds
                "elevated_risk": 35,
                "low_risk": 20,
            },
            "targets": {
                "defensive": ["XLU", "XLP", "VNQ"],  # Utilities, Staples, REITs
                "risk_on": ["QQQ", "SPY", "IWM"],  # Growth
            },
        },
        "btc_price": {
            "thresholds": {
                "bullish": 60,  # >60% odds of hitting target
                "bearish": 40,
            },
            "targets": {
            },
        },
    }

    def __init__(self, kalshi_client=None):
        """
        Initialize the Kalshi Oracle.

        Args:
            kalshi_client: Optional KalshiClient instance. If not provided,
                          will attempt to create one from environment variables.
        """
        self.client = kalshi_client
        self._market_cache: dict[str, MarketOddsSnapshot] = {}
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minute cache

        # Try to initialize client if not provided
        if self.client is None:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Kalshi client from environment variables."""
        try:
            from src.brokers.kalshi_client import KalshiClient

            email = os.getenv("KALSHI_EMAIL")
            password = os.getenv("KALSHI_PASSWORD")
            paper = os.getenv("KALSHI_PAPER", "true").lower() == "true"

            if email and password:
                self.client = KalshiClient(email=email, password=password, paper=paper)
                logger.info(f"KalshiOracle initialized with {'paper' if paper else 'live'} client")
            else:
                logger.warning("Kalshi credentials not found - oracle will return empty signals")
        except ImportError:
            logger.warning("KalshiClient not available - oracle disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Kalshi client: {e}")

    def fetch_market_odds(self, force_refresh: bool = False) -> list[MarketOddsSnapshot]:
        """
        Fetch current odds from Kalshi markets.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of MarketOddsSnapshot objects
        """
        if self.client is None:
            logger.warning("No Kalshi client available")
            return []

        # Check cache
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._last_fetch
            and (now - self._last_fetch).total_seconds() < self._cache_ttl_seconds
        ):
            return list(self._market_cache.values())

        try:
            markets = self.client.get_markets(status="open", limit=200)
            snapshots = []

            for market in markets:
                snapshot = MarketOddsSnapshot(
                    ticker=market.ticker,
                    title=market.title,
                    yes_odds=market.yes_price,
                    volume=market.volume,
                    category=market.category,
                    fetched_at=now,
                )
                self._market_cache[market.ticker] = snapshot
                snapshots.append(snapshot)

            self._last_fetch = now
            logger.info(f"Fetched {len(snapshots)} Kalshi markets")
            return snapshots

        except Exception as e:
            logger.error(f"Failed to fetch Kalshi markets: {e}")
            return list(self._market_cache.values())  # Return stale cache

    def _find_markets_by_pattern(
        self, patterns: list[str], markets: list[MarketOddsSnapshot]
    ) -> list[MarketOddsSnapshot]:
        """Find markets matching any of the given patterns."""
        matches = []
        for market in markets:
            for pattern in patterns:
                if (
                    pattern.upper() in market.ticker.upper()
                    or pattern.upper() in market.title.upper()
                ):
                    matches.append(market)
                    break
        return matches

    def generate_fed_signal(self, markets: list[MarketOddsSnapshot]) -> Optional[KalshiSignal]:
        """
        Generate trading signal from Fed rate prediction markets.

        Logic:
        - High rate hike odds (>75%) → Bearish bonds, short duration
        - Low rate hike odds (<25%) → Bullish bonds, long duration
        """
        config = self.SIGNAL_THRESHOLDS["fed_rate_hike"]
        fed_markets = self._find_markets_by_pattern(config["pattern"], markets)

        if not fed_markets:
            return None

        # Use the most liquid Fed market
        fed_markets.sort(key=lambda m: m.volume, reverse=True)
        primary_market = fed_markets[0]
        odds = primary_market.yes_odds

        thresholds = config["thresholds"]

        if odds >= thresholds["strong_bearish_bonds"]:
            return KalshiSignal(
                signal_type="fed_rate",
                direction=SignalDirection.STRONG_BEARISH,
                asset_class=AssetClass.BOND,
                target_symbols=config["targets"]["bearish"],
                confidence=min(odds / 100, 0.95),
                kalshi_odds=odds,
                threshold_crossed=f"Rate hike odds {odds}% > {thresholds['strong_bearish_bonds']}%",
                reasoning=f"High Fed rate hike probability ({odds}%) signals bearish bonds. "
                "Prefer short duration (SHV) over long bonds (TLT).",
            )
        elif odds >= thresholds["bearish_bonds"]:
            return KalshiSignal(
                signal_type="fed_rate",
                direction=SignalDirection.BEARISH,
                asset_class=AssetClass.BOND,
                target_symbols=config["targets"]["bearish"],
                confidence=0.6,
                kalshi_odds=odds,
                threshold_crossed=f"Rate hike odds {odds}% > {thresholds['bearish_bonds']}%",
                reasoning=f"Elevated rate hike probability ({odds}%) - cautious on bonds.",
            )
        elif odds <= thresholds["strong_bullish_bonds"]:
            return KalshiSignal(
                signal_type="fed_rate",
                direction=SignalDirection.STRONG_BULLISH,
                asset_class=AssetClass.BOND,
                target_symbols=config["targets"]["bullish"],
                confidence=min((100 - odds) / 100, 0.95),
                kalshi_odds=odds,
                threshold_crossed=f"Rate hike odds {odds}% < {thresholds['strong_bullish_bonds']}%",
                reasoning=f"Low Fed rate hike probability ({odds}%) signals bullish bonds. "
                "Long duration bonds (TLT, BND) attractive.",
            )
        elif odds <= thresholds["bullish_bonds"]:
            return KalshiSignal(
                signal_type="fed_rate",
                direction=SignalDirection.BULLISH,
                asset_class=AssetClass.BOND,
                target_symbols=config["targets"]["bullish"],
                confidence=0.6,
                kalshi_odds=odds,
                threshold_crossed=f"Rate hike odds {odds}% < {thresholds['bullish_bonds']}%",
                reasoning=f"Moderate rate hold probability ({100 - odds}%) - favorable for bonds.",
            )

        return KalshiSignal(
            signal_type="fed_rate",
            direction=SignalDirection.NEUTRAL,
            asset_class=AssetClass.BOND,
            target_symbols=[],
            confidence=0.3,
            kalshi_odds=odds,
            threshold_crossed="No threshold crossed",
            reasoning=f"Fed rate odds ({odds}%) in neutral zone - no strong signal.",
        )

    def generate_recession_signal(
        self, markets: list[MarketOddsSnapshot]
    ) -> Optional[KalshiSignal]:
        """
        Generate trading signal from recession prediction markets.

        Logic:
        - High recession odds (>50%) → Defensive sectors (utilities, staples)
        - Low recession odds (<20%) → Risk-on (growth, small caps)
        """
        config = self.SIGNAL_THRESHOLDS["recession"]
        recession_markets = self._find_markets_by_pattern(config["pattern"], markets)

        if not recession_markets:
            return None

        recession_markets.sort(key=lambda m: m.volume, reverse=True)
        primary_market = recession_markets[0]
        odds = primary_market.yes_odds

        thresholds = config["thresholds"]

        if odds >= thresholds["high_risk"]:
            return KalshiSignal(
                signal_type="recession",
                direction=SignalDirection.BEARISH,
                asset_class=AssetClass.SECTOR,
                target_symbols=config["targets"]["defensive"],
                confidence=min(odds / 100, 0.90),
                kalshi_odds=odds,
                threshold_crossed=f"Recession odds {odds}% > {thresholds['high_risk']}%",
                reasoning=f"High recession probability ({odds}%) - rotate to defensive "
                "sectors (utilities XLU, staples XLP, REITs VNQ).",
            )
        elif odds >= thresholds["elevated_risk"]:
            return KalshiSignal(
                signal_type="recession",
                direction=SignalDirection.BEARISH,
                asset_class=AssetClass.SECTOR,
                target_symbols=config["targets"]["defensive"][:2],  # Partial rotation
                confidence=0.55,
                kalshi_odds=odds,
                threshold_crossed=f"Recession odds {odds}% > {thresholds['elevated_risk']}%",
                reasoning=f"Elevated recession risk ({odds}%) - consider adding defensives.",
            )
        elif odds <= thresholds["low_risk"]:
            return KalshiSignal(
                signal_type="recession",
                direction=SignalDirection.BULLISH,
                asset_class=AssetClass.SECTOR,
                target_symbols=config["targets"]["risk_on"],
                confidence=min((100 - odds) / 100, 0.85),
                kalshi_odds=odds,
                threshold_crossed=f"Recession odds {odds}% < {thresholds['low_risk']}%",
                reasoning=f"Low recession probability ({odds}%) - risk-on positioning "
                "favored (QQQ, SPY, IWM).",
            )

        return None  # No signal in neutral zone

        """
        """
        config = self.SIGNAL_THRESHOLDS["btc_price"]

            return None

        # Find bullish price target markets (e.g., > $100K by end of year")
        odds = primary_market.yes_odds

        thresholds = config["thresholds"]

        if odds >= thresholds["bullish"]:
            return KalshiSignal(
                signal_type="btc_price",
                direction=SignalDirection.BULLISH,
                confidence=min(odds / 100, 0.85),
                kalshi_odds=odds,
                threshold_crossed=ftarget odds {odds}% > {thresholds['bullish']}%",
                reasoning=f"High probability ({odds}%) of hitting price target - "
            )
        elif odds <= thresholds["bearish"]:
            return KalshiSignal(
                signal_type="btc_price",
                direction=SignalDirection.BEARISH,
                confidence=min((100 - odds) / 100, 0.75),
                kalshi_odds=odds,
                threshold_crossed=ftarget odds {odds}% < {thresholds['bearish']}%",
                reasoning=f"Low probability ({odds}%) of hitting target - "
            )

        return None

    def get_all_signals(self, force_refresh: bool = False) -> list[KalshiSignal]:
        """
        Generate all available signals from current Kalshi markets.

        Returns:
            List of actionable KalshiSignal objects
        """
        markets = self.fetch_market_odds(force_refresh=force_refresh)

        if not markets:
            logger.warning("No Kalshi market data available for signal generation")
            return []

        signals = []

        # Generate signals from each category
        signal_generators = [
            self.generate_fed_signal,
            self.generate_recession_signal,
        ]

        for generator in signal_generators:
            try:
                signal = generator(markets)
                if signal and signal.is_actionable:
                    signals.append(signal)
                    logger.info(
                        f"Generated signal: {signal.signal_type} - "
                        f"{signal.direction.value} - targets: {signal.target_symbols}"
                    )
            except Exception as e:
                logger.error(f"Error generating signal from {generator.__name__}: {e}")

        return signals

    def get_signal_for_symbol(self, symbol: str) -> Optional[KalshiSignal]:
        """
        Get any Kalshi-derived signal relevant to a specific symbol.

        Args:
            symbol: The trading symbol to check (e.g., "TLT", "SPY", )

        Returns:
            KalshiSignal if there's a relevant signal, None otherwise
        """
        signals = self.get_all_signals()

        for signal in signals:
            if symbol in signal.target_symbols:
                return signal

        return None

    def should_trade_symbol(self, symbol: str, proposed_direction: str) -> tuple[bool, str]:
        """
        Check if Kalshi signals support trading a symbol in a given direction.

        The signal's target_symbols represent "what to buy given this market view".
        For example:
        - Bearish bonds signal targeting SHV means "buy SHV (short duration)"
        - Bullish bonds signal targeting TLT means "buy TLT (long bonds)"

        So if a symbol is in the signal's targets, buying it is CONFIRMED
        regardless of whether the signal is bullish/bearish - the signal
        already did the work of determining what to buy.

        Args:
            symbol: Symbol to trade
            proposed_direction: "buy" or "sell"

        Returns:
            Tuple of (should_trade: bool, reason: str)
        """
        signal = self.get_signal_for_symbol(symbol)

        if signal is None:
            return True, "No Kalshi signal - proceed with other indicators"

        # If symbol is in the signal's target_symbols, the signal is recommending it
        if proposed_direction == "buy":
            # Signal recommends this symbol - confirm buy
            return True, f"Kalshi confirms buy: {signal.reasoning}"
        elif proposed_direction == "sell":
            # Signal recommends buying this symbol, so selling is contra-indicated
            return False, f"Kalshi contra-indicates sell: {signal.reasoning}"

        return True, "Kalshi neutral - proceed with other indicators"


# Singleton instance for easy access
_oracle_instance: Optional[KalshiOracle] = None


def get_kalshi_oracle() -> KalshiOracle:
    """Get or create the global KalshiOracle instance."""
    global _oracle_instance
    if _oracle_instance is None:
        _oracle_instance = KalshiOracle()
    return _oracle_instance


def get_kalshi_signals() -> list[KalshiSignal]:
    """Convenience function to get all current Kalshi signals."""
    return get_kalshi_oracle().get_all_signals()
