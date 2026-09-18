# Architectural Blueprint: FlashREINFORCE Asynchronous Agent Rollouts & CobbleDB Storage

## Executive Summary

To drive systematic improvements in execution speed, GPU/inference margin, and state-serving reliability, this architecture codifies two foundational engineering patterns:

1. **FlashREINFORCE & NVIDIA Molt Asynchronous Rollout Engine**: Replaces synchronous group rollouts (standard GRPO group barriers) with asynchronous single-rollout streams, eliminating accelerator idle time and protecting against tool-call collapse.
2. **CobbleDB-Inspired Decoupled Hot Store**: Adapts Perplexity's CobbleDB key-value architecture (decoupling durable records, batch delivery, and local-first hot query serving with hedged requests) to achieve 5x lower latency, 82% p99 tail-latency reduction, and >20% cost savings over managed cloud databases.

---

## 1. FlashREINFORCE & Asynchronous Agent Rollout A/B Engine

### 1.1 The Operational Bottleneck in Synchronous Group Rollouts (GRPO)

In traditional Group Relative Policy Optimization (GRPO), $K$ trajectories are sampled synchronously for each scenario to compute group-relative advantage:
$$A(s, a) = R(s, a) - \text{mean}(R_{1..K})$$
When trajectories involve variable-length reasoning or multi-step tool calls, fast trajectories (e.g. 100ms) sit idle waiting for the slowest trajectory (the straggler, e.g. 300ms) to hit the synchronization barrier. Accelerators experience 25–40% idle waste.

Furthermore, empirical studies (e.g., Qwen Python-tool experiments) show that under synchronous GRPO, models frequently experience **tool-use collapse**: the policy learns shortcuts to bypass Python/API tools to optimize aggregate reward, failing on complex enterprise tasks.

### 1.2 Core Architectural Principles

- **Asynchronous Actor-Learner Architecture**:
  - Trajectories are generated asynchronously without group barriers.
  - Completed trajectories flow directly into a streaming replay queue.
- **Strict Economic Metric: Cost Per Solved Task**:
  $$\text{Cost per solved task} = \frac{\text{Total GPU, Inference, Tool, and Engineering Costs}}{\text{Verified Successful Tasks}}$$
- **Tool Retention as a Gating Metric**:
  - Requires candidate models to maintain $\ge 90\%$ tool-use retention vs baseline.
- **Deterministic Promotion Threshold**:
  - Promotion requires $\ge 15-25\%$ reduction in cost per solved task with zero regression in task success rate.

---

## 2. CobbleDB Decoupled Hot Store Architecture

### 2.1 The Problem with Monolithic Cloud Databases (DynamoDB / Managed KV)

- **High Read Latency**: Median batch-read latencies of 31.4ms and p99 tails of 123ms.
- **Pay-Per-Byte/IOPS Metering**: Massive infrastructure bills on high-frequency agent search and market feature reads.
- **Contention**: Interleaving heavy transactional writes with latency-critical agent reads.

### 2.2 The CobbleDB Three-Tier Pattern

Stolen from Perplexity's Hot Store architecture:

1. **Tier 1: Durable Pillar**: Persistent append-only journal (`journal.jsonl` / WAL) serving as the immutable source of truth.
2. **Tier 2: Lorry Batch Accumulator**: Asynchronously gathers updates into partition-aligned immutable batch files without interfering with active read traffic.
3. **Tier 3: Cobble Serving Replicas**: Local-first embedded key-value engines (LRU in-memory cache + local SQLite/RocksDB NVMe store).
4. **Hedged Request Router**:
   - Dispatches read requests to primary partition replicas.
   - If primary latency exceeds `hedged_delay_ms` (e.g. 15ms), concurrently dispatches a hedged request to a secondary replica.
   - Slashes p99 tail latency from 123ms down to 24.2ms (82% reduction).

---

## 3. Production Verification

The modules are implemented and verified in the trading codebase:

- `src/ml/async_rollout_evaluator.py`: Trajectory telemetry, profiler, cost-per-solved-task calculator, and A/B harness.
- `src/data/cobble_hot_store.py`: 3-tier decoupled store with SHA-256 record checksums and hedged request router.
- `tests/ml/test_async_rollout_evaluator.py`: Validates straggler profiling, tool collapse detection, and promotion gates.
- `tests/data/test_cobble_hot_store.py`: Validates durable append, Lorry batching, LRU eviction, and hedged request winning.
