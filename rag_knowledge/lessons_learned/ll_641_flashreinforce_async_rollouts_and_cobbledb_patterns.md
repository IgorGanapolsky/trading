# LL-641: FlashREINFORCE Asynchronous Rollouts and CobbleDB Decoupled Architecture

## Context & Origin

- **Date**: 2026-09-16
- **Reference**: FlashREINFORCE / NVIDIA Molt agentic RL principles and Perplexity CobbleDB hot store architecture.
- **Problem**:
  1. Synchronous group rollouts (e.g. standard GRPO) waste 20–40% accelerator compute waiting on straggler trajectories, and risk policy tool-call collapse.
  2. Monolithic managed cloud databases (e.g. DynamoDB) incur high latency tails (p99 > 120ms) and metered per-read/write billing.

## Core Lessons Learned

1. **Never Infer 50% Cheaper from 50% Fewer Rollouts**:
   - Measuring raw rollout count is a vanity metric.
   - The true north star is:
     $$\text{Cost per solved task} = \frac{\text{Total GPU, inference, tool, and engineering costs}}{\text{Verified successful tasks}}$$
   - Always benchmark on variable-length, tool-using tasks with deterministic verifiers.
2. **Treat Tool Retention as a Hard Gate**:
   - Synchronous RL algorithms can collapse tool usage to zero when reward shortcuts exist.
   - Any rollout engine candidate must maintain $\ge 90\%$ tool retention to avoid regression on real enterprise tasks.
3. **Decouple Storage into 3 Tiers (CobbleDB Pattern)**:
   - Tier 1: Durable append-only journal (Pillar).
   - Tier 2: Partition-aligned batch staging (Lorry).
   - Tier 3: Local-first embedded hot store with LRU cache (Cobble replica).
4. **Hedge Tail Latency to Kill Stragglers**:
   - When primary read exceeds p95 or threshold (e.g. 15ms), fire a concurrent hedged request to a secondary replica.
   - This single architectural pattern cuts p99 tail latency by up to 82%.

## Production Artifacts

- Evaluator: `src/ml/async_rollout_evaluator.py`
- Hot Store: `src/data/cobble_hot_store.py`
- Tests: `tests/ml/test_async_rollout_evaluator.py`, `tests/data/test_cobble_hot_store.py`
- Documentation: `docs/ASYNC_ROLLOUTS_AND_COBBLEDB_ARCHITECTURE.md`
