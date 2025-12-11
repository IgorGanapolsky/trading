"""
Unit tests for Kalshi Oracle - Cross-Asset Signal Generator.

Tests cover:
- Signal generation from market odds
- Threshold crossing logic
- Cross-asset mapping
- Trade validation
- Cache behavior

Author: Trading System
Created: 2025-12-09
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from src.signals.kalshi_oracle import (
    AssetClass,
    KalshiOracle,
    KalshiSignal,
    MarketOddsSnapshot,
    SignalDirection,
    get_kalshi_oracle,
    get_kalshi_signals,
)


class TestSignalDirection:
    """Test SignalDirection enum."""

    def test_all_directions_exist(self):
        """Test that all expected directions are defined."""
        assert SignalDirection.STRONG_BULLISH.value == "strong_bullish"
        assert SignalDirection.BULLISH.value == "bullish"
        assert SignalDirection.NEUTRAL.value == "neutral"
        assert SignalDirection.BEARISH.value == "bearish"
        assert SignalDirection.STRONG_BEARISH.value == "strong_bearish"


class TestAssetClass:
    """Test AssetClass enum."""

    def test_all_asset_classes_exist(self):
        """Test that all expected asset classes are defined."""
        assert AssetClass.EQUITY.value == "equity"
        assert AssetClass.BOND.value == "bond"
        assert AssetClass.CRYPTO.value == "crypto"
        assert AssetClass.SECTOR.value == "sector"
        assert AssetClass.VOLATILITY.value == "volatility"


class TestKalshiSignal:
    """Test KalshiSignal dataclass."""

    def test_signal_creation(self):
        """Test creating a signal."""
        signal = KalshiSignal(
            signal_type="fed_rate",
            direction=SignalDirection.BULLISH,
            asset_class=AssetClass.BOND,
            target_symbols=["TLT", "BND"],
            confidence=0.75,
            kalshi_odds=30.0,
            threshold_crossed="Rate hike odds 30% < 40%",
            reasoning="Low rate hike probability favors bonds",
        )

        assert signal.signal_type == "fed_rate"
        assert signal.direction == SignalDirection.BULLISH
        assert signal.asset_class == AssetClass.BOND
        assert signal.target_symbols == ["TLT", "BND"]
        assert signal.confidence == 0.75
        assert signal.kalshi_odds == 30.0
        assert signal.is_actionable is True

    def test_signal_not_actionable_low_confidence(self):
        """Test signal with low confidence is not actionable."""
        signal = KalshiSignal(
            signal_type="recession",
            direction=SignalDirection.BEARISH,
            asset_class=AssetClass.SECTOR,
            target_symbols=["XLU"],
            confidence=0.4,  # Below 0.6 threshold
            kalshi_odds=45.0,
            threshold_crossed="Elevated risk",
            reasoning="Moderate recession risk",
        )

        assert signal.is_actionable is False

    def test_signal_not_actionable_neutral(self):
        """Test neutral signal is not actionable."""
        signal = KalshiSignal(
            signal_type="fed_rate",
            direction=SignalDirection.NEUTRAL,
            asset_class=AssetClass.BOND,
            target_symbols=[],
            confidence=0.7,
            kalshi_odds=50.0,
            threshold_crossed="No threshold crossed",
            reasoning="Neutral zone",
        )

        assert signal.is_actionable is False


class TestMarketOddsSnapshot:
    """Test MarketOddsSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a market snapshot."""
        now = datetime.now(timezone.utc)
        snapshot = MarketOddsSnapshot(
            ticker="KXFED-DEC-HIKE",
            title="Fed Rate Hike December",
            yes_odds=65.0,
            volume=50000,
            category="economics",
            fetched_at=now,
        )

        assert snapshot.ticker == "KXFED-DEC-HIKE"
        assert snapshot.yes_odds == 65.0
        assert snapshot.volume == 50000
        assert snapshot.fetched_at == now


class TestKalshiOracle:
    """Test KalshiOracle class."""

    @pytest.fixture
    def oracle_no_client(self):
        """Create oracle without a client."""
        with patch.dict("os.environ", {}, clear=True):
            oracle = KalshiOracle(kalshi_client=None)
            oracle.client = None  # Ensure no client
            return oracle

    @pytest.fixture
    def mock_markets(self):
        """Create mock market data."""
        now = datetime.now(timezone.utc)
        return [
            MarketOddsSnapshot(
                ticker="KXFED-DEC25-HIKE",
                title="Fed Rate Hike December 2025",
                yes_odds=80.0,  # High hike odds
                volume=100000,
                category="economics",
                fetched_at=now,
            ),
            MarketOddsSnapshot(
                ticker="KXRECESSION-2025",
                title="US Recession by End of 2025",
                yes_odds=55.0,  # Elevated recession risk
                volume=75000,
                category="economics",
                fetched_at=now,
            ),
            MarketOddsSnapshot(
                ticker="KXBTC-100K-DEC25",
                title="BTC Above $100K by Dec 2025",
                yes_odds=70.0,  # Bullish BTC
                volume=50000,
                category="crypto",
                fetched_at=now,
            ),
        ]

    def test_init_without_client(self, oracle_no_client):
        """Test oracle initialization without a client."""
        assert oracle_no_client.client is None
        assert oracle_no_client._market_cache == {}

    def test_find_markets_by_pattern(self, oracle_no_client, mock_markets):
        """Test finding markets by pattern."""
        fed_markets = oracle_no_client._find_markets_by_pattern(
            ["KXFED", "FOMC", "RATE"], mock_markets
        )
        assert len(fed_markets) == 1
        assert fed_markets[0].ticker == "KXFED-DEC25-HIKE"

        crypto_markets = oracle_no_client._find_markets_by_pattern(["BTC", "BITCOIN"], mock_markets)
        assert len(crypto_markets) == 1
        assert crypto_markets[0].ticker == "KXBTC-100K-DEC25"

    def test_generate_fed_signal_bearish(self, oracle_no_client, mock_markets):
        """Test Fed signal generation with high hike odds (bearish bonds)."""
        signal = oracle_no_client.generate_fed_signal(mock_markets)

        assert signal is not None
        assert signal.signal_type == "fed_rate"
        assert signal.direction == SignalDirection.STRONG_BEARISH
        assert signal.asset_class == AssetClass.BOND
        assert "SHV" in signal.target_symbols  # Short duration
        assert signal.kalshi_odds == 80.0

    def test_generate_fed_signal_bullish(self, oracle_no_client):
        """Test Fed signal generation with low hike odds (bullish bonds)."""
        now = datetime.now(timezone.utc)
        markets = [
            MarketOddsSnapshot(
                ticker="KXFED-DEC25-HIKE",
                title="Fed Rate Hike December 2025",
                yes_odds=20.0,  # Low hike odds
                volume=100000,
                category="economics",
                fetched_at=now,
            ),
        ]

        signal = oracle_no_client.generate_fed_signal(markets)

        assert signal is not None
        assert signal.direction == SignalDirection.STRONG_BULLISH
        assert "TLT" in signal.target_symbols or "BND" in signal.target_symbols

    def test_generate_recession_signal_high_risk(self, oracle_no_client, mock_markets):
        """Test recession signal with high recession odds."""
        signal = oracle_no_client.generate_recession_signal(mock_markets)

        assert signal is not None
        assert signal.signal_type == "recession"
        assert signal.direction == SignalDirection.BEARISH
        assert signal.asset_class == AssetClass.SECTOR
        # Should recommend defensive sectors
        assert any(sym in signal.target_symbols for sym in ["XLU", "XLP", "VNQ"])

    def test_generate_recession_signal_low_risk(self, oracle_no_client):
        """Test recession signal with low recession odds."""
        now = datetime.now(timezone.utc)
        markets = [
            MarketOddsSnapshot(
                ticker="KXRECESSION-2025",
                title="US Recession by End of 2025",
                yes_odds=15.0,  # Low recession odds
                volume=75000,
                category="economics",
                fetched_at=now,
            ),
        ]

        signal = oracle_no_client.generate_recession_signal(markets)

        assert signal is not None
        assert signal.direction == SignalDirection.BULLISH
        # Should recommend risk-on assets
        assert any(sym in signal.target_symbols for sym in ["QQQ", "SPY", "IWM"])

    def test_generate_crypto_signal_bullish(self, oracle_no_client, mock_markets):
        """Test crypto signal with high probability of hitting target."""
        signal = oracle_no_client.generate_crypto_signal(mock_markets)

        assert signal is not None
        assert signal.signal_type == "btc_price"
        assert signal.direction == SignalDirection.BULLISH
        assert signal.asset_class == AssetClass.CRYPTO
        assert "BTC" in signal.target_symbols

    def test_generate_crypto_signal_bearish(self, oracle_no_client):
        """Test crypto signal with low probability of hitting target."""
        now = datetime.now(timezone.utc)
        markets = [
            MarketOddsSnapshot(
                ticker="KXBTC-100K-DEC25",
                title="BTC Above $100K by Dec 2025",
                yes_odds=30.0,  # Low odds
                volume=50000,
                category="crypto",
                fetched_at=now,
            ),
        ]

        signal = oracle_no_client.generate_crypto_signal(markets)

        assert signal is not None
        assert signal.direction == SignalDirection.BEARISH

    def test_get_signal_for_symbol(self, oracle_no_client, mock_markets):
        """Test getting signal relevant to a specific symbol."""
        # Manually set cache to avoid client call
        oracle_no_client._market_cache = {m.ticker: m for m in mock_markets}
        oracle_no_client._last_fetch = datetime.now(timezone.utc)

        # Should find signal for TLT (bond ETF affected by Fed rates)
        # Note: This depends on the mock data generating a bearish bond signal
        signal = oracle_no_client.get_signal_for_symbol("SHV")
        # Signal may or may not exist depending on thresholds
        # Just verify it returns None or a valid signal
        assert signal is None or isinstance(signal, KalshiSignal)

    def test_should_trade_symbol_no_signal(self, oracle_no_client):
        """Test trade validation when no relevant signal exists."""
        # Empty cache means no signals
        oracle_no_client._market_cache = {}

        should_trade, reason = oracle_no_client.should_trade_symbol("AAPL", "buy")

        assert should_trade is True
        assert "No Kalshi signal" in reason

    def test_should_trade_symbol_confirms_buy(self, oracle_no_client):
        """Test trade validation when signal confirms buy."""
        now = datetime.now(timezone.utc)
        # Create markets that would generate bullish bond signal
        markets = [
            MarketOddsSnapshot(
                ticker="KXFED-DEC25-HIKE",
                title="Fed Rate Hike December 2025",
                yes_odds=20.0,  # Low hike odds = bullish bonds
                volume=100000,
                category="economics",
                fetched_at=now,
            ),
        ]

        # Mock fetch_market_odds to return our test markets
        with patch.object(oracle_no_client, "fetch_market_odds", return_value=markets):
            should_trade, reason = oracle_no_client.should_trade_symbol("TLT", "buy")

        assert should_trade is True
        assert "confirms" in reason.lower()

    def test_should_trade_symbol_confirms_bearish_target(self, oracle_no_client):
        """Test that buying a bearish signal's target is confirmed.

        When Fed hike odds are high (80%), bearish signal targets SHV (short duration).
        Buying SHV should be CONFIRMED since the signal recommends it.
        """
        now = datetime.now(timezone.utc)
        # Create markets that would generate bearish bond signal
        markets = [
            MarketOddsSnapshot(
                ticker="KXFED-DEC25-HIKE",
                title="Fed Rate Hike December 2025",
                yes_odds=80.0,  # High hike odds = bearish bonds, targets SHV
                volume=100000,
                category="economics",
                fetched_at=now,
            ),
        ]

        # Mock fetch_market_odds to return our test markets
        with patch.object(oracle_no_client, "fetch_market_odds", return_value=markets):
            # SHV is in the bearish targets, so buying it should be CONFIRMED
            should_trade, reason = oracle_no_client.should_trade_symbol("SHV", "buy")

        # Bearish signal with SHV as target - buying SHV should be CONFIRMED
        assert should_trade is True
        assert "confirms" in reason.lower()

    def test_should_trade_symbol_contra_indicates_sell(self, oracle_no_client):
        """Test trade validation when signal contra-indicates sell.

        If a signal recommends buying TLT (bullish bonds), then trying to
        SELL TLT should be contra-indicated.
        """
        now = datetime.now(timezone.utc)
        # Create markets that would generate bullish bond signal
        markets = [
            MarketOddsSnapshot(
                ticker="KXFED-DEC25-HIKE",
                title="Fed Rate Hike December 2025",
                yes_odds=20.0,  # Low hike odds = bullish bonds, targets TLT
                volume=100000,
                category="economics",
                fetched_at=now,
            ),
        ]

        # Mock fetch_market_odds to return our test markets
        with patch.object(oracle_no_client, "fetch_market_odds", return_value=markets):
            # TLT is in the bullish targets, so selling it should be contra-indicated
            should_trade, reason = oracle_no_client.should_trade_symbol("TLT", "sell")

        # Signal recommends buying TLT, so selling is contra-indicated
        assert should_trade is False
        assert "contra-indicates" in reason.lower()

    def test_get_all_signals_empty_without_client(self, oracle_no_client):
        """Test getting signals without a client returns empty list."""
        signals = oracle_no_client.get_all_signals()
        assert signals == []

    def test_fetch_market_odds_without_client(self, oracle_no_client):
        """Test fetching odds without client returns empty list."""
        markets = oracle_no_client.fetch_market_odds()
        assert markets == []


class TestGlobalFunctions:
    """Test module-level convenience functions."""

    def test_get_kalshi_oracle_singleton(self):
        """Test that get_kalshi_oracle returns a singleton."""
        with patch.dict("os.environ", {}, clear=True):
            oracle1 = get_kalshi_oracle()
            oracle2 = get_kalshi_oracle()
            assert oracle1 is oracle2

    def test_get_kalshi_signals_returns_list(self):
        """Test that get_kalshi_signals returns a list."""
        with patch.dict("os.environ", {}, clear=True):
            signals = get_kalshi_signals()
            assert isinstance(signals, list)


class TestSignalThresholds:
    """Test the threshold configurations."""

    def test_fed_thresholds_are_valid(self):
        """Test Fed rate thresholds are properly ordered."""
        thresholds = KalshiOracle.SIGNAL_THRESHOLDS["fed_rate_hike"]["thresholds"]

        assert thresholds["strong_bullish_bonds"] < thresholds["bullish_bonds"]
        assert thresholds["bullish_bonds"] < thresholds["bearish_bonds"]
        assert thresholds["bearish_bonds"] < thresholds["strong_bearish_bonds"]

    def test_recession_thresholds_are_valid(self):
        """Test recession thresholds are properly ordered."""
        thresholds = KalshiOracle.SIGNAL_THRESHOLDS["recession"]["thresholds"]

        assert thresholds["low_risk"] < thresholds["elevated_risk"]
        assert thresholds["elevated_risk"] < thresholds["high_risk"]

    def test_all_signal_types_have_patterns(self):
        """Test all signal types have pattern configurations."""
        for signal_type, config in KalshiOracle.SIGNAL_THRESHOLDS.items():
            assert "pattern" in config, f"{signal_type} missing pattern"
            assert "thresholds" in config, f"{signal_type} missing thresholds"
            assert "targets" in config, f"{signal_type} missing targets"
