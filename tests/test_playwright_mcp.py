"""Tests for Playwright MCP integration.

These tests verify the Playwright MCP client, sentiment scraper,
and trade verifier functionality.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.integrations.playwright_mcp.client import (
    AccessibilitySnapshot,
    BrowserState,
    PlaywrightMCPClient,
    get_playwright_client,
)
from src.integrations.playwright_mcp.scraper import (
    AggregatedSentiment,
    DataSource,
    MentionData,
    ScrapeResult,
    SentimentScraper,
    SentimentSignal,
)
from src.integrations.playwright_mcp.verifier import (
    PositionSnapshot,
    TradeVerifier,
    VerificationResult,
)

# ============================================================================
# Client Tests
# ============================================================================


class TestPlaywrightMCPClient:
    """Tests for PlaywrightMCPClient."""

    def test_client_initialization(self):
        """Test client initializes with correct defaults."""
        client = PlaywrightMCPClient()

        assert client.headless is True
        assert client.timeout == 30000
        assert client.is_initialized is False
        assert isinstance(client.state, BrowserState)

    def test_client_custom_settings(self, tmp_path):
        """Test client with custom settings."""
        client = PlaywrightMCPClient(
            headless=False,
            timeout=60000,
            screenshots_dir=str(tmp_path / "screenshots"),
        )

        assert client.headless is False
        assert client.timeout == 60000
        assert client.screenshots_dir == tmp_path / "screenshots"

    def test_browser_state_initial(self):
        """Test initial browser state."""
        client = PlaywrightMCPClient()
        state = client.state

        assert state.current_url == ""
        assert state.page_title == ""
        assert state.is_ready is False
        assert state.last_action == ""

    @pytest.mark.asyncio
    async def test_initialize_npx_not_found(self):
        """Test initialization fails gracefully when npx not found."""
        client = PlaywrightMCPClient()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("npx not found")
            result = await client.initialize()

        assert result is False
        assert client.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Test successful initialization."""
        client = PlaywrightMCPClient()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await client.initialize()

        assert result is True
        assert client.is_initialized is True


class TestAccessibilitySnapshot:
    """Tests for AccessibilitySnapshot."""

    def test_snapshot_creation(self):
        """Test creating an accessibility snapshot."""
        tree = {
            "role": "document",
            "name": "Test Page",
            "children": [
                {"role": "button", "name": "Submit"},
                {"role": "link", "name": "Home"},
            ],
        }

        snapshot = AccessibilitySnapshot(
            url="https://example.com",
            title="Test Page",
            tree=tree,
        )

        assert snapshot.url == "https://example.com"
        assert snapshot.title == "Test Page"
        assert snapshot.tree == tree

    def test_find_elements_by_role(self):
        """Test finding elements by role."""
        tree = {
            "role": "document",
            "children": [
                {"role": "button", "name": "Submit"},
                {"role": "button", "name": "Cancel"},
                {"role": "link", "name": "Home"},
            ],
        }

        snapshot = AccessibilitySnapshot(
            url="https://example.com",
            title="Test",
            tree=tree,
        )

        buttons = snapshot.find_elements(role="button")
        assert len(buttons) == 2
        assert buttons[0]["name"] == "Submit"
        assert buttons[1]["name"] == "Cancel"

    def test_find_elements_by_name(self):
        """Test finding elements by name."""
        tree = {
            "role": "document",
            "children": [
                {"role": "button", "name": "Submit Form"},
                {"role": "link", "name": "Submit Link"},
                {"role": "heading", "name": "Title"},
            ],
        }

        snapshot = AccessibilitySnapshot(
            url="https://example.com",
            title="Test",
            tree=tree,
        )

        submit_elements = snapshot.find_elements(name="submit")
        assert len(submit_elements) == 2


# ============================================================================
# Scraper Tests
# ============================================================================


class TestSentimentScraper:
    """Tests for SentimentScraper."""

    def test_scraper_initialization(self):
        """Test scraper initializes with defaults."""
        scraper = SentimentScraper()

        assert scraper.max_posts_per_source == 50
        assert scraper.scroll_depth == 3
        assert scraper.client is not None

    def test_analyze_sentiment_bullish(self):
        """Test bullish sentiment detection."""
        scraper = SentimentScraper()

        signal, confidence = scraper._analyze_sentiment(
            "SPY is going to the moon! 🚀 Diamond hands baby, buy calls!"
        )

        assert signal == SentimentSignal.BULLISH
        assert confidence > 0.6

    def test_analyze_sentiment_bearish(self):
        """Test bearish sentiment detection."""
        scraper = SentimentScraper()

        signal, confidence = scraper._analyze_sentiment(
            "This stock is going to crash hard. Puts all day. 🐻 Bagholders beware!"
        )

        assert signal == SentimentSignal.BEARISH
        assert confidence > 0.6

    def test_analyze_sentiment_neutral(self):
        """Test neutral sentiment detection."""
        scraper = SentimentScraper()

        signal, confidence = scraper._analyze_sentiment(
            "The earnings report will be released next week. Waiting to see results."
        )

        assert signal == SentimentSignal.NEUTRAL

    def test_find_tickers_with_dollar_sign(self):
        """Test finding tickers with $ prefix."""
        scraper = SentimentScraper()

        found = scraper._find_tickers(
            "I'm bullish on $SPY and $QQQ but bearish on $TSLA",
            ["SPY", "QQQ", "TSLA", "AAPL"],
        )

        assert "SPY" in found
        assert "QQQ" in found
        assert "TSLA" in found
        assert "AAPL" not in found

    def test_find_tickers_without_dollar_sign(self):
        """Test finding tickers without $ prefix."""
        scraper = SentimentScraper()

        found = scraper._find_tickers(
            "Looking at SPY and QQQ today for momentum plays",
            ["SPY", "QQQ", "NVDA"],
        )

        assert "SPY" in found
        assert "QQQ" in found
        assert "NVDA" not in found

    def test_parse_count_thousands(self):
        """Test parsing count strings with K suffix."""
        scraper = SentimentScraper()

        assert scraper._parse_count("1.5K") == 1500
        assert scraper._parse_count("10K") == 10000

    def test_parse_count_millions(self):
        """Test parsing count strings with M suffix."""
        scraper = SentimentScraper()

        assert scraper._parse_count("2.3M") == 2300000
        assert scraper._parse_count("1M") == 1000000

    def test_parse_count_plain_number(self):
        """Test parsing plain numbers."""
        scraper = SentimentScraper()

        assert scraper._parse_count("1234") == 1234
        assert scraper._parse_count("5,678") == 5678

    def test_aggregate_sentiment(self):
        """Test sentiment aggregation."""
        scraper = SentimentScraper()

        mentions = [
            MentionData(
                ticker="SPY",
                source=DataSource.REDDIT,
                url="https://reddit.com/r/test",
                title="SPY to the moon!",
                content="",
                sentiment=SentimentSignal.BULLISH,
                confidence=0.8,
                timestamp=datetime.now(),
                upvotes=100,
                comments=20,
            ),
            MentionData(
                ticker="SPY",
                source=DataSource.YOUTUBE,
                url="https://youtube.com/watch",
                title="SPY Analysis",
                content="",
                sentiment=SentimentSignal.BULLISH,
                confidence=0.7,
                timestamp=datetime.now(),
                upvotes=500,
                comments=50,
            ),
            MentionData(
                ticker="SPY",
                source=DataSource.REDDIT,
                url="https://reddit.com/r/test2",
                title="SPY crash incoming",
                content="",
                sentiment=SentimentSignal.BEARISH,
                confidence=0.6,
                timestamp=datetime.now(),
                upvotes=30,
                comments=10,
            ),
        ]

        result = scraper._aggregate_sentiment(["SPY"], mentions)

        assert "SPY" in result
        spy_sentiment = result["SPY"]
        assert spy_sentiment.total_mentions == 3
        assert spy_sentiment.bullish_count == 2
        assert spy_sentiment.bearish_count == 1
        assert spy_sentiment.weighted_score > 0  # More bullish than bearish


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""

    def test_scrape_result_creation(self):
        """Test creating a scrape result."""
        result = ScrapeResult(
            source=DataSource.REDDIT,
            mentions=[],
            total_posts_scanned=100,
            scrape_time=datetime.now(),
            duration_seconds=5.5,
        )

        assert result.source == DataSource.REDDIT
        assert result.total_posts_scanned == 100
        assert result.duration_seconds == 5.5
        assert len(result.errors) == 0


# ============================================================================
# Verifier Tests
# ============================================================================


class TestTradeVerifier:
    """Tests for TradeVerifier."""

    def test_verifier_initialization(self, tmp_path):
        """Test verifier initializes correctly."""
        verifier = TradeVerifier(
            audit_dir=str(tmp_path / "audit"),
            paper_trading=True,
        )

        assert verifier.paper_trading is True
        assert verifier.audit_dir == tmp_path / "audit"

    def test_verifier_urls_paper_trading(self):
        """Test correct URLs for paper trading mode."""
        verifier = TradeVerifier(paper_trading=True)

        assert "paper" in verifier.ALPACA_URLS["paper_dashboard"]
        assert "paper" in verifier.ALPACA_URLS["positions"]

    def test_extract_positions_from_empty_snapshot(self):
        """Test extracting positions from empty snapshot."""
        verifier = TradeVerifier()

        positions = verifier._extract_positions_from_snapshot(None)
        assert positions == []

    def test_verification_result_creation(self, tmp_path):
        """Test creating a verification result."""
        result = VerificationResult(
            verified=True,
            order_id="test-order-123",
            symbol="SPY",
            expected_qty=10.0,
            actual_qty=10.0,
            expected_side="buy",
            screenshot_path=tmp_path / "screenshot.png",
            verification_time=datetime.now(),
        )

        assert result.verified is True
        assert result.order_id == "test-order-123"
        assert result.symbol == "SPY"
        assert len(result.errors) == 0


class TestPositionSnapshot:
    """Tests for PositionSnapshot dataclass."""

    def test_position_snapshot_creation(self, tmp_path):
        """Test creating a position snapshot."""
        snapshot = PositionSnapshot(
            positions=[
                {"symbol": "SPY", "qty": "10", "market_value": "$5000"},
                {"symbol": "QQQ", "qty": "5", "market_value": "$2000"},
            ],
            account_equity=10000.0,
            buying_power=5000.0,
            screenshot_path=tmp_path / "positions.png",
            capture_time=datetime.now(),
        )

        assert len(snapshot.positions) == 2
        assert snapshot.account_equity == 10000.0
        assert snapshot.source == "alpaca_web"


# ============================================================================
# Integration Tests
# ============================================================================


class TestPlaywrightMCPIntegration:
    """Integration tests for the Playwright MCP module."""

    @pytest.mark.asyncio
    async def test_scraper_handles_client_not_initialized(self):
        """Test scraper handles uninitialized client gracefully."""
        scraper = SentimentScraper()

        # Mock the client to simulate initialization failure
        scraper.client = MagicMock()
        scraper.client.is_initialized = False
        scraper.client.initialize = AsyncMock(return_value=False)
        scraper.client.navigate = AsyncMock(return_value=None)

        results = await scraper.scrape_all(["SPY"], [DataSource.REDDIT])

        # Should return empty results, not crash
        assert "SPY" in results
        assert results["SPY"].total_mentions == 0

    @pytest.mark.asyncio
    async def test_verifier_handles_missing_order(self):
        """Test verifier handles missing order gracefully."""
        verifier = TradeVerifier()

        # Mock the client
        verifier.client = MagicMock()
        verifier.client.is_initialized = True
        verifier.client.initialize = AsyncMock(return_value=True)
        verifier.client.navigate = AsyncMock(return_value=None)

        result = await verifier.verify_order_execution(
            order_id="nonexistent-order",
            expected_symbol="SPY",
            expected_qty=10.0,
            expected_side="buy",
        )

        assert result.verified is False
        assert len(result.errors) > 0


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingletonClient:
    """Tests for singleton client pattern."""

    def test_get_playwright_client_returns_same_instance(self):
        """Test that get_playwright_client returns same instance."""
        # Reset singleton
        import src.integrations.playwright_mcp.client as client_module

        client_module._client_instance = None

        client1 = get_playwright_client()
        client2 = get_playwright_client()

        assert client1 is client2

    def test_get_playwright_client_custom_settings_first_call(self):
        """Test custom settings on first call."""
        import src.integrations.playwright_mcp.client as client_module

        client_module._client_instance = None

        client = get_playwright_client(headless=False)

        assert client.headless is False


# ============================================================================
# Data Classes Tests
# ============================================================================


class TestMentionData:
    """Tests for MentionData dataclass."""

    def test_mention_data_creation(self):
        """Test creating mention data."""
        mention = MentionData(
            ticker="NVDA",
            source=DataSource.REDDIT,
            url="https://reddit.com/r/stocks/abc",
            title="NVDA earnings play",
            content="Looking at NVDA calls for earnings...",
            sentiment=SentimentSignal.BULLISH,
            confidence=0.85,
            timestamp=datetime.now(),
            upvotes=150,
            comments=45,
            author="trader123",
            metadata={"subreddit": "stocks"},
        )

        assert mention.ticker == "NVDA"
        assert mention.source == DataSource.REDDIT
        assert mention.sentiment == SentimentSignal.BULLISH
        assert mention.confidence == 0.85


class TestAggregatedSentiment:
    """Tests for AggregatedSentiment dataclass."""

    def test_aggregated_sentiment_creation(self):
        """Test creating aggregated sentiment."""
        sentiment = AggregatedSentiment(
            ticker="AAPL",
            total_mentions=10,
            bullish_count=6,
            bearish_count=2,
            neutral_count=2,
            avg_confidence=0.75,
            weighted_score=0.4,
            sources=[DataSource.REDDIT, DataSource.YOUTUBE],
            top_mentions=[],
        )

        assert sentiment.ticker == "AAPL"
        assert sentiment.total_mentions == 10
        assert sentiment.weighted_score == 0.4
        assert len(sentiment.sources) == 2


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
