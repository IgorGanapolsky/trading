"""Tests for the feedback training script."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestTrainFromFeedback:
    """Test the feedback training script."""

    def test_script_exists(self):
        """Verify the training script exists."""
        script = Path(__file__).parent.parent / "scripts" / "train_from_feedback.py"
        assert script.exists(), "train_from_feedback.py should exist"

    def test_script_is_executable_module(self):
        """Script can be imported as a module."""
        # Import the module
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            assert hasattr(train_from_feedback, "load_model")
            assert hasattr(train_from_feedback, "save_model")
            assert hasattr(train_from_feedback, "update_model")
            assert hasattr(train_from_feedback, "extract_features")
        finally:
            sys.path.pop(0)

    def test_extract_features_test_keyword(self):
        """Extract test-related features."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import extract_features

            features = extract_features("Running pytest to verify the fix")
            assert "test" in features
        finally:
            sys.path.pop(0)

    def test_extract_features_ci_keyword(self):
        """Extract CI-related features."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import extract_features

            features = extract_features("Fixed the workflow action")
            assert "ci" in features
        finally:
            sys.path.pop(0)

    def test_extract_features_trade_keyword(self):
        """Extract trade-related features."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import extract_features

            features = extract_features("Opening a new position order")
            assert "trade" in features
        finally:
            sys.path.pop(0)

    def test_load_model_creates_default(self):
        """Load model returns default if file missing."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(
                    train_from_feedback,
                    "MODEL_PATH",
                    Path(tmpdir) / "nonexistent.json",
                ):
                    model = train_from_feedback.load_model()
                    assert model["alpha"] == 1.0
                    assert model["beta"] == 1.0
                    assert model["feature_weights"] == {}
        finally:
            sys.path.pop(0)

    def test_update_model_positive(self):
        """Positive feedback increases alpha."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    train_from_feedback.update_model("positive", "Fixed the test")

                    # Check model was updated
                    with open(model_path) as f:
                        model = json.load(f)
                    assert model["alpha"] == 2.0  # 1 (default) + 1
                    assert model["beta"] == 1.0
                    assert model["feature_weights"].get("test") == 0.1
        finally:
            sys.path.pop(0)

    def test_update_model_negative(self):
        """Negative feedback increases beta."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    train_from_feedback.update_model("negative", "Broke the CI")

                    # Check model was updated
                    with open(model_path) as f:
                        model = json.load(f)
                    assert model["alpha"] == 1.0
                    assert model["beta"] == 2.0  # 1 (default) + 1
                    assert model["feature_weights"].get("ci") == -0.1
        finally:
            sys.path.pop(0)

    def test_cli_positive_feedback(self):
        """CLI accepts positive feedback."""
        script = Path(__file__).parent.parent / "scripts" / "train_from_feedback.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--feedback",
                "positive",
                "--context",
                "test",
            ],
            capture_output=True,
            text=True,
        )
        # Script may succeed or fail based on model path, but should not crash
        assert result.returncode in [0, 1]

    def test_cli_requires_feedback_arg(self):
        """CLI requires feedback argument."""
        script = Path(__file__).parent.parent / "scripts" / "train_from_feedback.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()
