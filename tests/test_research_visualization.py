"""
Tests for Gemini Deep Research visualization components.

Tests both:
1. GeminiDeepResearch visual output handling (gemini_deep_research.py)
2. ResearchVisualizer chart generation (research_visualizer.py)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestResearchOutput:
    """Test the ResearchOutput dataclass."""

    def test_research_output_creation(self):
        """Test creating a ResearchOutput instance."""
        from src.ml.gemini_deep_research import ResearchOutput

        output = ResearchOutput(
            research_name="BTC_test",
            timestamp="20251216_120000",
            text_content={"recommendation": "BUY", "confidence": 0.8},
            visual_outputs=[
                {"type": "image", "path": "chart.png", "mime_type": "image/png"}  # noqa: S108
            ],
            sources=["https://example.com"],
        )

        assert output.research_name == "BTC_test"
        assert output.has_visuals is True
        assert output.text_content["recommendation"] == "BUY"

    def test_research_output_to_dict(self):
        """Test serialization to dictionary."""
        from src.ml.gemini_deep_research import ResearchOutput

        output = ResearchOutput(
            research_name="test",
            timestamp="20251216_120000",
            text_content={"data": "value"},
        )

        result = output.to_dict()

        assert isinstance(result, dict)
        assert result["research_name"] == "test"
        assert result["visual_outputs"] == []
        assert result["status"] == "completed"

    def test_research_output_no_visuals(self):
        """Test has_visuals property when empty."""
        from src.ml.gemini_deep_research import ResearchOutput

        output = ResearchOutput(
            research_name="test",
            timestamp="20251216_120000",
            text_content={},
        )

        assert output.has_visuals is False


class TestGeminiDeepResearchVisuals:
    """Test visual output handling in GeminiDeepResearch."""

    @patch("src.ml.gemini_deep_research.GEMINI_AVAILABLE", True)
    def test_init_creates_directories(self):
        """Test that initialization creates output directories."""
        from src.ml.gemini_deep_research import GeminiDeepResearch

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "research_outputs"

            # Patch environment to avoid real API init
            with patch.dict("os.environ", {}, clear=True):
                _researcher = GeminiDeepResearch(output_dir=output_dir)

            assert output_dir.exists()
            assert (output_dir / "visuals").exists()
            assert (output_dir / "json").exists()

    def test_parse_text_output_json(self):
        """Test JSON extraction from text output."""
        from src.ml.gemini_deep_research import GeminiDeepResearch

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True):
                researcher = GeminiDeepResearch(output_dir=Path(tmpdir))

            text = 'Here is the analysis: {"recommendation": "BUY", "confidence": 0.8}'
            result = researcher._parse_text_output(text, "test")

            assert result["recommendation"] == "BUY"
            assert result["confidence"] == 0.8

    def test_parse_text_output_no_json(self):
        """Test fallback when no JSON in text."""
        from src.ml.gemini_deep_research import GeminiDeepResearch

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True):
                researcher = GeminiDeepResearch(output_dir=Path(tmpdir))

            text = "This is plain text analysis without JSON."
            result = researcher._parse_text_output(text, "test")

            assert "raw_research" in result
            assert result["research_name"] == "test"

    @patch("src.ml.gemini_deep_research.GEMINI_AVAILABLE", True)
    def test_save_research_output(self):
        """Test saving research output to JSON file."""
        from src.ml.gemini_deep_research import GeminiDeepResearch, ResearchOutput

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with patch.dict("os.environ", {}, clear=True):
                researcher = GeminiDeepResearch(output_dir=output_dir)

            research_output = ResearchOutput(
                research_name="BTC_test",
                timestamp="20251216_120000",
                text_content={"recommendation": "HOLD"},
            )

            filepath = researcher._save_research(research_output)

            assert filepath.exists()
            with open(filepath) as f:
                saved_data = json.load(f)
            assert saved_data["research_name"] == "BTC_test"

    @patch("src.ml.gemini_deep_research.GEMINI_AVAILABLE", True)
    def test_get_latest_research_none(self):
        """Test getting latest research when none exists."""
        from src.ml.gemini_deep_research import GeminiDeepResearch

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {}, clear=True):
                researcher = GeminiDeepResearch(output_dir=Path(tmpdir))

            result = researcher.get_latest_research("nonexistent")
            assert result is None


class TestResearchVisualizer:
    """Test the ResearchVisualizer chart generation."""

    @pytest.fixture
    def sample_research_data(self):
        """Sample research data for testing."""
        return {
            "research_name": "BTC_market_research",
            "recommendation": "BUY",
            "confidence": 0.75,
            "sentiment": "bullish",
            "key_levels": {"support": [95000, 92000], "resistance": [100000, 105000]},
            "allocation": {"crypto": 30, "stocks": 50, "cash": 20},
            "risk_level": "medium",
            "key_risks": ["Fed policy", "Geopolitical tensions"],
        }

    def test_visualizer_init_creates_directory(self):
        """Test that visualizer creates output directory."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "charts"
            visualizer = ResearchVisualizer(output_dir=output_dir)

            assert output_dir.exists()
            assert visualizer.output_dir == output_dir

    def test_has_recommendation_data(self, sample_research_data):
        """Test detection of recommendation data."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))

            assert visualizer._has_recommendation_data(sample_research_data) is True
            assert visualizer._has_recommendation_data({}) is False

    def test_has_sentiment_data(self, sample_research_data):
        """Test detection of sentiment data."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))

            assert visualizer._has_sentiment_data(sample_research_data) is True
            assert visualizer._has_sentiment_data({"fear_greed_index": 50}) is True
            assert visualizer._has_sentiment_data({}) is False

    def test_has_allocation_data(self, sample_research_data):
        """Test detection of allocation data."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))

            assert visualizer._has_allocation_data(sample_research_data) is True
            assert visualizer._has_allocation_data({}) is False

    @pytest.mark.skipif(
        not pytest.importorskip("matplotlib", reason="matplotlib not installed"),
        reason="matplotlib required",
    )
    def test_visualize_research_generates_charts(self, sample_research_data):
        """Test that visualize_research generates expected charts."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))
            result = visualizer.visualize_research(sample_research_data)

            assert "charts" in result
            assert "generated_at" in result

            # Check that charts were created
            charts = result["charts"]
            assert len(charts) > 0

            # Verify recommendation chart
            if "recommendation" in charts:
                assert Path(charts["recommendation"]["path"]).exists()

    @pytest.mark.skipif(
        not pytest.importorskip("matplotlib", reason="matplotlib not installed"),
        reason="matplotlib required",
    )
    def test_create_recommendation_chart(self, sample_research_data):
        """Test recommendation chart generation."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))
            result = visualizer._create_recommendation_chart(
                sample_research_data, "test", save=True
            )

            assert result is not None
            assert result["type"] == "recommendation"
            assert Path(result["path"]).exists()

    @pytest.mark.skipif(
        not pytest.importorskip("matplotlib", reason="matplotlib not installed"),
        reason="matplotlib required",
    )
    def test_create_sentiment_gauge_chart(self, sample_research_data):
        """Test sentiment gauge chart generation."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))
            result = visualizer._create_sentiment_gauge_chart(
                sample_research_data, "test", save=True
            )

            assert result is not None
            assert result["type"] == "sentiment"

    @pytest.mark.skipif(
        not pytest.importorskip("matplotlib", reason="matplotlib not installed"),
        reason="matplotlib required",
    )
    def test_create_allocation_pie_chart(self, sample_research_data):
        """Test allocation pie chart generation."""
        from src.ml.research_visualizer import ResearchVisualizer

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))
            result = visualizer._create_allocation_pie_chart(
                sample_research_data, "test", save=True
            )

            assert result is not None
            assert result["type"] == "allocation"

    def test_visualize_with_minimal_data(self):
        """Test visualization with minimal data (graceful handling)."""
        from src.ml.research_visualizer import ResearchVisualizer

        minimal_data = {"research_name": "minimal"}

        with tempfile.TemporaryDirectory() as tmpdir:
            visualizer = ResearchVisualizer(output_dir=Path(tmpdir))
            result = visualizer.visualize_research(minimal_data)

            # Should complete without error, may have no charts
            assert "charts" in result
            assert "generated_at" in result


class TestConvenienceFunction:
    """Test the convenience function."""

    def test_visualize_research_output_function(self):
        """Test the module-level convenience function."""
        from src.ml.research_visualizer import visualize_research_output

        sample_data = {
            "research_name": "test",
            "recommendation": "HOLD",
            "confidence": 0.5,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = visualize_research_output(sample_data, output_dir=Path(tmpdir))

            assert "charts" in result
            assert "generated_at" in result


class TestMockedGeminiInteraction:
    """Test Gemini API interaction with mocking."""

    @patch("src.ml.gemini_deep_research.GEMINI_AVAILABLE", True)
    @patch("src.ml.gemini_deep_research.genai")
    def test_run_research_with_visual_outputs(self, mock_genai):
        """Test that visual outputs are captured from API response."""
        from src.ml.gemini_deep_research import GeminiDeepResearch

        # Setup mock
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        # Create mock interaction with text and image outputs
        mock_text_output = MagicMock()
        mock_text_output.type = "text"
        mock_text_output.text = '{"recommendation": "BUY", "confidence": 0.8}'

        mock_image_output = MagicMock()
        mock_image_output.type = "image"
        mock_image_output.mime_type = "image/png"
        # Base64 encoded 1x1 PNG
        mock_image_output.data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        mock_interaction = MagicMock()
        mock_interaction.id = "test-123"
        mock_interaction.status = "completed"
        mock_interaction.outputs = [mock_text_output, mock_image_output]

        mock_client.interactions.create.return_value = mock_interaction
        mock_client.interactions.get.return_value = mock_interaction

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
                researcher = GeminiDeepResearch(output_dir=Path(tmpdir))

            result = researcher._run_research("test query", "test_research")

            assert result is not None
            assert result["recommendation"] == "BUY"
            assert "_research_output" in result

            # Check that visual was saved
            research_output = result["_research_output"]
            assert len(research_output["visual_outputs"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
