"""
Tests for Dialogflow CX webhook.

Ensures the webhook correctly:
1. Handles Dialogflow CX request format
2. Queries RAG system for lessons
3. Returns properly formatted responses
4. Handles errors gracefully
"""

import pytest
from unittest.mock import patch, MagicMock


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
        assert response["fulfillmentResponse"]["messages"][0]["text"]["text"] == [
            "Test message"
        ]

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
        """Mock RAG system to avoid ChromaDB dependency."""
        with patch("src.agents.dialogflow_webhook.rag") as mock:
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
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post(
            "/webhook",
            json={
                "text": "what lessons did you learn",
                "sessionInfo": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "fulfillmentResponse" in data
        mock_rag.query.assert_called()

    def test_webhook_extracts_transcript_field(self, mock_rag):
        """Verify webhook extracts query from 'transcript' field."""
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

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
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post("/webhook", json={})

        assert response.status_code == 200
        # Should use default query
        mock_rag.query.assert_called()

    def test_health_endpoint(self, mock_rag):
        """Verify health endpoint returns correct status."""
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "lessons_loaded" in data

    def test_root_endpoint(self, mock_rag):
        """Verify root endpoint returns service info."""
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Trading AI RAG Webhook"
        assert "/webhook" in data["endpoints"]

    def test_test_endpoint(self, mock_rag):
        """Verify test endpoint queries RAG."""
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

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
        with patch("src.agents.dialogflow_webhook.rag") as mock:
            mock.lessons = []
            mock.query.return_value = []
            mock.get_critical_lessons.return_value = []
            yield mock

    def test_webhook_session_info_params(self, mock_rag_empty):
        """Test extracting query from sessionInfo.parameters."""
        from src.agents.dialogflow_webhook import app
        from fastapi.testclient import TestClient

        # Set up mock to return results on second call
        with patch("src.agents.dialogflow_webhook.rag") as mock:
            mock.lessons = []
            mock.query.return_value = [
                {"id": "ll_001", "severity": "INFO", "content": "Test"}
            ]

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
        with patch("src.agents.dialogflow_webhook.rag") as mock:
            mock.lessons = []
            mock.query.return_value = [
                {"id": "ll_001", "severity": "INFO", "content": "Test"}
            ]

            from src.agents.dialogflow_webhook import app
            from fastapi.testclient import TestClient

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
        with patch("src.agents.dialogflow_webhook.rag") as mock:
            mock.lessons = []
            # First call returns empty, second call returns results
            mock.query.side_effect = [
                [],  # First call - no results
                [{"id": "ll_001", "severity": "INFO", "content": "Fallback result"}],  # Fallback
            ]

            from src.agents.dialogflow_webhook import app
            from fastapi.testclient import TestClient

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
        with patch("src.agents.dialogflow_webhook.rag") as mock:
            mock.query.side_effect = Exception("Database error")

            from src.agents.dialogflow_webhook import app
            from fastapi.testclient import TestClient

            client = TestClient(app)

            response = client.post(
                "/webhook",
                json={"text": "test query"},
            )

            # Should return 200 with error message (Dialogflow expects 200)
            assert response.status_code == 200
            data = response.json()
            assert "Error" in data["fulfillmentResponse"]["messages"][0]["text"]["text"][0]


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
