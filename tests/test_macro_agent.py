"""Unit tests for the MacroeconomicAgent."""

import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.agents.macro_agent import MacroeconomicAgent


class TestMacroeconomicAgent(unittest.TestCase):
    def setUp(self):
        """Set up for each test."""
        self.cache_path = Path("test_cache/macro_context.json")
        self.cache_path.parent.mkdir(exist_ok=True)

        # We need to mock the dependencies during init to avoid real connections
        with (
            patch("src.agents.macro_agent.SentimentRAGStore"),
            patch("src.agents.macro_agent.LangChainSentimentAgent"),
        ):
            self.agent = MacroeconomicAgent(cache_path=self.cache_path, cache_ttl_hours=1)

        # Replace internal components with mocks for testing
        self.agent.rag_store = MagicMock()
        self.agent.llm_agent = MagicMock()

    def tearDown(self):
        """Clean up after each test."""
        if self.cache_path.exists():
            self.cache_path.unlink()
        if self.cache_path.parent.exists():
            try:
                self.cache_path.parent.rmdir()
            except OSError:
                pass

    def test_get_macro_context_from_cache(self):
        """Test that a valid cache is read correctly."""
        # Arrange
        cached_data = {
            "state": "DOVISH",
            "reason": "Cached reason",
            "confidence": 0.8,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.cache_path.write_text(json.dumps(cached_data))

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "DOVISH")
        self.assertEqual(context["reason"], "Cached reason")
        self.agent.rag_store.query.assert_not_called()
        self.agent.llm_agent.analyze_news.assert_not_called()

    def test_get_macro_context_stale_cache(self):
        """Test that a stale cache triggers a new analysis."""
        # Arrange
        stale_timestamp = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        cached_data = {
            "state": "DOVISH",
            "reason": "Stale reason",
            "timestamp": stale_timestamp,
        }
        self.cache_path.write_text(json.dumps(cached_data))

        # Mock the dependencies for the new analysis
        self.agent.rag_store.query.return_value = [{"text": "doc1"}]
        self.agent.llm_agent.analyze_news.return_value = {
            "score": -0.7,
            "reason": "New Hawkish reason",
            "model": "test-model",
        }

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "HAWKISH")
        self.assertEqual(context["reason"], "New Hawkish reason")
        self.agent.rag_store.query.assert_called_once()
        self.agent.llm_agent.analyze_news.assert_called_once()

    def test_get_macro_context_dovish_scenario(self):
        """Test a positive LLM score results in a DOVISH state."""
        # Arrange
        self.agent.rag_store.query.return_value = [{"text": "good news"}]
        self.agent.llm_agent.analyze_news.return_value = {
            "score": 0.8,
            "reason": "Rate cuts expected.",
            "model": "test-model",
        }

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "DOVISH")
        self.assertEqual(context["reason"], "Rate cuts expected.")
        self.assertEqual(context["confidence"], 0.8)
        self.assertTrue(self.cache_path.exists())

    def test_get_macro_context_hawkish_scenario(self):
        """Test a negative LLM score results in a HAWKISH state."""
        # Arrange
        self.agent.rag_store.query.return_value = [{"text": "bad news"}]
        self.agent.llm_agent.analyze_news.return_value = {
            "score": -0.6,
            "reason": "Inflation rising.",
            "model": "test-model",
        }

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "HAWKISH")
        self.assertEqual(context["reason"], "Inflation rising.")
        self.assertEqual(context["confidence"], 0.6)

    def test_get_macro_context_neutral_scenario(self):
        """Test a neutral LLM score results in a NEUTRAL state."""
        # Arrange
        self.agent.rag_store.query.return_value = [{"text": "mixed news"}]
        self.agent.llm_agent.analyze_news.return_value = {
            "score": 0.1,
            "reason": "Mixed signals.",
            "model": "test-model",
        }

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "NEUTRAL")

    def test_rag_store_failure(self):
        """Test that a RAG store failure results in an UNKNOWN state."""
        # Arrange
        self.agent.rag_store.query.side_effect = Exception("RAG DB is down")

        # Act
        context = self.agent.get_macro_context()

        # Assert
        self.assertEqual(context["state"], "UNKNOWN")
        self.assertIn("RAG DB is down", context["reason"])


if __name__ == "__main__":
    unittest.main()
