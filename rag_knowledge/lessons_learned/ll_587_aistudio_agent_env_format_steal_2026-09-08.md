# LL-587 — AI Studio agents FORMAT: allowlists + sources + stop (2026-09-08)

## Context

CEO: implement/test high-ROI from <https://aistudio.google.com/docs/agents>
(canonical text: <https://ai.google.dev/gemini-api/docs/aistudio-agents>).
AGENT-595.

## Steal (FORMAT only)

1. Deny-by-default **tool allowlist** (forbid submit_order/liquidate/live).
2. **Network allowlist** for egress (Alpaca/GitHub/Linear/localhost).
3. **Sources pack**: AGENTS.md + skills/\*/SKILL.md present.
4. **Termination criteria**: stop/out-of-scope + ≥1 AC (cost control FORMAT).

## Non-goals / refuse

- Google AI Studio Playground / Antigravity billed runs
- Vertex Agent Builder / Managed Agents API
- Untracked primary-checkout Gemini/edge/context theater SKUs

## Prevention

- `scripts/aistudio_agent_env_doctor.py` + `make aistudio-roi`
- Tests cover forbidden tools, unknown domains, missing stop/AC
