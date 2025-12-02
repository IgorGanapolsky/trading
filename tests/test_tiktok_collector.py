"""
Test suite for TikTok sentiment collector.

Tests TikTok API integration, sentiment analysis, and data extraction.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from src.rag.collectors.tiktok_collector import TikTokCollector


class TestTikTokCollector:
    """Test TikTok collector functionality."""

    @pytest.fixture
    def collector(self):
        """Create TikTokCollector instance for testing."""
        return TikTokCollector()

    @pytest.fixture
    def mock_video_data(self):
        """Mock TikTok API video response data."""
        return {
            "data": {
                "videos": [
                    {
                        "id": "7123456789",
                        "video_description": "$NVDA to the moon! Strong buy signal 🚀📈",
                        "create_time": int(datetime.now().timestamp()),
                        "username": "stocktrader123",
                        "like_count": 1500,
                        "comment_count": 250,
                        "share_count": 100,
                        "view_count": 50000,
                        "hashtag_names": ["stocks", "investing", "NVDA"],
                    },
                    {
                        "id": "7123456790",
                        "video_description": "$SPY bearish trend, selling positions",
                        "create_time": int(datetime.now().timestamp()),
                        "username": "marketanalyst",
                        "like_count": 800,
                        "comment_count": 120,
                        "share_count": 40,
                        "view_count": 25000,
                        "hashtag_names": ["trading", "SPY"],
                    },
                ]
            }
        }

    def test_initialization(self, collector):
        """Test collector initialization."""
        assert collector.source_name == "tiktok"
        assert collector.access_token is None
        assert collector.request_count == 0

    def test_extract_tickers(self, collector):
        """Test ticker extraction from text."""
        # Test single ticker
        text1 = "I'm buying $NVDA today!"
        tickers1 = collector._extract_tickers(text1)
        assert "NVDA" in tickers1
        assert len(tickers1) == 1

        # Test multiple tickers
        text2 = "Portfolio: $SPY $QQQ $NVDA $GOOGL"
        tickers2 = collector._extract_tickers(text2)
        assert tickers2 == {"SPY", "QQQ", "NVDA", "GOOGL"}

        # Test no tickers
        text3 = "Market update for today"
        tickers3 = collector._extract_tickers(text3)
        assert len(tickers3) == 0

        # Test filtering common words
        text4 = "$THE $FOR $AND real ticker is $AAPL"
        tickers4 = collector._extract_tickers(text4)
        assert "AAPL" in tickers4
        assert "THE" not in tickers4
        assert "FOR" not in tickers4

    def test_analyze_sentiment(self, collector):
        """Test sentiment analysis."""
        # Bullish text
        bullish_text = "Strong buy signal! Moon rocket gains 🚀📈"
        bullish_score = collector._analyze_sentiment(bullish_text)
        assert bullish_score > 0

        # Bearish text
        bearish_text = "Sell now! Crash incoming, market will tank"
        bearish_score = collector._analyze_sentiment(bearish_text)
        assert bearish_score < 0

        # Neutral text
        neutral_text = "Market update for today"
        neutral_score = collector._analyze_sentiment(neutral_text)
        assert neutral_score == 0.0

        # Mixed text (more bullish)
        mixed_text = "Some weakness but overall bullish breakout strong"
        mixed_score = collector._analyze_sentiment(mixed_text)
        assert mixed_score > 0

    def test_calculate_engagement_score(self, collector):
        """Test engagement score calculation."""
        # High engagement video
        high_engagement_video = {
            "like_count": 10000,
            "comment_count": 2000,
            "share_count": 500,
            "view_count": 100000,
        }
        high_score = collector._calculate_engagement_score(high_engagement_video)
        assert high_score > 0
        assert high_score <= 100

        # Low engagement video
        low_engagement_video = {
            "like_count": 10,
            "comment_count": 2,
            "share_count": 0,
            "view_count": 1000,
        }
        low_score = collector._calculate_engagement_score(low_engagement_video)
        assert low_score < high_score

        # Zero engagement
        zero_engagement_video = {
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "view_count": 1000,
        }
        zero_score = collector._calculate_engagement_score(zero_engagement_video)
        assert zero_score == 0.0

    @patch("requests.post")
    def test_get_access_token_success(self, mock_post, collector):
        """Test successful OAuth2 token retrieval."""
        # Mock successful auth response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_token_123",
            "expires_in": 7200,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Set credentials
        collector.client_key = "test_key"
        collector.client_secret = "test_secret"

        # Get token
        token = collector._get_access_token()

        assert token == "test_token_123"
        assert collector.access_token == "test_token_123"
        assert collector.token_expires_at is not None

    @patch("requests.post")
    def test_get_access_token_cached(self, mock_post, collector):
        """Test cached token reuse."""
        # Set cached token
        collector.access_token = "cached_token"
        collector.token_expires_at = datetime.now().timestamp() + 3600

        # Get token (should use cache, not call API)
        token = collector._get_access_token()

        assert token == "cached_token"
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_search_videos(self, mock_post, collector, mock_video_data):
        """Test video search functionality."""
        # Mock auth response
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 7200,
        }
        mock_auth_response.raise_for_status = Mock()

        # Mock search response
        mock_search_response = Mock()
        mock_search_response.json.return_value = mock_video_data
        mock_search_response.raise_for_status = Mock()

        # Configure mock to return different responses
        mock_post.side_effect = [mock_auth_response, mock_search_response]

        # Set credentials
        collector.client_key = "test_key"
        collector.client_secret = "test_secret"

        # Search videos
        videos = collector._search_videos(query="stocks", max_results=20, days_back=7)

        assert len(videos) == 2
        assert videos[0]["id"] == "7123456789"
        assert "$NVDA" in videos[0]["video_description"]

    @patch.object(TikTokCollector, "_search_videos")
    def test_collect_ticker_news(self, mock_search, collector):
        """Test ticker-specific news collection."""
        # Mock video data with ticker mention
        mock_search.return_value = [
            {
                "id": "7123456789",
                "video_description": "$NVDA strong buy! 🚀",
                "create_time": int(datetime.now().timestamp()),
                "username": "trader",
                "like_count": 1000,
                "comment_count": 100,
                "share_count": 50,
                "view_count": 20000,
                "hashtag_names": ["stocks", "NVDA"],
            }
        ]

        # Collect news
        articles = collector.collect_ticker_news(ticker="NVDA", days_back=7)

        assert len(articles) > 0
        assert articles[0]["ticker"] == "NVDA"
        assert articles[0]["source"] == "tiktok"
        assert "engagement_score" in articles[0]
        assert articles[0]["sentiment"] > 0.5  # Bullish

    @patch.object(TikTokCollector, "_search_videos")
    def test_get_ticker_sentiment_summary(self, mock_search, collector):
        """Test sentiment summary generation."""
        # Mock multiple videos with varying sentiment
        mock_search.return_value = [
            {
                "id": "1",
                "video_description": "$NVDA bullish! Buy buy buy! 🚀",
                "create_time": int(datetime.now().timestamp()),
                "username": "trader1",
                "like_count": 2000,
                "comment_count": 200,
                "share_count": 100,
                "view_count": 50000,
                "hashtag_names": ["stocks"],
            },
            {
                "id": "2",
                "video_description": "$NVDA looking weak, might sell",
                "create_time": int(datetime.now().timestamp()),
                "username": "trader2",
                "like_count": 500,
                "comment_count": 50,
                "share_count": 10,
                "view_count": 10000,
                "hashtag_names": ["stocks"],
            },
        ]

        # Get summary
        summary = collector.get_ticker_sentiment_summary(ticker="NVDA", days_back=7)

        assert summary["symbol"] == "NVDA"
        assert summary["source"] == "tiktok"
        assert summary["video_count"] == 2
        assert 0 <= summary["sentiment_score"] <= 1
        assert summary["engagement_score"] > 0

    def test_no_credentials_handling(self, collector):
        """Test graceful handling when credentials are missing."""
        # Ensure no credentials
        collector.client_key = None
        collector.client_secret = None

        # Attempt to get token
        token = collector._get_access_token()
        assert token is None

        # Attempt to search (should return empty list)
        videos = collector._search_videos(query="stocks")
        assert videos == []

    @patch.object(TikTokCollector, "_search_videos")
    def test_collect_market_news(self, mock_search, collector):
        """Test general market news collection."""
        # Mock videos without specific ticker
        mock_search.return_value = [
            {
                "id": "1",
                "video_description": "Market update: stocks rising today 📈",
                "create_time": int(datetime.now().timestamp()),
                "username": "marketanalyst",
                "like_count": 1000,
                "comment_count": 100,
                "share_count": 50,
                "view_count": 30000,
                "hashtag_names": ["stockmarket", "investing"],
            }
        ]

        # Collect market news
        articles = collector.collect_market_news(days_back=1)

        assert len(articles) > 0
        assert articles[0]["source"] == "tiktok"
        assert "engagement_score" in articles[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
