from __future__ import annotations

from src.orchestration.context_engine import ContextMemory, ContextEngine, MemoryTimescale


def test_context_memory_uses_dict_value_as_content():
    memory = ContextMemory(
        key="m1",
        value={"result": "WIN"},
        timescale=MemoryTimescale.DAILY,
    )

    assert memory.content == {"result": "WIN"}


def test_context_engine_stores_and_retrieves_agent_memories(tmp_path):
    engine = ContextEngine(base_dir=tmp_path / "agent_context")

    stored = engine.store_memory(
        agent_id="ExecutionAgent",
        content={
            "timestamp": "2026-07-02T13:00:00",
            "outcome": {"result": "WIN", "pl": 42.0},
        },
        tags={"ExecutionAgent", "outcome", "WIN"},
        timescale=MemoryTimescale.DAILY,
        outcome_pl=42.0,
    )
    memories = engine.retrieve_memories(
        agent_id="ExecutionAgent",
        limit=5,
        timescales=[MemoryTimescale.DAILY],
    )

    assert len(memories) == 1
    assert memories[0].key == stored.key
    assert memories[0].content["outcome"]["result"] == "WIN"
    assert memories[0].outcome_pl == 42.0
    assert memories[0].timescale == MemoryTimescale.DAILY


def test_context_engine_filters_timescales_and_skips_corrupt_memories(tmp_path):
    engine = ContextEngine(base_dir=tmp_path / "agent_context")
    engine.store_memory(
        agent_id="ExecutionAgent",
        content={"result": "daily"},
        timescale=MemoryTimescale.DAILY,
    )
    engine.store_memory(
        agent_id="ExecutionAgent",
        content={"result": "semantic"},
        timescale=MemoryTimescale.SEMANTIC,
    )
    (engine.memory_dir / "ExecutionAgent_bad.json").write_text(
        "{not-valid-json",
        encoding="utf-8",
    )

    memories = engine.retrieve_memories(
        agent_id="ExecutionAgent",
        timescales=[MemoryTimescale.SEMANTIC],
    )

    assert [memory.content["result"] for memory in memories] == ["semantic"]
