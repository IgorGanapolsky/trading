# LL-633 — Cache teachers; iterate the student

**Date:** 2026-09-15  
**Source:** <https://www.linkedin.com/blog/engineering/infrastructure/the-training-infrastructure-behind-ai-powered-job-search-eight-x-faster-multi-teacher-distillation>  
**Issue:** AGENT-633

## Lesson

LinkedIn’s 8× win is mostly eliminating redundant teacher inference when only
the student changes — offline per-shard caches keyed by teacher version + data
fingerprint. Same for our probes: don’t re-score every tick when signals are warm.

## Prevention

`multi_teacher_distill.py` pluggable teachers + cache amortization metrics.

## Evidence

pytest: second pass teacher_calls==0 with warm cache.
