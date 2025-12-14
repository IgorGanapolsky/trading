"""
Unit tests for Claude Opus 4.5 optimization features.

Tests verify:
- EffortLevel enum and EffortConfig dataclass
- Agent-specific effort configurations
- Model selection based on effort level
- Confidence-based model escalation
- Smart council routing

Reference: rag_knowledge/lessons_learned/ll_011_opus_45_optimization_dec11.md
"""


class TestEffortLevelConfig:
    """Tests for EffortLevel and EffortConfig."""

    def test_effort_levels_exist(self):
        """Verify all effort levels are defined."""
        from src.agent_framework.agent_sdk_config import EffortLevel

        assert EffortLevel.LOW.value == "low"
        assert EffortLevel.MEDIUM.value == "medium"
        assert EffortLevel.HIGH.value == "high"

    def test_effort_config_for_low(self):
        """Verify LOW effort config has correct settings."""
        from src.agent_framework.agent_sdk_config import EffortConfig, EffortLevel

        config = EffortConfig.for_level(EffortLevel.LOW)

        assert config.level == EffortLevel.LOW
        assert config.max_tokens == 500
        assert config.temperature == 0.3

    def test_effort_config_for_medium(self):
        """Verify MEDIUM effort config has correct settings."""
        from src.agent_framework.agent_sdk_config import EffortConfig, EffortLevel

        config = EffortConfig.for_level(EffortLevel.MEDIUM)

        assert config.level == EffortLevel.MEDIUM
        assert config.max_tokens == 2000
        assert config.temperature == 0.5

    def test_effort_config_for_high(self):
        """Verify HIGH effort config has correct settings."""
        from src.agent_framework.agent_sdk_config import EffortConfig, EffortLevel

        config = EffortConfig.for_level(EffortLevel.HIGH)

        assert config.level == EffortLevel.HIGH
        assert config.max_tokens == 4096
        assert config.temperature == 0.7


class TestAgentEffortConfiguration:
    """Tests for agent-specific effort configurations."""

    def test_execution_agent_uses_low_effort(self):
        """Execution agent should use LOW effort (simple tasks)."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("execution_agent")

        assert effort == EffortLevel.LOW

    def test_signal_agent_uses_medium_effort(self):
        """Signal agent should use MEDIUM effort (standard analysis)."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("signal_agent")

        assert effort == EffortLevel.MEDIUM

    def test_research_agent_uses_high_effort(self):
        """Research agent should use HIGH effort (deep analysis)."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("research_agent")

        assert effort == EffortLevel.HIGH

    def test_rl_agent_uses_high_effort(self):
        """RL agent should use HIGH effort (complex reasoning)."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("rl_agent")

        assert effort == EffortLevel.HIGH

    def test_unknown_agent_uses_default_medium(self):
        """Unknown agents should use default MEDIUM effort."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("unknown_agent_xyz")

        assert effort == EffortLevel.MEDIUM


class TestModelSelectionByEffort:
    """Tests for model selection based on effort level."""

    def test_low_effort_selects_haiku(self):
        """LOW effort should select Haiku model."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        model = config.get_model_for_effort(EffortLevel.LOW)

        assert "haiku" in model.lower()

    def test_medium_effort_selects_sonnet(self):
        """MEDIUM effort should select Sonnet model."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        model = config.get_model_for_effort(EffortLevel.MEDIUM)

        assert "sonnet" in model.lower()

    def test_high_effort_selects_opus(self):
        """HIGH effort should select Opus model."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        model = config.get_model_for_effort(EffortLevel.HIGH)

        assert "opus" in model.lower()

    def test_agent_model_selection_matches_effort(self):
        """Agent model selection should match effort level."""
        from src.agent_framework.agent_sdk_config import get_agent_sdk_config

        config = get_agent_sdk_config()

        # Execution agent (LOW) should get Haiku
        exec_model = config.get_model_for_agent("execution_agent")
        assert "haiku" in exec_model.lower()

        # Research agent (HIGH) should get Opus
        research_model = config.get_model_for_agent("research_agent")
        assert "opus" in research_model.lower()


class TestConfidenceEscalation:
    """Tests for confidence-based model escalation."""

    def test_low_confidence_triggers_escalation(self):
        """Confidence < 0.7 should trigger escalation."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        # Low confidence should escalate from LOW
        assert config.should_escalate_model(0.5, EffortLevel.LOW) is True

        # Low confidence should escalate from MEDIUM
        assert config.should_escalate_model(0.5, EffortLevel.MEDIUM) is True

    def test_high_confidence_prevents_escalation(self):
        """Confidence >= 0.7 should not trigger escalation."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        # High confidence should not escalate
        assert config.should_escalate_model(0.8, EffortLevel.LOW) is False
        assert config.should_escalate_model(0.9, EffortLevel.MEDIUM) is False

    def test_high_effort_never_escalates(self):
        """HIGH effort should never escalate (already at max)."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        # Even low confidence should not escalate from HIGH
        assert config.should_escalate_model(0.3, EffortLevel.HIGH) is False
        assert config.should_escalate_model(0.1, EffortLevel.HIGH) is False

    def test_escalation_returns_higher_model(self):
        """Escalation should return the next higher model."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        # LOW -> MEDIUM (Sonnet)
        model, new_effort = config.get_escalated_model(EffortLevel.LOW)
        assert new_effort == EffortLevel.MEDIUM
        assert "sonnet" in model.lower()

        # MEDIUM -> HIGH (Opus)
        model, new_effort = config.get_escalated_model(EffortLevel.MEDIUM)
        assert new_effort == EffortLevel.HIGH
        assert "opus" in model.lower()

    def test_escalation_disabled_config(self):
        """Escalation should be controllable via config."""
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        # Disable escalation
        config.enable_confidence_escalation = False

        # Now even low confidence should not escalate
        assert config.should_escalate_model(0.3, EffortLevel.LOW) is False

        # Re-enable for other tests
        config.enable_confidence_escalation = True


class TestEffortConfigIntegration:
    """Integration tests for effort-based optimization."""

    def test_full_effort_workflow(self):
        """Test complete effort configuration workflow."""
        from src.agent_framework.agent_sdk_config import (
            EffortLevel,
            get_agent_sdk_config,
        )

        config = get_agent_sdk_config()

        # 1. Get agent effort
        effort = config.get_agent_effort("signal_agent")
        assert effort == EffortLevel.MEDIUM

        # 2. Get effort config
        effort_config = config.get_agent_effort_config("signal_agent")
        assert effort_config.level == EffortLevel.MEDIUM
        assert effort_config.max_tokens == 2000

        # 3. Get model for agent
        model = config.get_model_for_agent("signal_agent")
        assert "sonnet" in model.lower()

        # 4. Check escalation with low confidence
        should_escalate = config.should_escalate_model(0.5, effort)
        assert should_escalate is True

        # 5. Get escalated model
        new_model, new_effort = config.get_escalated_model(effort)
        assert new_effort == EffortLevel.HIGH
        assert "opus" in new_model.lower()

    def test_effort_config_defaults(self):
        """Verify default effort config values are sensible."""
        from src.agent_framework.agent_sdk_config import EffortConfig

        # Default config should be MEDIUM
        default = EffortConfig()
        assert default.max_tokens == 2000
        assert default.temperature == 0.7
        assert default.use_model_escalation is True


class TestRegressionLL011:
    """Regression tests for ll_011 (Opus 4.5 optimization)."""

    def test_ll_011_effort_levels_defined(self):
        """
        Regression: ll_011 - All effort levels must be properly defined.

        If this test fails, effort-based optimization is broken.
        """
        from src.agent_framework.agent_sdk_config import EffortConfig, EffortLevel

        for level in EffortLevel:
            config = EffortConfig.for_level(level)
            assert config.max_tokens > 0
            assert 0 <= config.temperature <= 1

    def test_ll_011_critical_agents_use_high_effort(self):
        """
        Regression: ll_011 - Critical agents must use HIGH effort.

        Research and RL agents need deep reasoning capabilities.
        """
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()

        critical_agents = ["research_agent", "rl_agent", "meta_agent", "debate_agents"]

        for agent_id in critical_agents:
            effort = config.get_agent_effort(agent_id)
            assert effort == EffortLevel.HIGH, f"{agent_id} should use HIGH effort"

    def test_ll_011_execution_agent_uses_low_effort(self):
        """
        Regression: ll_011 - Execution agent must use LOW effort.

        Simple order execution doesn't need expensive models.
        """
        from src.agent_framework.agent_sdk_config import EffortLevel, get_agent_sdk_config

        config = get_agent_sdk_config()
        effort = config.get_agent_effort("execution_agent")

        assert effort == EffortLevel.LOW
