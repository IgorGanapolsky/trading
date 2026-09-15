# Agent fan-out memory (AgentZip FORMAT)

<!-- FORMAT steal from arXiv:2609.11294 via @omarsar0. Not a kernel/page
     compressor product clone. -->

**Sources:**

- Paper: [arXiv:2609.11294](https://arxiv.org/abs/2609.11294)
- Thread: [x.com/omarsar0/status/2098531286319341932](https://x.com/omarsar0/status/2098531286319341932)

## Steal

| Paper idea                   | Our rail                                              |
| ---------------------------- | ----------------------------------------------------- |
| Template-relative redundancy | `template_sha` + sandboxes still on `origin/main` tip |
| Cross-sandbox redundancy     | count siblings; recommend prune over spawn            |
| What/when to compress        | GC/hygiene during **LLM wait**, not tool bursts       |
| Prefetch at restore          | `prefetch_on_restore` shared Agents/SPEC/constants    |
| Memory is the capacity limit | `recommended_max_sandboxes` from free GB              |

## Commands

```bash
python3 scripts/agent_fanout_memory.py
python3 scripts/ralph_gsd_tick.py --fanout-memory --strict
```

## NEVER

- Implement AgentZip kernel modules here
- Spawn unbounded worktrees / subagents when `free_gb_est` is under floor
- Reload full AGENTS.md independently in every sibling (reuse fingerprint)
