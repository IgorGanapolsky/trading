# PAIR fleet router (NVIDIA FORMAT)

<!-- FORMAT steal from NVIDIA PAIR + InfoQ Sep 2026. Not a product clone. -->

**Sources:**

- [NVIDIA blog](https://developer.nvidia.com/blog/nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/)
- [InfoQ](https://www.infoq.com/news/2026/09/nvidia-pair-ai-task-router/)

## Steal

| PAIR idea                           | Our rail                                |
| ----------------------------------- | --------------------------------------- |
| Familiar Ollama/OpenAI endpoint     | Prefer Mac `127.0.0.1:11434` PAIR proxy |
| Route independent requests          | `pair_fleet_router.py chat/fanout`      |
| Eligibility = online+engine+model   | `inventory` / `select_node`             |
| Jobs view = ground truth            | `data/runtime/pair_fleet_jobs.jsonl`    |
| Elastic clients                     | Nodes in `pair_fleet_nodes.json`        |
| Never pool VRAM / shard one request | Explicit `never` in inventory JSON      |

## Nodes

| Node                | Role                                                                |
| ------------------- | ------------------------------------------------------------------- |
| `mac-pair-local`    | Official NVIDIA PAIR proxy (preferred)                              |
| `mac-ollama-engine` | Direct `:11435` fallback                                            |
| `s25-termux-ollama` | Galaxy S25 Termux Ollama on LAN (elastic; **not** official PAIR OS) |

## S25 note

Play Store Termux blocks adb `run-as` / RunCommandService. Agent writes bootstrap to
`/sdcard/Download/pair_s25_ollama_serve.sh` and probes LAN. When Termux serves
`:11434`, the fleet router auto-includes it.

## NEVER

- Claim multi-node without Jobs ledger showing >1 `node_id`
- Merge GPUs / pool VRAM
- Require harness API changes (proxy stays OpenAI/Ollama shaped)
