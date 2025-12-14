"""Critical Import Verification Tests.

These tests ensure all inter-module imports resolve correctly.
If any of these fail, it means a PR has broken import dependencies
and should NOT be merged.

Created: Dec 11, 2025 after missing function imports blocked trading.
See: rag_knowledge/lessons_learned/ll_011_missing_function_imports_dec11.md
"""

import sys
from pathlib import Path

import pytest

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCriticalImports:
    """Test that all critical imports resolve without errors."""

    def test_psychology_integration_imports(self):
        """Verify psychology module exports required functions.

        These functions are imported by debate_agents.py and other modules.
        If they don't exist, the entire trading system crashes at startup.
        """
        from src.coaching.mental_toughness_coach import (
            get_position_size_modifier,
            get_prompt_context,
        )

        # Verify functions are callable
        assert callable(get_prompt_context)
        assert callable(get_position_size_modifier)

        # Verify they return expected types
        ctx = get_prompt_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 0

        mod = get_position_size_modifier()
        assert isinstance(mod, float)
        assert 0.0 <= mod <= 1.0

    def test_debate_agents_imports(self):
        """Verify debate agents module can be imported.

        This module imports from mental_toughness_coach, so if those
        imports fail, this test catches it.
        """
        from src.agents.debate_agents import (
            BearAgent,
            BullAgent,
            DebateModerator,
            DebateOutcome,
        )

        assert BullAgent is not None
        assert BearAgent is not None
        assert DebateModerator is not None
        assert DebateOutcome is not None

    def test_reflexion_loop_imports(self):
        """Verify reflexion loop module can be imported."""
        from src.coaching.reflexion_loop import (
            ReflectionMemory,
            ReflexionLoop,
            TradeReflection,
            reflect_and_store,
        )

        assert ReflexionLoop is not None
        assert TradeReflection is not None
        assert ReflectionMemory is not None
        assert callable(reflect_and_store)

    def test_orchestrator_import(self):
        """Verify TradingOrchestrator can be imported.

        This is the ultimate test - if TradingOrchestrator imports,
        then all its dependencies also import correctly.
        """
        from src.orchestrator.main import TradingOrchestrator

        assert TradingOrchestrator is not None

    def test_multi_llm_analysis_imports(self):
        """Verify multi-LLM analysis module imports."""
        from src.core.multi_llm_analysis import MultiLLMAnalyzer

        assert MultiLLMAnalyzer is not None

    def test_signal_agent_imports(self):
        """Verify signal agent module imports."""
        from src.agents.signal_agent import SignalAgent

        assert SignalAgent is not None


class TestPsychologyIntegration:
    """Test that psychology integration actually works end-to-end."""

    def test_get_prompt_context_contains_required_sections(self):
        """Verify prompt context has all required sections."""
        from src.coaching.mental_toughness_coach import get_prompt_context

        ctx = get_prompt_context()

        # Required sections based on implementation
        assert "Cognitive Bias Awareness" in ctx
        assert "Current Psychology State" in ctx
        assert "Decision Framework" in ctx

    def test_position_modifier_respects_zones(self):
        """Verify position modifier returns appropriate values."""
        from src.coaching.mental_toughness_coach import get_position_size_modifier

        # Default state should return >= 0.5 (not in TILT)
        mod = get_position_size_modifier()
        assert mod >= 0.5, f"Default state returned {mod}, expected >= 0.5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
