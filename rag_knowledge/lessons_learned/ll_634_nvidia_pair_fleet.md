# LL-634 — PAIR: route independent jobs; Jobs ledger is ground truth

**Date:** 2026-09-15  
**Sources:** NVIDIA PAIR blog · InfoQ nvidia-pair-ai-task-router  
**Issue:** AGENT-634

## Lesson

PAIR widens multi-agent inference by placing each independent request on one
eligible node. It does not merge GPUs. Claim multi-node only when the Jobs
ledger shows >1 node_id. Android is not official PAIR OS — S25 joins as Termux
Ollama elastic capacity when :11434 answers on LAN.

## Prevention

`pair_fleet_router` inventory + jobs JSONL; prefer Mac PAIR proxy.

## Evidence

PAIR_OK via router; inventory ready_count>=1 on Mac.
