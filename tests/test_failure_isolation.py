from src.agent_framework.context_engine import ContextEngine
from src.orchestrator.failure_isolation import FailureIsolationManager


class DummyTelemetry:
    def __init__(self) -> None:
        self.events = []

    def record(self, event_type: str, ticker: str, status: str, payload):
        self.events.append(
            {
                "event_type": event_type,
                "ticker": ticker,
                "status": status,
                "payload": payload,
            }
        )


def test_prune_memories(tmp_path):
    engine = ContextEngine(storage_dir=tmp_path / "context")

    keep = engine.store_memory(
        agent_id="agent",
        content={"type": "keep"},
        tags={"info"},
    )
    remove = engine.store_memory(
        agent_id="agent",
        content={"type": "failure"},
        tags={"failure", "gate.momentum", "SPY"},
    )

    removed_ids = engine.prune_memories(agent_id="agent", tags={"failure"}, max_removed=3)

    assert remove.memory_id in removed_ids
    assert keep.memory_id in engine.memory
    assert remove.memory_id not in engine.memory
    assert not (tmp_path / "context" / "memories" / f"{remove.memory_id}.json").exists()


def test_failure_isolation_logs_and_prunes(tmp_path):
    engine = ContextEngine(storage_dir=tmp_path / "context")
    telemetry = DummyTelemetry()
    log_dir = tmp_path / "logs"
    manager = FailureIsolationManager(
        telemetry=telemetry,
        context_engine=engine,
        log_dir=log_dir,
        agent_id="agent",
    )

    # Seed a prior failure memory that should be pruned.
    stale = engine.store_memory(
        agent_id="agent",
        content={"type": "stale"},
        tags={"failure", "gate.momentum", "SPY"},
    )

    def boom():
        raise RuntimeError("boom")  # noqa: TRY301 - used for sandboxing

    outcome = manager.run("momentum", "SPY", boom)

    assert not outcome.ok
    assert telemetry.events
    assert telemetry.events[0]["status"] == "error"
    assert stale.memory_id not in engine.memory
    assert log_dir.exists()
    assert any(log_dir.glob("*.json"))
    assert "boom" in outcome.failure.error
    assert outcome.failure.metadata["attempts"]
