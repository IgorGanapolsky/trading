#!/usr/bin/env python3
"""Doctor for the *installed* NVIDIA Personal AI Router (upstream GitHub).

Upstream: https://github.com/NVIDIA/Personal-AI-Router
Does not reimplement PAIR — verifies the local install and records Jobs-compatible
placement for the harness.

Checks:
  - ~/.nvpair binaries present
  - ollama-proxy listening on :11434
  - engine on :11435 (behind proxy)
  - OpenAI-compatible /v1/models
  - optional chat smoke
  - honest limits: no VRAM pool; Android not official OS
"""

from __future__ import annotations

import argparse
import json
import socket
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HOME = Path.home()
NVPAIR = HOME / ".nvpair"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _get(url: str, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001
        return None


def doctor(*, smoke: bool = False) -> dict:
    checks = []
    manifest = NVPAIR / "manifest.json"
    checks.append(
        {
            "id": "nvpair_dir",
            "ok": NVPAIR.is_dir(),
            "detail": str(NVPAIR),
        }
    )
    product = None
    if manifest.exists():
        try:
            product = json.loads(manifest.read_text()).get("product")
        except json.JSONDecodeError:
            product = None
    checks.append(
        {
            "id": "manifest",
            "ok": product is not None,
            "product": product,
            "upstream": "https://github.com/NVIDIA/Personal-AI-Router",
        }
    )
    for name in ("ollama-proxy", "nvpair-tui", "nvpair-job-scheduler"):
        path = NVPAIR / name
        checks.append({"id": f"bin_{name}", "ok": path.exists(), "path": str(path)})

    proxy_up = _port_open("127.0.0.1", 11434)
    engine_up = _port_open("127.0.0.1", 11435)
    checks.append({"id": "proxy_11434", "ok": proxy_up})
    checks.append({"id": "engine_11435", "ok": engine_up})

    models = []
    data = _get("http://127.0.0.1:11434/v1/models") if proxy_up else None
    if data:
        models = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
    checks.append(
        {
            "id": "v1_models",
            "ok": bool(models),
            "models": models[:12],
        }
    )

    smoke_ok = None
    if smoke and models:
        model = "qwen2.5:3b-hermes-64k" if "qwen2.5:3b-hermes-64k" in models else models[0]
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/v1/chat/completions",
                data=json.dumps(
                    {
                        "model": model,
                        "messages": [{"role": "user", "content": "Reply with exactly: PAIR_OK"}],
                        "max_tokens": 16,
                        "temperature": 0,
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
                body = json.loads(resp.read().decode())
            content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            smoke_ok = "PAIR_OK" in content
        except Exception as exc:  # noqa: BLE001
            smoke_ok = False
            checks.append({"id": "smoke_error", "ok": False, "detail": str(exc)})
    if smoke:
        checks.append({"id": "chat_smoke", "ok": bool(smoke_ok)})

    hard = [
        c
        for c in checks
        if c["id"] in {"nvpair_dir", "proxy_11434", "v1_models"} and not c.get("ok")
    ]
    return {
        "ok": len(hard) == 0,
        "framework": "pair_upstream_doctor",
        "stolen_format": "Verify upstream NVIDIA/Personal-AI-Router install; harness stays on OpenAI/Ollama proxy",
        "source": {"github": "https://github.com/NVIDIA/Personal-AI-Router"},
        "limits": {
            "no_vram_pool": True,
            "no_request_shard": True,
            "android_official": False,
            "os_support": ["Windows 11", "Linux", "macOS"],
        },
        "checks": checks,
        "hard_fails": [c["id"] for c in hard],
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = doctor(smoke=args.smoke)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
