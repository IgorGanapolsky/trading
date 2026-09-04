# LL-574 — Speculative decode is n-gram verify, not TensorRT

**Date:** 2026-09-04
**Severity:** 3
**Linear:** AGENT-574

## Mistake class

Cloning NVIDIA TensorRT-LLM / EAGLE training, or citing their SPEED-Bench
speedup as ours, instead of shipping the model-free suffix/n-gram row.

## Correction

Draft D tokens from n-gram suffix match. Target accepts until first mismatch
(lossless). Measure AL. Increase D only while AL/(1+Od) improves. GPU GEMM
guidelines stay backlog without our hardware measurements.

## Prevention

`tests/test_speculative_decode.py` refuses lookalike TensorRT/EAGLE snippets
and requires `estimated_speedup is None` when AL is 0.
