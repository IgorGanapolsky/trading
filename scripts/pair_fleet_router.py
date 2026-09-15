#!/usr/bin/env python3
"""PAIR-FORMAT fleet inference router for the trading/Hermes harness.

Sources:
- https://developer.nvidia.com/blog/nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/
- https://www.infoq.com/news/2026/09/nvidia-pair-ai-task-router/

Steal (not a NVIDIA PAIR product clone):
  - One familiar OpenAI/Ollama-compatible endpoint view for agents
  - Route *independent* requests to eligible nodes (never shard one request)
  - Eligibility: online + engine up + exact model present + load
  - Elastic clients: nodes can appear/disappear
  - Jobs ledger = placement ground truth (PAIR Jobs view FORMAT)
  - Official PAIR on Mac (:11434) is preferred when healthy
  - Samsung Galaxy S25 can join as Termux Ollama elastic node (Android is not
    official PAIR; LAN probe when Termux serves :11434)

EXIT 0 always for status. EXIT 2 with --strict if no eligible node for model.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

# ThreadPoolExecutor imported once at module scope for inventory + fanout.

ROOT = Path(__file__).resolve().parents[1]
JOBS_LOG = ROOT / "data" / "runtime" / "pair_fleet_jobs.jsonl"
NODES_CONFIG = ROOT / "data" / "runtime" / "pair_fleet_nodes.json"

DEFAULT_NODES = [
    {
        "id": "mac-pair-local",
        "kind": "nvidia_pair_proxy",
        "base_url": "http://127.0.0.1:11434",
        "api": "openai",  # /v1/models
        "enabled": True,
        "notes": "NVIDIA PAIR ollama-proxy on Mac (preferred)",
    },
    {
        "id": "mac-ollama-engine",
        "kind": "ollama_engine",
        "base_url": "http://127.0.0.1:11435",
        "api": "ollama",  # /api/tags
        "enabled": True,
        "notes": "Direct engine behind PAIR — use only if proxy down",
    },
    {
        "id": "s25-termux-ollama",
        "kind": "elastic_phone",
        "base_url": "http://192.168.12.237:11434",
        "api": "ollama",
        "enabled": True,
        "notes": "Galaxy S25 Termux Ollama when serving on LAN (not official PAIR OS)",
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _http_json(url: str, *, timeout: float = 2.5, data: dict | None = None) -> dict | None:
    try:
        body = None
        headers = {"Accept": "application/json"}
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST" if data else "GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def load_nodes() -> list[dict]:
    if NODES_CONFIG.exists():
        try:
            raw = json.loads(NODES_CONFIG.read_text())
            if isinstance(raw, list) and raw:
                return raw
            if isinstance(raw, dict) and isinstance(raw.get("nodes"), list):
                return raw["nodes"]
        except (OSError, json.JSONDecodeError):
            pass
    return list(DEFAULT_NODES)


def save_nodes(nodes: list[dict]) -> None:
    NODES_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    NODES_CONFIG.write_text(json.dumps({"nodes": nodes, "updated_at": _now()}, indent=2))


def list_models(node: dict) -> list[str]:
    base = node["base_url"].rstrip("/")
    if node.get("api") == "openai":
        data = _http_json(f"{base}/v1/models")
        if not data:
            return []
        return [m.get("id") or m.get("name") or "" for m in (data.get("data") or []) if m]
    data = _http_json(f"{base}/api/tags")
    if not data:
        return []
    return [m.get("name") or m.get("model") or "" for m in (data.get("models") or []) if m]


def probe_node(node: dict) -> dict:
    t0 = time.monotonic()
    models = list_models(node) if node.get("enabled", True) else []
    ready = bool(models)
    return {
        **node,
        "ready": ready,
        "models": models,
        "model_count": len(models),
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        "probed_at": _now(),
    }


def inventory() -> dict:
    nodes = load_nodes()
    probed = []
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(nodes)))) as pool:
        futs = {pool.submit(probe_node, n): n for n in nodes}
        for fut in as_completed(futs):
            probed.append(fut.result())
    probed.sort(key=lambda n: (not n.get("ready"), n.get("id") or ""))
    ready = [n for n in probed if n.get("ready")]
    upstream = None
    try:
        from pair_upstream_doctor import doctor as _doctor

        upstream = _doctor(smoke=False)
    except Exception as exc:  # noqa: BLE001
        upstream = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "ok": bool(ready),
        "framework": "pair_fleet_router",
        "upstream_doctor": upstream,
        "stolen_format": (
            "NVIDIA PAIR FORMAT — route independent inference across local nodes; "
            "no harness API change; Jobs ledger for placement (not VRAM pooling)"
        ),
        "source": {
            "github": "https://github.com/NVIDIA/Personal-AI-Router",
            "nvidia_blog": (
                "https://developer.nvidia.com/blog/"
                "nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/"
            ),
            "infoq": "https://www.infoq.com/news/2026/09/nvidia-pair-ai-task-router/",
        },
        "nodes": probed,
        "ready_count": len(ready),
        "never": [
            "merge GPUs / pool VRAM",
            "shard one request across machines",
            "claim multi-node without Jobs ledger proof",
            "treat Android as official PAIR OS",
        ],
        "ts": _now(),
    }


def select_node(inv: dict, *, model: str) -> dict | None:
    """Pick one eligible ready node that advertises the model (least load heuristic)."""
    model = (model or "").strip()
    candidates = []
    for n in inv.get("nodes") or []:
        if not n.get("ready"):
            continue
        names = n.get("models") or []
        # Exact / same-tag variants only — do NOT match whole model family (qwen2.5:*).
        if any(m == model or m.startswith(model + ":") or m.startswith(model + "-") for m in names):
            # Prefer official PAIR proxy over direct engine / phone
            prefer = (
                0
                if n.get("kind") == "nvidia_pair_proxy"
                else 1
                if n.get("kind") == "ollama_engine"
                else 2
            )
            candidates.append((prefer, n.get("latency_ms") or 9999, n))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def append_job(row: dict) -> None:
    JOBS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with JOBS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def chat(
    *,
    model: str,
    prompt: str,
    max_tokens: int = 64,
) -> dict:
    """Route one independent chat completion to an eligible node."""
    inv = inventory()
    node = select_node(inv, model=model)
    job = {
        "id": f"job-{int(time.time() * 1000)}",
        "ts": _now(),
        "model": model,
        "status": "pending",
        "node_id": None,
        "base_url": None,
    }
    if not node:
        job["status"] = "no_eligible_node"
        append_job(job)
        return {
            "ok": False,
            "error": "no_eligible_node",
            "model": model,
            "inventory": inv,
            "job": job,
        }

    base = node["base_url"].rstrip("/")
    job["node_id"] = node["id"]
    job["base_url"] = base
    job["kind"] = node.get("kind")
    t0 = time.monotonic()

    if node.get("api") == "openai" or "11434" in base and node.get("kind") == "nvidia_pair_proxy":
        payload = _http_json(
            f"{base}/v1/chat/completions",
            timeout=120,
            data={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
            },
        )
        content = None
        if payload:
            choices = payload.get("choices") or []
            if choices:
                content = (choices[0].get("message") or {}).get("content")
        ok = content is not None
    else:
        payload = _http_json(
            f"{base}/api/generate",
            timeout=120,
            data={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        content = (payload or {}).get("response")
        ok = content is not None

    job["status"] = "ok" if ok else "failed"
    job["elapsed_ms"] = round((time.monotonic() - t0) * 1000, 1)
    append_job(job)
    return {
        "ok": ok,
        "content": content,
        "model": model,
        "node": {"id": node["id"], "kind": node.get("kind"), "base_url": base},
        "job": job,
        "inventory_ready": inv.get("ready_count"),
    }


def fanout_demo(prompts: list[str], *, model: str) -> dict:
    """Independent requests in parallel — PAIR's multi-agent sweet spot."""
    results = []
    with ThreadPoolExecutor(max_workers=min(len(prompts), 4) or 1) as pool:
        futs = [pool.submit(chat, model=model, prompt=p, max_tokens=24) for p in prompts]
        for fut in as_completed(futs):
            results.append(fut.result())
    nodes_used = sorted({(r.get("node") or {}).get("id") for r in results if r.get("ok")})
    return {
        "ok": all(r.get("ok") for r in results),
        "framework": "pair_fleet_router",
        "jobs": len(results),
        "nodes_used": nodes_used,
        "multi_node_proven": len(nodes_used) > 1,
        "results": results,
        "note": "Claim multi-node only when nodes_used > 1 (Jobs ledger ground truth)",
        "ts": _now(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory", help="probe configured nodes")
    c = sub.add_parser("chat", help="route one independent completion")
    c.add_argument("--model", default=os.environ.get("PAIR_MODEL", "qwen2.5:3b-hermes-64k"))
    c.add_argument("--prompt", default="Reply with exactly: PAIR_OK")
    f = sub.add_parser("fanout", help="parallel independent prompts")
    f.add_argument("--model", default=os.environ.get("PAIR_MODEL", "qwen2.5:3b-hermes-64k"))
    f.add_argument("--n", type=int, default=3)
    s = sub.add_parser("seed-config", help="write default nodes config")
    s.add_argument("--s25-host", default="192.168.12.237")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    if args.cmd == "seed-config":
        nodes = list(DEFAULT_NODES)
        for n in nodes:
            if n["id"] == "s25-termux-ollama":
                n["base_url"] = f"http://{args.s25_host}:11434"
        save_nodes(nodes)
        print(json.dumps({"ok": True, "path": str(NODES_CONFIG), "nodes": nodes}, indent=2))
        return 0
    if args.cmd == "inventory":
        out = inventory()
        print(json.dumps(out, indent=2, sort_keys=True))
        if args.strict and not out.get("ok"):
            return 2
        return 0
    if args.cmd == "chat":
        out = chat(model=args.model, prompt=args.prompt)
        print(json.dumps(out, indent=2, sort_keys=True))
        if args.strict and not out.get("ok"):
            return 2
        return 0
    if args.cmd == "fanout":
        prompts = [f"Reply with exactly: JOB_{i}" for i in range(args.n)]
        out = fanout_demo(prompts, model=args.model)
        print(json.dumps(out, indent=2, sort_keys=True))
        if args.strict and not out.get("ok"):
            return 2
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
