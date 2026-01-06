"""
Tests for .claude/hooks/surface_feedback_patterns.sh

This test file ensures the RLHF feedback patterns hook correctly:
1. Reads the Thompson Sampling model from models/ml/feedback_model.json
2. Reads feedback stats from data/feedback/stats.json
3. Displays positive and negative feature patterns
4. Runs without errors even when files are missing

Created: Jan 6, 2026 - Implementing test coverage for new hook
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestHookFileValidation:
    """Tests for hook file structure and validity."""

    @pytest.fixture
    def hook_path(self):
        """Get the path to the hook file."""
        return Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"

    def test_hook_file_exists(self, hook_path):
        """Verify the hook file exists."""
        assert hook_path.exists(), f"Hook file should exist at {hook_path}"

    def test_hook_file_is_executable(self, hook_path):
        """Verify the hook file is executable."""
        assert os.access(hook_path, os.X_OK), "Hook file should be executable"

    def test_hook_has_shebang(self, hook_path):
        """Verify the hook file starts with proper shebang."""
        with open(hook_path) as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash"), "Hook must start with #!/bin/bash"

    def test_hook_file_is_valid_bash(self, hook_path):
        """Verify the hook file has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(hook_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Hook has syntax errors: {result.stderr}"

    def test_hook_references_model_file(self, hook_path):
        """Verify hook reads the feedback model file."""
        content = hook_path.read_text()
        assert "feedback_model.json" in content, "Hook should reference feedback_model.json"

    def test_hook_references_stats_file(self, hook_path):
        """Verify hook reads the feedback stats file."""
        content = hook_path.read_text()
        assert "stats.json" in content, "Hook should reference stats.json"


class TestHookExecution:
    """Tests for hook execution behavior."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory with mock files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory structure
            models_dir = Path(tmpdir) / "models" / "ml"
            models_dir.mkdir(parents=True)
            data_dir = Path(tmpdir) / "data" / "feedback"
            data_dir.mkdir(parents=True)

            yield Path(tmpdir)

    def test_hook_runs_without_model_file(self, temp_project_dir):
        """Verify hook exits gracefully when model file doesn't exist."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        # Should exit cleanly (exit 0)
        assert result.returncode == 0, f"Hook should exit cleanly: {result.stderr}"

    def test_hook_displays_feedback_with_model(self, temp_project_dir):
        """Verify hook displays feedback when model file exists."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # Create mock model file
        model_data = {
            "alpha": 5.0,
            "beta": 2.0,
            "feature_weights": {
                "trade": 0.2,
                "ci": 0.15,
                "test": -0.1,
                "error": -0.3,
            },
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        # Create mock stats file
        stats_data = {
            "total": 10,
            "positive": 8,
            "negative": 2,
            "satisfaction_rate": 80.0,
        }
        stats_path = temp_project_dir / "data" / "feedback" / "stats.json"
        stats_path.write_text(json.dumps(stats_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        # Check output contains expected elements
        output = result.stdout
        assert "RLHF FEEDBACK MODEL" in output, "Should display RLHF header"
        assert "α=5.0" in output, "Should show alpha value"
        assert "β=2.0" in output, "Should show beta value"
        assert "Posterior" in output, "Should show posterior"
        assert "POSITIVE patterns" in output, "Should show positive patterns"
        assert "NEGATIVE patterns" in output, "Should show negative patterns"

    def test_hook_shows_negative_features(self, temp_project_dir):
        """Verify hook correctly identifies negative feature weights."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # Create model with negative features
        model_data = {
            "alpha": 3.0,
            "beta": 3.0,
            "feature_weights": {
                "hallucination": -0.5,
                "promise": -0.3,
                "incomplete": -0.2,
            },
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        output = result.stdout
        # Should list negative patterns
        assert "hallucination" in output or "promise" in output or "incomplete" in output, (
            "Should show negative feature names"
        )

    def test_hook_shows_positive_features(self, temp_project_dir):
        """Verify hook correctly identifies positive feature weights."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # Create model with positive features
        model_data = {
            "alpha": 4.0,
            "beta": 1.0,
            "feature_weights": {
                "verify": 0.4,
                "evidence": 0.3,
                "complete": 0.2,
            },
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        output = result.stdout
        # Should list positive patterns
        assert "verify" in output or "evidence" in output or "complete" in output, (
            "Should show positive feature names"
        )


class TestThompsonSamplingDisplay:
    """Tests for Thompson Sampling model display correctness."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models" / "ml"
            models_dir.mkdir(parents=True)
            data_dir = Path(tmpdir) / "data" / "feedback"
            data_dir.mkdir(parents=True)
            yield Path(tmpdir)

    def test_posterior_calculation_display(self, temp_project_dir):
        """Verify posterior is calculated correctly: α / (α + β)."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # α=8, β=2 → posterior = 8/10 = 0.8
        model_data = {
            "alpha": 8.0,
            "beta": 2.0,
            "feature_weights": {},
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        assert "0.8" in result.stdout, "Posterior should be 0.8 for α=8, β=2"

    def test_sample_count_display(self, temp_project_dir):
        """Verify sample count is calculated correctly: α + β - 2 (subtract priors)."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # α=10, β=5 → samples = 10 + 5 - 2 = 13
        model_data = {
            "alpha": 10.0,
            "beta": 5.0,
            "feature_weights": {"test": 0.1},
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        assert "Samples: 13" in result.stdout, "Sample count should be 13 for α=10, β=5"


class TestFeedbackStatsDisplay:
    """Tests for feedback stats display."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models" / "ml"
            models_dir.mkdir(parents=True)
            data_dir = Path(tmpdir) / "data" / "feedback"
            data_dir.mkdir(parents=True)
            yield Path(tmpdir)

    def test_stats_display(self, temp_project_dir):
        """Verify feedback stats are displayed correctly."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        model_data = {
            "alpha": 3.0,
            "beta": 1.0,
            "feature_weights": {"ci": 0.1},
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        stats_data = {
            "total": 15,
            "positive": 12,
            "negative": 3,
            "satisfaction_rate": 80.0,
        }
        stats_path = temp_project_dir / "data" / "feedback" / "stats.json"
        stats_path.write_text(json.dumps(stats_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        output = result.stdout
        assert "12 thumbs up" in output, "Should show positive count"
        assert "3 thumbs down" in output, "Should show negative count"
        assert "80" in output, "Should show satisfaction rate"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir) / "models" / "ml"
            models_dir.mkdir(parents=True)
            data_dir = Path(tmpdir) / "data" / "feedback"
            data_dir.mkdir(parents=True)
            yield Path(tmpdir)

    def test_handles_empty_feature_weights(self, temp_project_dir):
        """Verify hook handles empty feature weights gracefully."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        model_data = {
            "alpha": 3.0,
            "beta": 1.0,
            "feature_weights": {},
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        assert result.returncode == 0, "Should handle empty feature weights"
        assert "none detected yet" in result.stdout, "Should indicate no patterns detected"

    def test_handles_malformed_json(self, temp_project_dir):
        """Verify hook handles malformed JSON gracefully."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text("{ invalid json }")

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        # Should not crash
        assert result.returncode == 0, "Should handle malformed JSON without crashing"

    def test_handles_zero_samples(self, temp_project_dir):
        """Verify hook handles zero samples (only priors)."""
        hook_path = (
            Path(__file__).parent.parent / ".claude" / "hooks" / "surface_feedback_patterns.sh"
        )

        # α=1, β=1 (priors only) → samples = 0
        model_data = {
            "alpha": 1.0,
            "beta": 1.0,
            "feature_weights": {},
            "last_updated": "2026-01-06T12:00:00",
        }
        model_path = temp_project_dir / "models" / "ml" / "feedback_model.json"
        model_path.write_text(json.dumps(model_data))

        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(temp_project_dir)},
        )

        # With 0 samples, should not display (no meaningful data)
        assert result.returncode == 0, "Should handle zero samples"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
