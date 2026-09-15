# Multi-teacher distillation FORMAT (LinkedIn infra)

<!-- FORMAT steal from LinkedIn "8X faster multi-teacher distillation" (Aug 2026).
     Not Ray / FSDP / H200 / SGLang training SaaS. -->

**Sources:**

- [InfoQ](https://www.infoq.com/news/2026/09/linkedin-ai-multi-teacher/)
- [LinkedIn engineering](https://www.linkedin.com/blog/engineering/infrastructure/the-training-infrastructure-behind-ai-powered-job-search-eight-x-faster-multi-teacher-distillation)

## Steal

| LinkedIn idea                         | Our rail                                                 |
| ------------------------------------- | -------------------------------------------------------- |
| Pluggable specialized teachers        | `relevance` / `engagement` / `embedding` teachers        |
| Offline cache by model+data version   | `data/runtime/teacher_cache/<id>/<ver>/`                 |
| Per-shard cache                       | one JSON per example id + data fingerprint               |
| Online vs offline per teacher         | `mode=auto\|online\|offline`                             |
| Student iterates without teacher GPUs | `fuse_student` from cached soft labels                   |
| 8× narrative                          | eliminate redundant teacher re-infer across student runs |

## Why it pays here

Agents re-run expensive probes every tick. Cache teacher signals; iterate the
“student” (fusion / pick / rank) cheaply. Same shape as LinkedIn: teachers
stabilize → runs converge to fully cached.

## NEVER

- Train billion-param teachers in this lab
- Claim 22k QPS/GPU or H200 HFU numbers as ours
- Invalidate all teacher caches when only student weights change

## InfoQ additions

- Collector merge: average or learned weights
- Convergence: online while teachers change → offline when stable
- Compounding speedups (cache amortization), not one GPU trick
