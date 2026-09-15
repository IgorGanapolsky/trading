# HydraFusion routing FORMAT (InfoQ / GitHub)

<!-- FORMAT steal from GitHub Project HydraFusion via InfoQ (Sep 2026).
     Not Copilot CLI /experimental and not a multi-provider SaaS router. -->

**Sources:**

- [InfoQ news](https://www.infoq.com/news/2026/09/github-hydrafusion/)
- [GitHub blog](https://github.blog/ai-and-ml/github-copilot/project-hydrafusion-frontier-quality-via-multi-model-orchestration/)

## Steal

| HydraFusion         | Our rail                                                               |
| ------------------- | ---------------------------------------------------------------------- |
| **Single**          | One Ralph tick / quick path                                            |
| **Cascade**         | Draft → `verify_complete` gate → escalate `goal_backward` only if fail |
| **Critique**        | Draft → tool-less critic → one revision → fail-safe validate           |
| Complete accounting | `cost_units` on every leg                                              |
| Bounded execution   | `timeout_s` + max legs                                                 |
| Isolated review     | Critic `tools_allowed=false`                                           |
| Fail-safe apply     | Validator/gate before accept                                           |
| Validated routing   | Scripts must exist before run                                          |

## Commands

```bash
python3 scripts/hydrafusion_route.py --task "fix flaky CI"
python3 scripts/hydrafusion_route.py --task "kill switch" --high-risk
python3 scripts/ralph_gsd_tick.py --hydrafusion-route --task "typo" --throwaway
```

## NEVER

- Enable Copilot HydraFusion /experimental here
- Give the critic write/tool authority
- Always-frontier every tick (defeats Cascade savings)
