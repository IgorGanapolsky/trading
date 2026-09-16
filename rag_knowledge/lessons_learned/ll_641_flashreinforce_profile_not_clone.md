# LL-641 — FlashREINFORCE FORMAT: profile rollouts, do not replace GRPO

Source: [YouTube Music v-LD_XChPkA](https://music.youtube.com/watch?v=v-LD_XChPkA) (2026-09-16)

## Steal (FORMAT)

1. Profile first: duration, straggler %, queue, tokens, tool calls, verified success, **cost per solved task**.
2. Async matters because fast trajectories wait on slow ones in synchronized GRPO groups — not because "one rollout" is a brand.
3. Tool-use retention is a gate. A trainer that drives tool calls to zero is a fail for an agent desk even if reward ticks up.
4. Half the rollouts ≠ half the GPU-hours, memory, wall time, or dollars.

## Do not

- Replace `src/ml/grpo_trade_learner.py` with FlashREINFORCE.
- Clone NVIDIA Molt or build a custom async RL platform.
- Start with "general agent intelligence." Contained family here: `spy_put_credit` paper dry-run (verifiable plan).
- Promote on raw reward alone.
- Claim GRPO is the operator path (it is optional research).

## Ship

`scripts/rollout_cost_profile.py` profile|compare. Promotion: ≥15% lower cost/solved **or** higher success at equal/better cost, and tools must not collapse.

## Cash

This is ops/eval hygiene. Commercial fee-yes is still a separate F.
