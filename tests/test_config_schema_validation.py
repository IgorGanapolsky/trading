"""
Config Schema Validation Tests

Validates that all config files use valid enum values defined in code.
This prevents bugs like LL_033 (invalid AssetClass "commodity").

Author: Claude (AI CTO)
Date: 2025-12-14
"""

import json
from pathlib import Path

import pytest


class TestConfigEnumValidation:
    """Validate config files against Python enum definitions."""

    def test_strategy_registry_asset_classes(self):
        """Ensure all asset_class values are valid AssetClass enum values."""
        from src.strategies.registry import AssetClass

        valid_values = {e.value for e in AssetClass}
        config_path = Path("config/strategy_registry.json")

        if not config_path.exists():
            pytest.skip("strategy_registry.json not found")

        with open(config_path) as f:
            data = json.load(f)

        errors = []
        for name, strategy in data.get("strategies", {}).items():
            asset_class = strategy.get("asset_class")
            if asset_class not in valid_values:
                errors.append(
                    f"Strategy '{name}' has invalid asset_class: '{asset_class}'. "
                    f"Valid values: {valid_values}"
                )

        assert not errors, "\n".join(errors)

    def test_strategy_registry_status_values(self):
        """Ensure all status values are valid StrategyStatus enum values."""
        from src.strategies.registry import StrategyStatus

        valid_values = {e.value for e in StrategyStatus}
        config_path = Path("config/strategy_registry.json")

        if not config_path.exists():
            pytest.skip("strategy_registry.json not found")

        with open(config_path) as f:
            data = json.load(f)

        errors = []
        for name, strategy in data.get("strategies", {}).items():
            status = strategy.get("status")
            if status not in valid_values:
                errors.append(
                    f"Strategy '{name}' has invalid status: '{status}'. "
                    f"Valid values: {valid_values}"
                )

        assert not errors, "\n".join(errors)

    def test_all_json_configs_parseable(self):
        """Ensure all JSON config files are valid JSON."""
        config_dir = Path("config")
        if not config_dir.exists():
            pytest.skip("config/ directory not found")

        errors = []
        for json_file in config_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{json_file}: {e}")

        assert not errors, "\n".join(errors)


class TestRagLessonsIntegration:
    """Test that lessons learned are properly indexed and queryable."""

    def test_lesson_ll_033_exists(self):
        """Verify LL_033 (config enum validation) lesson exists."""
        lesson_path = Path("rag_knowledge/lessons_learned/ll_033_config_enum_validation.md")
        assert lesson_path.exists(), "LL_033 lesson file missing"

        content = lesson_path.read_text()
        assert "AssetClass" in content, "Lesson should reference AssetClass"
        assert "commodity" in content, "Lesson should mention the invalid value"
        assert "Prevention" in content, "Lesson should have prevention measures"

    def test_lessons_have_required_fields(self):
        """Ensure new lessons (2025-12-14+) have required metadata fields."""
        lessons_dir = Path("rag_knowledge/lessons_learned")
        if not lessons_dir.exists():
            pytest.skip("lessons_learned directory not found")

        required_fields = ["ID", "Severity", "Category"]
        errors = []
        warnings = []

        # Only strictly check lessons from ll_033 onwards (new standard)
        for lesson_file in lessons_dir.glob("ll_*.md"):
            # Extract lesson number
            name = lesson_file.name
            try:
                num = int(name.split("_")[1])
                is_new_standard = num >= 33
            except (IndexError, ValueError):
                is_new_standard = False

            content = lesson_file.read_text()
            for field in required_fields:
                if f"**{field}**:" not in content:
                    if is_new_standard:
                        errors.append(f"{name}: Missing {field}")
                    else:
                        warnings.append(f"{name}: Missing {field}")

        # Only fail on new lessons missing fields
        if warnings:
            print(f"\nWARNING: {len(warnings)} older lessons missing metadata (non-blocking)")

        assert not errors, "\n".join(errors)


class TestPrecommitValidation:
    """Test that pre-commit hooks are properly configured."""

    def test_precommit_config_exists(self):
        """Verify .pre-commit-config.yaml exists."""
        config_path = Path(".pre-commit-config.yaml")
        assert config_path.exists(), "Pre-commit config missing"

    def test_precommit_has_ruff(self):
        """Ensure ruff linter is configured."""
        config_path = Path(".pre-commit-config.yaml")
        if not config_path.exists():
            pytest.skip("Pre-commit config not found")

        content = config_path.read_text()
        assert "ruff" in content, "Ruff linter not configured in pre-commit"

    def test_precommit_has_json_check(self):
        """Ensure JSON validation is configured."""
        config_path = Path(".pre-commit-config.yaml")
        if not config_path.exists():
            pytest.skip("Pre-commit config not found")

        content = config_path.read_text()
        assert "check-json" in content, "JSON check not configured in pre-commit"
