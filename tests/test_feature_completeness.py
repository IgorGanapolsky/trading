"""
Feature Completeness Verification Tests

Ensures that features declared in configuration are actually implemented
and that the system doesn't accumulate phantom features.

These tests prevent the LL-034 antipattern (placeholder code).
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestFeatureCompleteness:
    """Verify declared features have implementations."""

    def test_sentiment_sources_match_weights(self):
        """
        Verify all sentiment sources in SOURCE_WEIGHTS have getter methods.
        Prevents: Declaring sources that don't exist (LL-034).
        """
        from src.utils.unified_sentiment import UnifiedSentiment

        analyzer = UnifiedSentiment()

        for source_name in analyzer.SOURCE_WEIGHTS:
            method_name = f"_get_{source_name}_sentiment"
            assert hasattr(analyzer, method_name), (
                f"SOURCE_WEIGHTS declares '{source_name}' but "
                f"'{method_name}' method doesn't exist"
            )

    def test_enabled_sources_flag_consistency(self):
        """
        Verify enabled_sources flags match SOURCE_WEIGHTS keys.
        """
        from src.utils.unified_sentiment import UnifiedSentiment

        analyzer = UnifiedSentiment()

        weights_keys = set(analyzer.SOURCE_WEIGHTS.keys())
        enabled_keys = set(analyzer.enabled_sources.keys())

        assert weights_keys == enabled_keys, (
            f"Mismatch between SOURCE_WEIGHTS and enabled_sources. "
            f"In weights but not enabled: {weights_keys - enabled_keys}. "
            f"In enabled but not weights: {enabled_keys - weights_keys}"
        )

    def test_collector_orchestrator_consistency(self):
        """
        Verify NewsOrchestrator only initializes collectors that exist.
        """
        from src.rag.collectors.orchestrator import NewsOrchestrator

        orchestrator = NewsOrchestrator()

        for name, collector in orchestrator.collectors.items():
            # Verify collector has required method
            assert hasattr(collector, "collect_ticker_news") or hasattr(
                collector, "collect_market_news"
            ), f"Collector '{name}' missing collect methods"

    def test_strategy_registry_matches_implementations(self):
        """
        Verify strategies in registry have actual implementation files.
        """
        registry_file = PROJECT_ROOT / "config" / "strategy_registry.json"

        if not registry_file.exists():
            pytest.skip("strategy_registry.json not found")

        registry = json.loads(registry_file.read_text())
        strategies_dir = PROJECT_ROOT / "src" / "strategies"

        for strategy_name, config in registry.items():
            if config.get("enabled", False):
                # Check if strategy file exists
                expected_files = [
                    strategies_dir / f"{strategy_name}.py",
                    strategies_dir / f"{strategy_name}_strategy.py",
                ]
                exists = any(f.exists() for f in expected_files)

                assert exists, (
                    f"Strategy '{strategy_name}' is enabled in registry "
                    f"but no implementation file found"
                )

    def test_skills_have_implementations(self):
        """
        Verify skills in .claude/skills/ have actual scripts.
        """
        skills_dir = PROJECT_ROOT / ".claude" / "skills"

        if not skills_dir.exists():
            pytest.skip("Skills directory not found")

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            # Check for scripts directory
            scripts_dir = skill_dir / "scripts"
            has_scripts = scripts_dir.exists() and any(scripts_dir.glob("*.py"))

            # Skills without scripts are OK if they're documentation-only
            skill_content = skill_md.read_text()
            if "tools:" in skill_content and not has_scripts:
                # Skill declares tools but has no scripts - potential issue
                # Allow if it references external modules
                if "src/" not in skill_content:
                    pytest.fail(
                        f"Skill '{skill_dir.name}' declares tools but has no scripts"
                    )

    def test_env_example_matches_actual_usage(self):
        """
        Verify .env.example variables are actually used in code.
        """
        env_example = PROJECT_ROOT / ".env.example"

        if not env_example.exists():
            pytest.skip(".env.example not found")

        # Extract variable names
        env_vars = set()
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=")[0].strip()
                env_vars.add(var_name)

        # Search for usage in Python files
        used_vars = set()
        for py_file in (PROJECT_ROOT / "src").rglob("*.py"):
            try:
                content = py_file.read_text()
                for var in env_vars:
                    if f'"{var}"' in content or f"'{var}'" in content or f"os.getenv('{var}" in content:
                        used_vars.add(var)
            except Exception:
                pass

        # Check scripts too
        for py_file in (PROJECT_ROOT / "scripts").rglob("*.py"):
            try:
                content = py_file.read_text()
                for var in env_vars:
                    if f'"{var}"' in content or f"'{var}'" in content:
                        used_vars.add(var)
            except Exception:
                pass

        unused = env_vars - used_vars

        # Filter out common/expected unused vars
        expected_unused = {
            "PYTHONPATH",
            "PATH",
        }
        truly_unused = unused - expected_unused

        # Allow some unused (configs are sometimes for future features)
        # But warn if more than 30% are unused
        unused_ratio = len(truly_unused) / len(env_vars) if env_vars else 0

        if unused_ratio > 0.3:
            pytest.fail(
                f"Too many unused env vars ({len(truly_unused)}/{len(env_vars)}): "
                f"{list(truly_unused)[:10]}..."
            )


class TestNoPhantomConfigs:
    """Verify configs don't reference non-existent code."""

    def test_system_state_strategies_exist(self):
        """
        Verify strategies in system_state.json have implementations.
        """
        state_file = PROJECT_ROOT / "data" / "system_state.json"

        if not state_file.exists():
            pytest.skip("system_state.json not found")

        state = json.loads(state_file.read_text())
        active_strategies = state.get("active_strategies", [])

        strategies_dir = PROJECT_ROOT / "src" / "strategies"

        for strategy in active_strategies:
            strategy_name = strategy.get("name", strategy) if isinstance(strategy, dict) else strategy

            # Normalize name
            normalized = strategy_name.lower().replace(" ", "_").replace("-", "_")

            # Look for matching file
            possible_files = [
                strategies_dir / f"{normalized}.py",
                strategies_dir / f"{normalized}_strategy.py",
            ]

            exists = any(f.exists() for f in possible_files)

            if not exists:
                # Check if it's a class in another file
                found_class = False
                class_pattern = f"class.*{strategy_name}"

                for py_file in strategies_dir.glob("*.py"):
                    try:
                        import re
                        if re.search(class_pattern, py_file.read_text(), re.IGNORECASE):
                            found_class = True
                            break
                    except Exception:
                        pass

                assert found_class, (
                    f"Strategy '{strategy_name}' in system_state.json "
                    f"has no implementation"
                )
