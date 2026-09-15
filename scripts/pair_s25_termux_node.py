#!/usr/bin/env python3
"""Bootstrap/probe Galaxy S25 as elastic Ollama node (PAIR FORMAT companion).

Android is NOT an official NVIDIA PAIR OS. The phone joins our fleet router as an
elastic Termux Ollama endpoint on LAN when available.

Play Store Termux builds block `run-as` and often omit RunCommandService.
This script:
  1. Detects phone IP via adb
  2. Writes a bootstrap shell script to shared storage
  3. Tries to open Termux
  4. Probes http://<phone>:11434/api/tags
  5. Updates pair_fleet_nodes.json when healthy

Agent automates everything possible; if Termux must accept a one-time
allow-external-apps grant, the probe stays fail-closed until Ollama answers.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "data" / "runtime" / "pair_fleet_nodes.json"
BOOTSTRAP = """#!/data/data/com.termux/files/usr/bin/bash
# PAIR elastic node bootstrap for S25 — start Ollama on LAN
set -e
pkg install -y ollama 2>/dev/null || true
export OLLAMA_HOST=0.0.0.0:11434
# small model for phone RAM
ollama pull qwen2.5:1.5b-instruct 2>/dev/null || ollama pull tinyllama 2>/dev/null || true
exec ollama serve
"""


def _adb(*args: str, serial: str = "R3CY90QPM7E") -> str:
    adb = shutil.which("adb")
    if not adb:
        return "adb not found"
    cmd = [adb, "-s", serial, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)  # nosec B603
    return (r.stdout or "") + (r.stderr or "")


def phone_ip(serial: str = "R3CY90QPM7E") -> str | None:
    out = _adb("shell", "ip", "-f", "inet", "addr", "show", "wlan0", serial=serial)
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    if m:
        return m.group(1)
    out = _adb("shell", "dumpsys", "wifi", serial=serial)
    m = re.search(r"IP:\s*/(\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def write_bootstrap(serial: str = "R3CY90QPM7E") -> str:
    path = "/sdcard/Download/pair_s25_ollama_serve.sh"
    with tempfile.NamedTemporaryFile("w", suffix="_pair_s25.sh", delete=False) as tmp:
        tmp.write(BOOTSTRAP)
        local = tmp.name
    subprocess.run(  # nosec B603
        [shutil.which("adb") or "adb", "-s", serial, "push", local, path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    Path(local).unlink(missing_ok=True)
    _adb("shell", "am", "start", "-n", "com.termux/.app.TermuxActivity", serial=serial)
    return path


def probe(host: str, port: int = 11434) -> dict:
    url = f"http://{host}:{port}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # nosec B310
            data = json.loads(resp.read().decode())
        models = [m.get("name") for m in (data.get("models") or [])]
        return {"ok": True, "host": host, "port": port, "models": models}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "host": host, "port": port, "error": f"{type(exc).__name__}: {exc}"}


def update_nodes_config(host: str, *, ready: bool, models: list | None = None) -> None:
    NODES.parent.mkdir(parents=True, exist_ok=True)
    payload = {"nodes": [], "updated_at": datetime.now(UTC).isoformat()}
    if NODES.exists():
        try:
            payload = json.loads(NODES.read_text())
        except json.JSONDecodeError:
            pass
    nodes = payload.get("nodes") or []
    found = False
    for n in nodes:
        if n.get("id") == "s25-termux-ollama":
            n["base_url"] = f"http://{host}:11434"
            n["enabled"] = True
            n["last_probe_ok"] = ready
            n["models_cached"] = models or []
            found = True
    if not found:
        nodes.append(
            {
                "id": "s25-termux-ollama",
                "kind": "elastic_phone",
                "base_url": f"http://{host}:11434",
                "api": "ollama",
                "enabled": True,
                "last_probe_ok": ready,
                "models_cached": models or [],
                "notes": "Galaxy S25 Termux Ollama elastic node (not official PAIR OS)",
            }
        )
    payload["nodes"] = nodes
    payload["updated_at"] = datetime.now(UTC).isoformat()
    NODES.write_text(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", default="R3CY90QPM7E")
    p.add_argument("--bootstrap", action="store_true")
    args = p.parse_args(argv)
    ip = phone_ip(args.serial)
    out: dict = {
        "ok": False,
        "framework": "pair_s25_termux_node",
        "serial": args.serial,
        "ip": ip,
        "official_pair_os": False,
        "ts": datetime.now(UTC).isoformat(),
    }
    if not ip:
        out["error"] = "phone_ip_unavailable"
        print(json.dumps(out, indent=2))
        return 2
    if args.bootstrap:
        out["bootstrap_path"] = write_bootstrap(args.serial)
    status = probe(ip)
    out["probe"] = status
    out["ok"] = bool(status.get("ok"))
    update_nodes_config(ip, ready=out["ok"], models=status.get("models"))
    if not out["ok"]:
        out["next"] = (
            "Termux Play build blocks adb run-as/RunCommandService. "
            "Open Termux once and run the bootstrap script from Download, "
            "or enable allow-external-apps; agent will auto-detect when :11434 answers."
        )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
