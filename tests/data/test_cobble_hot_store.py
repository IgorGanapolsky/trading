"""Unit tests for CobbleDB decoupled hot store and hedged request router."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.data.cobble_hot_store import (
    CobbleDBHotStoreSystem,
    CobbleRecord,
    CobbleReplica,
    DurablePillar,
    HedgedRequestRouter,
    LorryBatchAccumulator,
)


def test_cobble_record_checksum_generation():
    record1 = CobbleRecord(key="spy_tick_01", value={"vix": 18.5, "delta": 0.15}, partition_id=3, version=1)
    record2 = CobbleRecord(key="spy_tick_01", value={"vix": 18.5, "delta": 0.15}, partition_id=3, version=1)
    record3 = CobbleRecord(key="spy_tick_01", value={"vix": 20.0, "delta": 0.15}, partition_id=3, version=1)

    assert record1.checksum == record2.checksum
    assert record1.checksum != record3.checksum
    assert len(record1.checksum) == 64


def test_durable_pillar_append_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        journal = Path(tmpdir) / "journal.jsonl"
        pillar = DurablePillar(journal)

        r1 = CobbleRecord(key="k1", value={"price": 100}, partition_id=1, version=1)
        r2 = CobbleRecord(key="k2", value={"price": 200}, partition_id=2, version=1)

        pillar.append(r1)
        pillar.append(r2)

        read_back = pillar.read_all()
        assert len(read_back) == 2
        assert read_back[0].key == "k1"
        assert read_back[1].key == "k2"
        assert read_back[0].checksum == r1.checksum


def test_lorry_batch_accumulator_flushing():
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_dir = Path(tmpdir) / "batches"
        lorry = LorryBatchAccumulator(batch_dir, batch_size=2)

        r1 = CobbleRecord(key="k1", value={"a": 1}, partition_id=1, version=1)
        r2 = CobbleRecord(key="k2", value={"a": 2}, partition_id=1, version=1)

        p1 = lorry.add(r1)
        assert p1 is None  # Buffer count 1 < 2

        p2 = lorry.add(r2)
        assert p2 is not None  # Flushed batch
        assert p2.exists()


def test_cobble_replica_lru_and_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_replica.db"
        replica = CobbleReplica(replica_id="rep_test", db_path=db_path, cache_capacity=2)

        r1 = CobbleRecord(key="k1", value={"val": 1}, partition_id=0, version=1)
        r2 = CobbleRecord(key="k2", value={"val": 2}, partition_id=0, version=1)
        r3 = CobbleRecord(key="k3", value={"val": 3}, partition_id=0, version=1)

        replica.put(r1)
        replica.put(r2)
        assert "k1" in replica.lru_cache
        assert "k2" in replica.lru_cache

        # Adding 3rd record evicts oldest (k1) from LRU memory, but keeps in DB
        replica.put(r3)
        assert "k1" not in replica.lru_cache
        assert "k3" in replica.lru_cache

        # Fetching k1 falls back to local SQLite and re-populates LRU
        fetched_k1 = replica.get("k1")
        assert fetched_k1 is not None
        assert fetched_k1.value == {"val": 1}
        assert "k1" in replica.lru_cache


def test_hedged_request_router():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        rep1 = CobbleReplica("r1", base / "r1.db")
        rep2 = CobbleReplica("r2", base / "r2.db")

        record = CobbleRecord(key="hedged_key", value={"fast": True}, partition_id=2, version=1)
        rep1.put(record)
        rep2.put(record)

        router = HedgedRequestRouter(
            replicas=[rep1, rep2],
            hedged_delay_ms=10.0,
        )

        # 1. Normal fast primary read (no hedging triggered)
        rec, receipt = router.read_with_hedging("hedged_key", simulated_primary_delay_ms=0.0)
        assert rec is not None
        assert receipt.hedged_request_fired is False

        # 2. Slow primary triggering hedged request (secondary completes faster)
        rec_hedged, receipt_hedged = router.read_with_hedging(
            "hedged_key",
            simulated_primary_delay_ms=25.0,  # Exceeds 10ms threshold
            simulated_secondary_delay_ms=2.0,  # Secondary wins
        )
        assert rec_hedged is not None
        assert receipt_hedged.hedged_request_fired is True
        assert receipt_hedged.winner == "HEDGED"

        stats = router.latency_stats()
        assert stats["hedged_pct"] > 0.0


def test_cobble_db_system_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        system = CobbleDBHotStoreSystem(base_dir=Path(tmpdir) / "cobble_root", num_replicas=2)

        # Write
        rec = system.write("option_chain_spy", {"dte": 30, "put_strike": 725})
        assert rec.checksum != ""

        # Read
        retrieved, receipt = system.read("option_chain_spy")
        assert retrieved is not None
        assert retrieved.value["put_strike"] == 725
        assert receipt.found is True
