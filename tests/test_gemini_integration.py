import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Try to import GeminiAgent, skip tests if google-generativeai is not available
try:
    from src.agents.gemini_agent import GeminiAgent

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GeminiAgent = None


class TestGeminiIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures. Skips if google-generativeai is not available."""
        if not GEMINI_AVAILABLE:
            self.skipTest(
                "google-generativeai package not available - install with: pip install google-generativeai"
            )
        self.agent = GeminiAgent(
            name="TestGemini",
            role="Tester",
            model="gemini-3-pro-preview",
            default_thinking_level="low",  # Low for faster tests
        )

    @unittest.skipUnless(GEMINI_AVAILABLE, "google-generativeai not installed")
    def test_initialization(self):
        """Test that the agent initializes correctly."""
        self.assertEqual(self.agent.name, "TestGemini")
        self.assertEqual(self.agent.role, "Tester")
        self.assertEqual(self.agent.model, "gemini-3-pro-preview")

    @unittest.skipUnless(GEMINI_AVAILABLE, "google-generativeai not installed")
    @patch("src.agents.gemini_agent.genai.GenerativeModel")
    def test_reason_mocked(self, mock_model_class):
        """Test the reason method with a mocked Gemini API."""
        # Setup mock
        mock_model_instance = mock_model_class.return_value
        mock_response = MagicMock()
        mock_response.text = "Decision: APPROVE\nReasoning: The trade looks good."
        mock_model_instance.generate_content.return_value = mock_response

        # Execute
        result = self.agent.reason("Should I buy AAPL?")

        # Verify
        self.assertIn("decision", result)
        self.assertIn("reasoning", result)
        # The mock response text parsing depends on the implementation of _parse_response
        # Assuming default parsing logic handles unstructured text or we need to mock structured output

    @unittest.skipUnless(GEMINI_AVAILABLE, "google-generativeai not installed")
    def test_health_check(self):
        """Test the health check mechanism."""
        # It should return True initially as there are no errors
        self.assertTrue(self.agent.health_check())


if __name__ == "__main__":
    unittest.main()
