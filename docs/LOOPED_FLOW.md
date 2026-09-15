# Looped flow ticks (FORMAT steal)

<!-- Thinking with Looped Flows (arXiv:2609.11801) via @omarsar0.
     Not a neural trainer, ARC clone, or parameter-efficient LM. -->

**Sources:**

- Paper: [arXiv:2609.11801](https://arxiv.org/abs/2609.11801)
- Thread: [x.com/omarsar0/status/2098807354343260366](https://x.com/omarsar0/status/2098807354343260366)

## Steal

| Paper idea                           | Our rail                                            |
| ------------------------------------ | --------------------------------------------------- |
| Early updates must set up later ones | Each step emits a **local** goal-backward objective |
| Local denoising objectives           | `noise = failing_conditions / total`                |
| Shared noise ties steps              | `shared_noise_seed` → stable `residual_id`          |
| Finer time grid = more compute       | `--loop-steps N` (bounded ≤16)                      |
| Multi-solution via init noise        | Different `--seed` → different residual_id          |

## Commands

```bash
python3 scripts/looped_flow_tick.py --goal harness --loop-steps 3
python3 scripts/ralph_gsd_tick.py --looped-flow --goal cash --loop-steps 2 --seed dial-batch
```

## NEVER

- Train looped flow models / claim ARC-AGI scores from this repo
- Skip local verify and only check the final tick
- Confuse more loop steps with commercial fee-yes

## Related

Goal-backward (`scripts/goal_backward_verify.py`) supplies the TRUE conditions that
define “noise.” Checkpoints (`checkpoint_pick.py`) choose rope length; looped flow
spends that rope with local objectives.
