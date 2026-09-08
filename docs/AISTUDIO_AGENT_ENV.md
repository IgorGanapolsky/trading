# AI Studio agent environment (trading FORMAT steal)

Source docs: [AI Studio agents](https://aistudio.google.com/docs/agents) /
[Gemini API aistudio-agents](https://ai.google.dev/gemini-api/docs/aistudio-agents).

| Theme                                          | Trading surface                                                 |
| ---------------------------------------------- | --------------------------------------------------------------- |
| Tool toggles (deny by default)                 | `check_tool_allowlist` in `src/ops/agent_environment_doctor.py` |
| Network allow list                             | `check_network_allowlist` (Alpaca/GitHub/Linear/localhost)      |
| Environment sources (`AGENTS.md` + `SKILL.md`) | `check_sources_pack`                                            |
| Termination / stop criteria                    | `check_termination_criteria`                                    |
| Doctor CLI                                     | `scripts/aistudio_agent_env_doctor.py`                          |

## Commands

```bash
.venv/bin/python scripts/aistudio_agent_env_doctor.py \
  --tools 'context_gist,system_health_check,aistudio_agent_env_doctor' \
  --domains 'api.github.com' \
  --acs 'tests pass|CLI fail-closed'

make aistudio-roi
```

## Explicit non-goals

- Do not run billed Google AI Studio / Antigravity playground agents as the deliverable.
- Do not adopt Vertex Agent Builder or Managed Agents API.
- Do not ship the untracked primary-checkout Gemini/edge/context theater SKUs.
- Do not allow `submit_order` / `liquidate` / live submit via the tool allowlist.
