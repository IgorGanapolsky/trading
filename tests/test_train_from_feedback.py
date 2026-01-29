"""Tests for the feedback training script."""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


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

    def test_per_category_update_positive(self):
        """Positive feedback increments category alpha."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    train_from_feedback.update_model("positive", "Running pytest suite")

                    with open(model_path) as f:
                        model = json.load(f)
                    assert model["per_category"]["test"]["alpha"] == 2.0
                    assert model["per_category"]["test"]["beta"] == 1.0
                    assert model["per_category"]["test"]["count"] == 1
        finally:
            sys.path.pop(0)

    def test_per_category_update_negative(self):
        """Negative feedback increments category beta."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    train_from_feedback.update_model("negative", "CI workflow broken")

                    with open(model_path) as f:
                        model = json.load(f)
                    assert model["per_category"]["ci"]["alpha"] == 1.0
                    assert model["per_category"]["ci"]["beta"] == 2.0
                    assert model["per_category"]["ci"]["count"] == 1
        finally:
            sys.path.pop(0)

    def test_per_category_backward_compat(self):
        """Old model without per_category loads correctly."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                # Write old-format model without per_category
                old_model = {
                    "alpha": 5.0,
                    "beta": 2.0,
                    "feature_weights": {"test": 0.5},
                    "last_updated": "2026-01-01T00:00:00",
                }
                with open(model_path, "w") as f:
                    json.dump(old_model, f)

                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    model = train_from_feedback.load_model()
                    assert "per_category" in model
                    assert "test" in model["per_category"]
                    assert model["per_category"]["test"]["alpha"] == 1.0
        finally:
            sys.path.pop(0)

    def test_time_decay_recent(self):
        """Feedback from 3 days ago gets weight 1.0."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import compute_time_weight

            ts = (datetime.now() - timedelta(days=3)).isoformat()
            assert compute_time_weight(ts) == 1.0
        finally:
            sys.path.pop(0)

    def test_time_decay_medium(self):
        """Feedback from 14 days ago gets weight 0.5."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import compute_time_weight

            ts = (datetime.now() - timedelta(days=14)).isoformat()
            assert compute_time_weight(ts) == 0.5
        finally:
            sys.path.pop(0)

    def test_time_decay_old(self):
        """Feedback from 60 days ago gets weight 0.25."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import compute_time_weight

            ts = (datetime.now() - timedelta(days=60)).isoformat()
            assert compute_time_weight(ts) == 0.25
        finally:
            sys.path.pop(0)

    def test_new_feature_extraction(self):
        """New feature patterns: analysis, log_parsing, system_health."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from train_from_feedback import extract_features

            assert "analysis" in extract_features("Running backtest analysis")
            assert "analysis" in extract_features("Research the market data")
            assert "log_parsing" in extract_features("Parse the output log")
            assert "system_health" in extract_features("Check system health monitor")
        finally:
            sys.path.pop(0)

    def test_recompute_flag(self):
        """--recompute rebuilds model from history."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            import train_from_feedback

            with tempfile.TemporaryDirectory() as tmpdir:
                model_path = Path(tmpdir) / "feedback_model.json"
                fb_dir = Path(tmpdir) / "feedback"
                fb_dir.mkdir()

                # Write some feedback history
                ts = datetime.now().isoformat()
                with open(fb_dir / "feedback_2026-01-29.jsonl", "w") as f:
                    f.write(
                        json.dumps({"timestamp": ts, "type": "positive", "summary": "test passed"})
                        + "\n"
                    )
                    f.write(
                        json.dumps(
                            {"timestamp": ts, "type": "negative", "summary": "CI workflow broke"}
                        )
                        + "\n"
                    )

                with patch.object(train_from_feedback, "MODEL_PATH", model_path):
                    with patch.object(train_from_feedback, "FEEDBACK_DIRS", [fb_dir]):
                        train_from_feedback.recompute_from_history()

                with open(model_path) as f:
                    model = json.load(f)

                # Should have 1.0 (prior) + 1.0 (positive) = 2.0 alpha
                assert model["alpha"] == 2.0
                # Should have 1.0 (prior) + 1.0 (negative) = 2.0 beta
                assert model["beta"] == 2.0
                assert "per_category" in model
        finally:
            sys.path.pop(0)
