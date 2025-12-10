"""
Tests for Multi-Timescale Memory System (Nested Learning)

Tests the hierarchical memory structure and multi-timescale retrieval.
"""

import pytest
from src.agent_framework.context_engine import (
    ContextEngine,
    ContextMemory,
    MemoryTimescale,
    MultiTimescaleMemory,
)


class TestMultiTimescaleMemory:
    """Test MultiTimescaleMemory class"""

    def test_init(self):
        """Test initialization"""
        mts = MultiTimescaleMemory("test_agent")
        assert mts.agent_id == "test_agent"
        assert len(mts.intraday_memory) == 0
        assert len(mts.daily_memory) == 0
        assert len(mts.weekly_memory) == 0
        assert len(mts.monthly_memory) == 0
        assert len(mts.episodic_memory) == 0

    def test_store_intraday(self):
        """Test storing intraday memory"""
        mts = MultiTimescaleMemory("test_agent")
        memory = ContextMemory(
            agent_id="test_agent",
            content={"action": "BUY", "symbol": "NVDA"},
            timescale=MemoryTimescale.INTRADAY,
        )

        mts.store(memory, auto_timescale=False)
        assert len(mts.intraday_memory) == 1
        assert len(mts.daily_memory) == 0

    def test_store_episodic(self):
        """Test storing episodic memory"""
        mts = MultiTimescaleMemory("test_agent")
        memory = ContextMemory(
            agent_id="test_agent",
            content={"action": "BUY", "pl": 100.0},
            timescale=MemoryTimescale.EPISODIC,
            importance_score=0.9,
        )

        mts.store(memory, auto_timescale=False)
        assert len(mts.episodic_memory) == 1
        assert not memory.is_expired()  # Episodic never expires

    def test_retrieve_by_timescale(self):
        """Test retrieving memories by timescale"""
        mts = MultiTimescaleMemory("test_agent")

        # Add memories to different timescales
        for i in range(3):
            memory = ContextMemory(
                agent_id="test_agent",
                content={"index": i},
                timescale=MemoryTimescale.DAILY,
            )
            mts.daily_memory.append(memory)

        memories = mts.retrieve(timescales=[MemoryTimescale.DAILY])
        assert len(memories) == 3

    def test_importance_scoring(self):
        """Test importance score filtering"""
        mts = MultiTimescaleMemory("test_agent")

        # Add memories with different importance
        low_importance = ContextMemory(
            agent_id="test_agent", content={"test": "low"}, importance_score=0.2
        )
        high_importance = ContextMemory(
            agent_id="test_agent", content={"test": "high"}, importance_score=0.8
        )

        mts.daily_memory.append(low_importance)
        mts.daily_memory.append(high_importance)

        # Retrieve with min_importance filter
        memories = mts.retrieve(min_importance=0.5)
        assert len(memories) == 1
        assert memories[0].importance_score == 0.8

    def test_consolidate_patterns(self):
        """Test pattern consolidation"""
        mts = MultiTimescaleMemory("test_agent")

        # Add multiple daily memories with same pattern
        for _i in range(5):
            memory = ContextMemory(
                agent_id="test_agent",
                content={"pattern": "momentum", "pl": 10.0},
                tags={"momentum", "NVDA"},
                timescale=MemoryTimescale.DAILY,
                importance_score=0.6,
            )
            mts.daily_memory.append(memory)

        consolidated = mts.consolidate_patterns()
        assert len(consolidated) > 0
        assert len(mts.weekly_memory) > 0  # Pattern promoted to weekly


class TestContextEngineMultiTimescale:
    """Test ContextEngine with multi-timescale support"""

    def test_store_with_timescale(self):
        """Test storing memory with timescale"""
        engine = ContextEngine(enable_multi_timescale=True)

        memory = engine.store_memory(
            agent_id="test_agent",
            content={"action": "BUY"},
            timescale=MemoryTimescale.EPISODIC,
            importance_score=0.9,
        )

        assert memory.timescale == MemoryTimescale.EPISODIC
        assert "test_agent" in engine.multi_timescale_memory

    def test_retrieve_multi_timescale(self):
        """Test retrieving memories with multi-timescale"""
        engine = ContextEngine(enable_multi_timescale=True)

        # Store memories in different timescales
        engine.store_memory(
            agent_id="test_agent",
            content={"test": "daily"},
            timescale=MemoryTimescale.DAILY,
        )
        engine.store_memory(
            agent_id="test_agent",
            content={"test": "episodic"},
            timescale=MemoryTimescale.EPISODIC,
            importance_score=0.9,
        )

        memories = engine.retrieve_memories(agent_id="test_agent", use_multi_timescale=True)

        assert len(memories) >= 2

    def test_get_agent_context_multi_timescale(self):
        """Test getting agent context with multi-timescale"""
        engine = ContextEngine(enable_multi_timescale=True)

        # Store some memories
        engine.store_memory(
            agent_id="test_agent",
            content={"test": "memory"},
            timescale=MemoryTimescale.DAILY,
        )

        # Register a blueprint first
        from src.agent_framework.context_engine import SemanticBlueprint

        blueprint = SemanticBlueprint(
            agent_id="test_agent",
            agent_name="Test Agent",
            role="Tester",
            description="Testing agent",
        )
        engine.register_blueprint(blueprint)

        context = engine.get_agent_context(agent_id="test_agent", use_multi_timescale=True)

        assert "memories" in context
        assert "timescale_breakdown" in context

    def test_importance_update(self):
        """Test importance score update from P/L"""
        memory = ContextMemory(
            agent_id="test_agent", content={"test": "memory"}, importance_score=0.5
        )

        memory.update_importance(pl=800.0, max_pl=1000.0)
        assert memory.importance_score > 0.5
        assert memory.outcome_pl == 800.0

    def test_memory_statistics(self):
        """Test memory statistics"""
        engine = ContextEngine(enable_multi_timescale=True)

        engine.store_memory(agent_id="test_agent", content={"test": "memory"})

        stats = engine.get_memory_statistics(agent_id="test_agent")
        assert "agent_memory" in stats
        assert "test_agent" in stats["agent_memory"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
