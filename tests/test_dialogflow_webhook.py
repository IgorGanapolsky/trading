"""
Tests for Dialogflow CX webhook.

Ensures the webhook correctly:
1. Handles Dialogflow CX request format
2. Queries RAG system for lessons
3. Returns properly formatted responses
4. Handles errors gracefully
"""

from unittest.mock import patch

import pytest

# Skip all tests if fastapi is not installed or has import issues
try:
    import fastapi  # noqa: F401
except (ImportError, SyntaxError, TypeError) as e:
    pytest.skip(
        f"fastapi not available or has import issues: {e}",
        allow_module_level=True,
    )


class TestDialogflowWebhookFormat:
    """Test Dialogflow response format."""

    def test_create_dialogflow_response_format(self):
        """Verify response matches Dialogflow CX webhook format."""
        # Import the function
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import create_dialogflow_response

        response = create_dialogflow_response("Test message")

        # Verify structure matches Dialogflow CX format
        assert "fulfillmentResponse" in response
        assert "messages" in response["fulfillmentResponse"]
        assert len(response["fulfillmentResponse"]["messages"]) == 1
        assert "text" in response["fulfillmentResponse"]["messages"][0]
        assert response["fulfillmentResponse"]["messages"][0]["text"]["text"] == ["Test message"]

    def test_format_lessons_response_no_results(self):
        """Verify empty results return helpful message."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_lessons_response

        result = format_lessons_response([], "test query")

        assert "No lessons found" in result
        assert "test query" in result
        assert "trading" in result or "risk" in result  # Suggests alternatives

    def test_format_lessons_response_with_results(self):
        """Verify lessons are formatted correctly."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_lessons_response

        mock_lessons = [
            {
                "id": "ll_001",
                "severity": "CRITICAL",
                "content": "Test lesson content",
            }
        ]

        result = format_lessons_response(mock_lessons, "test query")

        assert "ll_001" in result
        assert "CRITICAL" in result
        assert "Test lesson content" in result


class TestDialogflowWebhookIntegration:
    """Integration tests for webhook endpoints."""

    @pytest.fixture
    def mock_rag(self):
        """Mock RAG systems to avoid ChromaDB/Vertex AI dependency.

        The dialogflow_webhook module uses local_rag (LessonsLearnedRAG) and vertex_rag.
        We mock local_rag since that's the fallback used in CI (no GCP credentials).
        """
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = [{"id": "ll_001", "severity": "CRITICAL"}]
            mock.query.return_value = [
                {
                    "id": "ll_001",
                    "severity": "CRITICAL",
                    "content": "Test lesson about trading",
                    "snippet": "Test snippet",
                    "score": 0.9,
                }
            ]
            mock.get_critical_lessons.return_value = [{"id": "ll_001"}]
            yield mock

    def test_webhook_extracts_text_field(self, mock_rag):
        """Verify webhook extracts query from 'text' field."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        # Use a query that won't be detected as a trade query
        response = client.post(
            "/webhook",
            json={
                "text": "what failures happened",
                "sessionInfo": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "fulfillmentResponse" in data
        mock_rag.query.assert_called()

    def test_webhook_extracts_transcript_field(self, mock_rag):
        """Verify webhook extracts query from 'transcript' field."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.post(
            "/webhook",
            json={
                "transcript": "tell me about risk management",
                "sessionInfo": {},
            },
        )

        assert response.status_code == 200
        mock_rag.query.assert_called()

    def test_webhook_handles_empty_request(self, mock_rag):
        """Verify webhook handles request with no query gracefully."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.post("/webhook", json={})

        assert response.status_code == 200
        # Should return 200 even with empty request (uses default query)
        data = response.json()
        assert "fulfillmentResponse" in data

    def test_health_endpoint(self, mock_rag):
        """Verify health endpoint returns correct status."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "lessons_loaded" in data

    def test_root_endpoint(self, mock_rag):
        """Verify root endpoint returns service info."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Trading AI RAG Webhook"
        assert "/webhook" in data["endpoints"]

    def test_test_endpoint(self, mock_rag):
        """Verify test endpoint queries RAG."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.get("/test?query=trading%20lessons")

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results_count" in data


class TestDialogflowWebhookEdgeCases:
    """Edge case tests for full coverage."""

    def test_format_lesson_full(self):
        """Test format_lesson_full function."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_lesson_full

        lesson = {
            "content": "# Test Lesson Title\n\nThis is the content.",
            "severity": "CRITICAL",
        }

        result = format_lesson_full(lesson)

        assert "Test Lesson Title" in result
        assert "CRITICAL" in result
        assert "This is the content" in result

    def test_format_lesson_full_no_title(self):
        """Test format_lesson_full with no H1 title."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_lesson_full

        lesson = {
            "content": "Just content without a title header.",
            "severity": "WARNING",
        }

        result = format_lesson_full(lesson)

        assert "WARNING" in result
        assert "Just content" in result

    @pytest.fixture
    def mock_rag_empty(self):
        """Mock RAG that returns empty results."""
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = []
            mock.query.return_value = []
            mock.get_critical_lessons.return_value = []
            yield mock

    def test_webhook_session_info_params(self, mock_rag_empty):
        """Test extracting query from sessionInfo.parameters."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        # Set up mock to return results on second call
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = []
            mock.query.return_value = [{"id": "ll_001", "severity": "INFO", "content": "Test"}]

            client = TestClient(app)

            response = client.post(
                "/webhook",
                json={
                    "sessionInfo": {"parameters": {"query": "risk management"}},
                },
            )

            assert response.status_code == 200

    def test_webhook_fulfillment_tag(self):
        """Test extracting query from fulfillmentInfo.tag."""
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = []
            mock.query.return_value = [{"id": "ll_001", "severity": "INFO", "content": "Test"}]

            from fastapi.testclient import TestClient
            from src.agents.dialogflow_webhook import app

            client = TestClient(app)

            response = client.post(
                "/webhook",
                json={
                    "fulfillmentInfo": {"tag": "trading-tips"},
                },
            )

            assert response.status_code == 200

    def test_webhook_fallback_search(self):
        """Test fallback to broader search when no results."""
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = []
            # First call returns empty, second call returns results
            mock.query.side_effect = [
                [],  # First call - no results
                [{"id": "ll_001", "severity": "INFO", "content": "Fallback result"}],  # Fallback
            ]

            from fastapi.testclient import TestClient
            from src.agents.dialogflow_webhook import app

            client = TestClient(app)

            response = client.post(
                "/webhook",
                json={"text": "obscure query"},
            )

            assert response.status_code == 200
            # Should have called query twice
            assert mock.query.call_count == 2

    def test_webhook_error_handling(self):
        """Test error handling returns proper response."""
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.query.side_effect = Exception("Database error")

            from fastapi.testclient import TestClient
            from src.agents.dialogflow_webhook import app

            client = TestClient(app)

            response = client.post(
                "/webhook",
                json={"text": "test query"},
            )

            # Should return 200 with error message (Dialogflow expects 200)
            assert response.status_code == 200
            data = response.json()
            # Security fix (Jan 10, 2026): Error message no longer exposes exception details
            assert (
                "error occurred"
                in data["fulfillmentResponse"]["messages"][0]["text"]["text"][0].lower()
            )


class TestTradeQueryDetection:
    """Tests for is_trade_query() function with new keywords."""

    def test_is_trade_query_money_keywords(self):
        """Test that money-related queries are detected as trade queries."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_trade_query

        # These should ALL be detected as trade queries
        trade_queries = [
            "How much money we made today?",
            "What are today's profits?",
            "Show me my portfolio balance",
            "How much did we earn?",
            "What's our P/L today?",
            "Account balance please",
            "Show equity",
            "What's my returns?",
            "How are my gains?",
        ]

        for query in trade_queries:
            assert is_trade_query(query), f"Should detect as trade query: '{query}'"

    def test_is_trade_query_lesson_queries(self):
        """Test that lesson queries are NOT detected as trade queries."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_trade_query

        # These should NOT be detected as trade queries
        # Note: avoid words that contain trade keywords (e.g., "learn" contains "earn")
        lesson_queries = [
            "Show me critical failures",
            "What bugs were found?",
            "Tell me about system errors",
            "Describe the incident reports",
        ]

        for query in lesson_queries:
            assert not is_trade_query(query), f"Should NOT detect as trade query: '{query}'"

    def test_is_trade_query_case_insensitive(self):
        """Test that query detection is case insensitive."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_trade_query

        assert is_trade_query("MONEY")
        assert is_trade_query("Money")
        assert is_trade_query("PORTFOLIO BALANCE")


class TestTradeQueryFallbackBehavior:
    """Tests for trade query fallback when no ChromaDB trades exist."""

    def test_trade_query_returns_portfolio_status_not_lessons(self):
        """Verify P/L queries return portfolio data, not lessons."""
        from unittest.mock import patch

        # Note: mock_state removed - using mock_portfolio return value instead

        with patch("src.agents.dialogflow_webhook.local_rag") as mock_rag:
            mock_rag.lessons = []
            mock_rag.query.return_value = [
                {"id": "ll_001", "severity": "INFO", "content": "Test lesson"}
            ]

            with patch(
                "src.agents.dialogflow_webhook.get_current_portfolio_status"
            ) as mock_portfolio:
                mock_portfolio.return_value = {
                    "live": {
                        "equity": 100,
                        "total_pl": 5,
                        "total_pl_pct": 5.0,
                        "positions_count": 0,
                    },
                    "paper": {
                        "equity": 100000,
                        "total_pl": 1000,
                        "total_pl_pct": 1.0,
                        "positions_count": 2,
                        "win_rate": 80.0,
                    },
                    "last_trade_date": "2026-01-05",
                    "trades_today": 0,
                    "challenge_day": 69,
                }

                from fastapi.testclient import TestClient
                from src.agents.dialogflow_webhook import app

                client = TestClient(app)

                response = client.post(
                    "/webhook",
                    json={"text": "How much money did we make today?"},
                )

                assert response.status_code == 200
                data = response.json()
                text = data["fulfillmentResponse"]["messages"][0]["text"]["text"][0]

                # Should return portfolio status, NOT lessons
                assert "Portfolio" in text or "Equity" in text or "P/L" in text
                # Should NOT contain lesson references
                assert "ll_001" not in text

    def test_trade_query_unavailable_portfolio_returns_clear_message(self):
        """Verify P/L queries return trade history or portfolio status, not raw lessons."""
        from unittest.mock import patch

        with patch("src.agents.dialogflow_webhook.local_rag") as mock_rag:
            mock_rag.lessons = []
            mock_rag.query.return_value = [
                {"id": "ll_001", "severity": "INFO", "content": "Test lesson"}
            ]

            with patch(
                "src.agents.dialogflow_webhook.get_current_portfolio_status"
            ) as mock_portfolio:
                mock_portfolio.return_value = {}  # No portfolio data

                from fastapi.testclient import TestClient
                from src.agents.dialogflow_webhook import app

                client = TestClient(app)

                response = client.post(
                    "/webhook",
                    json={"text": "What's my balance?"},
                )

                assert response.status_code == 200
                data = response.json()
                text = data["fulfillmentResponse"]["messages"][0]["text"]["text"][0]

                # Should return trade history, portfolio status, or clear message
                # (trade history is now loaded from local JSON files)
                valid_response = (
                    "Trade History" in text
                    or "Portfolio" in text
                    or "Unavailable" in text
                    or "couldn't retrieve" in text
                )
                assert valid_response, f"Unexpected response: {text[:100]}"
                # Should NOT dump raw lessons
                assert "ll_001" not in text
                assert "Based on our lessons" not in text


class TestPortfolioStatusFunction:
    """Tests for get_current_portfolio_status() function."""

    def test_get_current_portfolio_status_returns_dict(self):
        """Test that function returns a dictionary with expected keys."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import get_current_portfolio_status

        result = get_current_portfolio_status()

        # Should return a dict (may be empty if no state file)
        assert isinstance(result, dict)

        if result:  # If state file exists
            assert "live" in result
            assert "paper" in result
            assert "last_trade_date" in result
            assert "trades_today" in result
            assert "challenge_day" in result

    def test_get_current_portfolio_status_live_account_fields(self):
        """Test that live account has expected fields."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import get_current_portfolio_status

        result = get_current_portfolio_status()

        if result and "live" in result:
            live = result["live"]
            assert "equity" in live
            assert "total_pl" in live
            assert "total_pl_pct" in live
            assert "positions_count" in live

    def test_get_current_portfolio_status_paper_account_fields(self):
        """Test that paper account has expected fields."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import get_current_portfolio_status

        result = get_current_portfolio_status()

        if result and "paper" in result:
            paper = result["paper"]
            assert "equity" in paper
            assert "total_pl" in paper
            assert "win_rate" in paper

    def test_get_current_portfolio_status_github_fallback(self):
        """Test that GitHub fallback is attempted when local file unavailable."""
        import json
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Mock state data that would come from GitHub
        mock_state = {
            "account": {
                "current_equity": 100,
                "total_pl": 5,
                "total_pl_pct": 5.0,
                "positions_count": 0,
            },
            "paper_account": {
                "current_equity": 100000,
                "total_pl": 1000,
                "total_pl_pct": 1.0,
                "positions_count": 2,
                "win_rate": 80.0,
            },
            "trades": {"last_trade_date": "2026-01-05", "total_trades_today": 0},
            "challenge": {"current_day": 69},
        }

        # Patch Path.exists to return False (no local file)
        # Patch urllib.request.urlopen to return mock data
        with patch("pathlib.Path.exists", return_value=False):
            with patch("urllib.request.urlopen") as mock_urlopen:
                # Set up mock response
                mock_response = MagicMock()
                mock_response.read.return_value = json.dumps(mock_state).encode("utf-8")
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                # Re-import to get fresh function
                from src.agents.dialogflow_webhook import get_current_portfolio_status

                _ = get_current_portfolio_status()  # Call function, result not needed for this test

                # GitHub URL should have been called
                mock_urlopen.assert_called()
                call_args = mock_urlopen.call_args
                assert "github.com" in str(call_args) or "githubusercontent" in str(call_args)

    def test_get_current_portfolio_status_returns_empty_on_all_failures(self):
        """Test that empty dict is returned when both local and GitHub fail."""
        import sys
        from pathlib import Path
        from unittest.mock import patch

        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Patch Path.exists to return False (no local file)
        # Patch urllib.request.urlopen to raise exception
        with patch("pathlib.Path.exists", return_value=False):
            with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
                from src.agents.dialogflow_webhook import get_current_portfolio_status

                result = get_current_portfolio_status()

                # Should return empty dict when both sources fail
                assert result == {}


class TestReadinessQueryDetection:
    """Tests for is_readiness_query() function."""

    def test_is_readiness_query_detects_ready_keyword(self):
        """Test that 'ready' queries are detected."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_readiness_query

        readiness_queries = [
            "How ready are we for today's trade?",
            "Are we ready to trade?",
            "ready for trading",
            "Is the system ready?",
        ]

        for query in readiness_queries:
            assert is_readiness_query(query), f"Should detect as readiness query: '{query}'"

    def test_is_readiness_query_detects_prepared_keyword(self):
        """Test that 'prepared' queries are detected."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_readiness_query

        assert is_readiness_query("Are we prepared to trade?")
        assert is_readiness_query("preparation status")

    def test_is_readiness_query_detects_checklist_keywords(self):
        """Test that checklist-related queries are detected."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_readiness_query

        assert is_readiness_query("pre-trade checklist")
        assert is_readiness_query("status check")
        assert is_readiness_query("preflight check")

    def test_is_readiness_query_case_insensitive(self):
        """Test that detection is case insensitive."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_readiness_query

        assert is_readiness_query("READY")
        assert is_readiness_query("Ready")
        assert is_readiness_query("STATUS CHECK")

    def test_is_readiness_query_not_trade_query(self):
        """Test that portfolio queries are NOT detected as readiness."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import is_readiness_query

        non_readiness_queries = [
            "What's my portfolio?",
            "Show me my balance",
            "How much money did we make?",
            "Show me recent trades",
        ]

        for query in non_readiness_queries:
            assert not is_readiness_query(query), f"Should NOT detect as readiness query: '{query}'"


class TestReadinessAssessment:
    """Tests for assess_trading_readiness() function."""

    def test_assess_trading_readiness_returns_dict(self):
        """Test that function returns expected dictionary structure."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import assess_trading_readiness

        result = assess_trading_readiness()

        assert isinstance(result, dict)
        assert "status" in result
        assert "emoji" in result
        assert "score" in result
        assert "max_score" in result
        assert "readiness_pct" in result
        assert "checks" in result
        assert "warnings" in result
        assert "blockers" in result
        assert "timestamp" in result

    def test_assess_trading_readiness_valid_status(self):
        """Test that status is one of expected values."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import assess_trading_readiness

        result = assess_trading_readiness()

        valid_statuses = ["READY", "NOT_READY", "CAUTION", "PARTIAL"]
        assert result["status"] in valid_statuses

    def test_assess_trading_readiness_valid_emoji(self):
        """Test that emoji corresponds to status."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import assess_trading_readiness

        result = assess_trading_readiness()

        # Emoji should match status
        emoji_mapping = {
            "READY": "🟢",
            "NOT_READY": "🔴",
            "CAUTION": "🟡",
            "PARTIAL": "🟡",
        }
        expected_emoji = emoji_mapping[result["status"]]
        assert result["emoji"] == expected_emoji

    def test_assess_trading_readiness_score_bounds(self):
        """Test that score is within bounds."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import assess_trading_readiness

        result = assess_trading_readiness()

        assert result["score"] >= 0
        assert result["score"] <= result["max_score"]
        assert result["readiness_pct"] >= 0
        assert result["readiness_pct"] <= 100

    def test_assess_trading_readiness_lists_are_lists(self):
        """Test that checks/warnings/blockers are lists."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import assess_trading_readiness

        result = assess_trading_readiness()

        assert isinstance(result["checks"], list)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["blockers"], list)


class TestFormatReadinessResponse:
    """Tests for format_readiness_response() function."""

    def test_format_readiness_response_contains_status(self):
        """Test that formatted response contains status."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_readiness_response

        assessment = {
            "status": "READY",
            "emoji": "🟢",
            "score": 80,
            "max_score": 100,
            "readiness_pct": 80.0,
            "checks": ["Market OPEN"],
            "warnings": [],
            "blockers": [],
            "timestamp": "2026-01-06 06:15 AM ET",
        }

        result = format_readiness_response(assessment)

        assert "TRADING READINESS: READY" in result
        assert "🟢" in result
        assert "80%" in result

    def test_format_readiness_response_shows_blockers(self):
        """Test that blockers are displayed."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_readiness_response

        assessment = {
            "status": "NOT_READY",
            "emoji": "🔴",
            "score": 20,
            "max_score": 100,
            "readiness_pct": 20.0,
            "checks": [],
            "warnings": [],
            "blockers": ["Market CLOSED - Weekend"],
            "timestamp": "2026-01-06 06:15 AM ET",
        }

        result = format_readiness_response(assessment)

        assert "BLOCKERS" in result
        assert "Market CLOSED" in result
        assert "Do NOT trade" in result

    def test_format_readiness_response_shows_warnings(self):
        """Test that warnings are displayed."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_readiness_response

        assessment = {
            "status": "CAUTION",
            "emoji": "🟡",
            "score": 60,
            "max_score": 100,
            "readiness_pct": 60.0,
            "checks": ["System state loaded"],
            "warnings": ["Market opens in 30 minutes", "Live capital building"],
            "blockers": [],
            "timestamp": "2026-01-06 06:15 AM ET",
        }

        result = format_readiness_response(assessment)

        assert "WARNINGS" in result
        assert "Market opens" in result
        assert "reduced position sizes" in result

    def test_format_readiness_response_shows_checks(self):
        """Test that passing checks are displayed."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import format_readiness_response

        assessment = {
            "status": "READY",
            "emoji": "🟢",
            "score": 100,
            "max_score": 100,
            "readiness_pct": 100.0,
            "checks": ["Market OPEN", "Win rate strong: 80%"],
            "warnings": [],
            "blockers": [],
            "timestamp": "2026-01-06 06:15 AM ET",
        }

        result = format_readiness_response(assessment)

        assert "PASSING" in result
        assert "Market OPEN" in result
        assert "All systems GO" in result


class TestReadinessWebhookIntegration:
    """Integration tests for readiness queries through webhook."""

    @pytest.fixture
    def mock_rag(self):
        """Mock RAG system."""
        with patch("src.agents.dialogflow_webhook.local_rag") as mock:
            mock.lessons = []
            mock.query.return_value = []
            mock.get_critical_lessons.return_value = []
            yield mock

    def test_webhook_routes_readiness_query(self, mock_rag):
        """Verify readiness queries are routed correctly."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.post(
            "/webhook",
            json={"text": "How ready are we for today's trade?"},
        )

        assert response.status_code == 200
        data = response.json()
        text = data["fulfillmentResponse"]["messages"][0]["text"]["text"][0]

        # Should return readiness assessment, not lessons or portfolio
        assert "TRADING READINESS" in text
        # Should NOT call RAG query for lessons
        mock_rag.query.assert_not_called()

    def test_webhook_readiness_takes_priority_over_trade(self, mock_rag):
        """Verify readiness query takes priority over trade query."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        # This query contains both "ready" and "trade" keywords
        response = client.post(
            "/webhook",
            json={"text": "Are we ready to trade today?"},
        )

        assert response.status_code == 200
        data = response.json()
        text = data["fulfillmentResponse"]["messages"][0]["text"]["text"][0]

        # Should return readiness assessment (priority)
        assert "TRADING READINESS" in text

    def test_test_readiness_endpoint(self, mock_rag):
        """Verify /test-readiness endpoint works."""
        from fastapi.testclient import TestClient
        from src.agents.dialogflow_webhook import app

        client = TestClient(app)

        response = client.get("/test-readiness")

        assert response.status_code == 200
        data = response.json()

        assert data["query_type"] == "readiness"
        assert "assessment" in data
        assert "formatted_response" in data
        assert "status" in data["assessment"]


class TestDialogflowWebhookSmokeTests:
    """Smoke tests for webhook reliability."""

    def test_webhook_module_imports(self):
        """Verify webhook module imports without errors."""
        try:
            from src.agents import dialogflow_webhook

            assert hasattr(dialogflow_webhook, "app")
            assert hasattr(dialogflow_webhook, "webhook")
            assert hasattr(dialogflow_webhook, "create_dialogflow_response")
        except ImportError as e:
            pytest.skip(f"Webhook dependencies not available: {e}")

    def test_webhook_response_not_truncated(self):
        """Verify long responses are not truncated."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from src.agents.dialogflow_webhook import create_dialogflow_response

        # Create a long message (1000+ chars)
        long_message = "A" * 2000

        response = create_dialogflow_response(long_message)

        # Verify full message is in response
        assert len(response["fulfillmentResponse"]["messages"][0]["text"]["text"][0]) == 2000

    def test_no_hardcoded_broker_responses(self):
        """Verify webhook doesn't contain hardcoded broker references."""
        from pathlib import Path

        webhook_path = Path(__file__).parent.parent / "src" / "agents" / "dialogflow_webhook.py"
        content = webhook_path.read_text()

        # These should NOT appear in hardcoded responses
        forbidden_patterns = [
            "Kalshi",  # We don't use Kalshi
            "Tradier",  # Tradier was removed Dec 2025
            "feeds are active",  # Hardcoded status response
        ]

        for pattern in forbidden_patterns:
            assert pattern not in content, f"Found forbidden hardcoded pattern: {pattern}"


class TestTradeQueryWordBoundary:
    """
    Regression tests for word boundary matching in is_trade_query().

    Bug (Jan 11, 2026): "lessons learned" was detected as trade query
    because "learned" contains "earn" as substring.
    """

    def test_lessons_learned_not_trade_query(self):
        """lessons learned should NOT be a trade query."""
        from src.agents.dialogflow_webhook import is_trade_query

        assert is_trade_query("What lessons did we learn?") is False
        assert is_trade_query("Tell me about lessons learned") is False
        assert is_trade_query("What was the last lesson you learned?") is False

    def test_actual_earn_is_trade_query(self):
        """Actual 'earn' word should be a trade query."""
        from src.agents.dialogflow_webhook import is_trade_query

        assert is_trade_query("What did I earn today?") is True
        assert is_trade_query("How much did we earn?") is True

    def test_other_false_positives_prevented(self):
        """Other potential false positives should be prevented."""
        from src.agents.dialogflow_webhook import is_trade_query

        # "made" in "automated" - should NOT match
        assert is_trade_query("How is the automated system?") is False
        # "loss" in "lossless" - should NOT match
        assert is_trade_query("Is the data lossless?") is False
        # "gain" in "again" - should NOT match
        assert is_trade_query("Try again") is False


class TestAnalyticalQueryDetection:
    """
    Tests for is_analytical_query() function (added Jan 13, 2026).

    Analytical queries (WHY, explain, etc.) should be routed to RAG
    for semantic understanding, not to simple portfolio status display.

    Bug: "Why did we not make money yesterday" was returning generic
    portfolio status instead of actually analyzing the question.
    """

    def test_why_questions_are_analytical(self):
        """WHY questions should be detected as analytical."""
        from src.agents.dialogflow_webhook import is_analytical_query

        analytical_queries = [
            "Why did we not make money yesterday?",
            "Why are we losing money?",
            "Why didn't the trade execute?",
            "Why is the system not trading?",
        ]

        for query in analytical_queries:
            assert is_analytical_query(query), f"Should detect as analytical: '{query}'"

    def test_explain_questions_are_analytical(self):
        """EXPLAIN/HOW COME questions should be analytical."""
        from src.agents.dialogflow_webhook import is_analytical_query

        analytical_queries = [
            "Explain what went wrong with our trades",
            "How come we lost on that trade?",
            "What happened to our profits?",
            "Tell me about why we didn't trade",
        ]

        for query in analytical_queries:
            assert is_analytical_query(query), f"Should detect as analytical: '{query}'"

    def test_in_detail_is_analytical(self):
        """Requests for detailed analysis should be analytical."""
        from src.agents.dialogflow_webhook import is_analytical_query

        assert is_analytical_query("Tell me in detail why we lost money")
        assert is_analytical_query("Please explain in detail the trade results")

    def test_simple_status_queries_not_analytical(self):
        """Simple status queries should NOT be analytical."""
        from src.agents.dialogflow_webhook import is_analytical_query

        non_analytical_queries = [
            "Show me my trades",
            "How much did we make today?",
            "What's my portfolio balance?",
            "Portfolio status",
            "Account balance",
        ]

        for query in non_analytical_queries:
            assert not is_analytical_query(query), f"Should NOT be analytical: '{query}'"

    def test_analytical_query_case_insensitive(self):
        """Analytical detection should be case insensitive."""
        from src.agents.dialogflow_webhook import is_analytical_query

        assert is_analytical_query("WHY did we lose money?")
        assert is_analytical_query("EXPLAIN the trade failure")
        assert is_analytical_query("What HAPPENED to profits?")


class TestDirectPLQueryDetection:
    """
    Tests for is_direct_pl_query() function (added Jan 13, 2026).

    Direct P/L queries like "How much money we made today?" should get
    conversational answers, not full portfolio dumps.
    """

    def test_direct_pl_queries_detected(self):
        """Test that direct P/L questions are detected correctly."""
        from src.agents.dialogflow_webhook import is_direct_pl_query

        direct_pl_queries = [
            "How much money we made today?",
            "How much did we make?",
            "What's our profit today?",
            "Did we make money?",
            "How are we doing today?",
            "What did we make?",
            "Any profit today?",
            "how much money did we earn",
            "did we earn anything today",
        ]
        for query in direct_pl_queries:
            assert is_direct_pl_query(query), f"Should be direct P/L: '{query}'"

    def test_non_direct_pl_queries(self):
        """Non-direct P/L questions should not match."""
        from src.agents.dialogflow_webhook import is_direct_pl_query

        non_direct_queries = [
            "What lessons did we learn?",
            "Show me the portfolio",
            "What is our strategy?",
            "Tell me about risk management",
            "List all positions",
        ]
        for query in non_direct_queries:
            assert not is_direct_pl_query(query), f"NOT direct P/L: '{query}'"

    def test_direct_pl_case_insensitive(self):
        """Direct P/L detection should be case insensitive."""
        from src.agents.dialogflow_webhook import is_direct_pl_query

        assert is_direct_pl_query("HOW MUCH MONEY we made?")
        assert is_direct_pl_query("Did We Make Money?")
        assert is_direct_pl_query("ANY PROFIT today?")
