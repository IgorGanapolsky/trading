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
- Network allowlist uses `urlsplit` hostname only; `test_network_rejects_userinfo_host_spoof` blocks `user@host` SSRF-shaped authority tricks (CodeRabbit on #4515)
- Never commit machine `/Users/<user>/` paths into RAG/docs — `absolute-user-path` hygiene + `scripts/check_staged_absolute_paths.py` (see LL-588)
- Do not land primary-checkout Gemini/edge/context theater SKUs on unrelated claimed branches
