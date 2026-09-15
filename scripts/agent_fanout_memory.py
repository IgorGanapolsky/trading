#!/usr/bin/env python3
"""High-fanout agent sandbox memory budget (AgentZip FORMAT steal).

Paper: Memory Compression for High-Fanout Agent Sandboxes (arXiv:2609.11294)
via @omarsar0 — sandboxes share a template + related trajectories; 76–96% of
pages show template-relative or cross-sandbox redundancy. AgentZip cuts
sandbox-owned memory up to 8.7× by compressing against template/siblings and
doing heavy work while waiting on the LLM.

We do NOT ship a kernel compressor. Local FORMAT:
  - inventory worktrees as sandboxes
  - measure shared template (origin/main tip) vs diverged tips
  - host memory pressure + recommended max concurrent fan-out
  - shared context fingerprint (Agents.md / SPEC / constants) for reuse
  - prefetch list for restore-time warm of template files
  - advice: run expensive GC/hygiene during LLM wait, not tool bursts

EXIT 0 when under budget. EXIT 2 with --strict when over fan-out or memory floor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Soft floors for a 24–36GB Mac running multi-agent fleet
DEFAULT_MAX_WORKTREES = 12
DEFAULT_MIN_FREE_GB = 4.0
DEFAULT_GB_PER_SANDBOX = 1.5  # conservative agent+tooling RSS allowance

TEMPLATE_FILES = (
    "Agents.md",
    "AGENTS.md",
    "docs/SPEC.md",
    "docs/CONSTITUTION.md",
    "src/core/trading_constants.py",
    "data/runtime/strategy_kill_switch.json",
)


def _git(*args: str, cwd: Path = ROOT) -> str:
    git_bin = shutil.which("git")
    if not git_bin:
        raise RuntimeError("git not found")
    proc = subprocess.run(  # nosec B603
        [git_bin, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git failed")[:300])
    return proc.stdout.strip()


def list_worktrees(repo: Path = ROOT) -> list[dict]:
    raw = _git("worktree", "list", "--porcelain", cwd=repo)
    blocks = raw.split("\n\n") if raw else []
    out = []
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        row: dict = {"path": "", "head": "", "branch": "", "bare": False, "detached": False}
        for ln in lines:
            if ln.startswith("worktree "):
                row["path"] = ln[len("worktree ") :]
            elif ln.startswith("HEAD "):
                row["head"] = ln[len("HEAD ") :]
            elif ln.startswith("branch "):
                row["branch"] = ln[len("branch ") :].removeprefix("refs/heads/")
            elif ln == "bare":
                row["bare"] = True
            elif ln == "detached":
                row["detached"] = True
        if row["path"]:
            out.append(row)
    return out


def template_sha(repo: Path = ROOT) -> str | None:
    try:
        return _git("rev-parse", "origin/main", cwd=repo)
    except RuntimeError:
        try:
            return _git("rev-parse", "main", cwd=repo)
        except RuntimeError:
            return None


def shared_context_fingerprint(repo: Path = ROOT) -> dict:
    h = hashlib.sha256()
    included = []
    missing = []
    for rel in TEMPLATE_FILES:
        path = repo / rel
        if not path.exists():
            # case variants
            if rel == "AGENTS.md" and (repo / "Agents.md").exists():
                path = repo / "Agents.md"
            else:
                missing.append(rel)
                continue
        data = path.read_bytes()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(data)
        included.append(rel)
    return {
        "fingerprint": h.hexdigest()[:16],
        "files": included,
        "missing": missing,
        "note": "Sandboxes should reuse this template context pack — do not reload full AGENTS per sibling",
    }


def host_memory_gb() -> dict:
    """macOS-friendly free/total estimate via sysctl + vm_stat pages."""
    out: dict = {"ok": False}
    try:
        total = int(_run(["sysctl", "-n", "hw.memsize"]).strip())
        out["total_gb"] = round(total / (1024**3), 2)
    except (OSError, ValueError, RuntimeError):
        out["total_gb"] = None
    free_gb = None
    try:
        vm = _run(["vm_stat"])
        page_size = 16384
        m = re.search(r"page size of (\d+) bytes", vm)
        if m:
            page_size = int(m.group(1))

        def pages(label: str) -> int:
            mm = re.search(rf"{label}:\s+(\d+)\.", vm)
            return int(mm.group(1)) if mm else 0

        free_pages = pages("Pages free") + pages("Pages speculative")
        # purgeable + inactive are reclaimable under pressure
        reclaim = pages("Pages purgeable") + pages("Pages inactive")
        free_gb = (free_pages + reclaim * 0.5) * page_size / (1024**3)
        out["free_gb_est"] = round(free_gb, 2)
        out["ok"] = True
    except (OSError, RuntimeError, ValueError):
        out["free_gb_est"] = None
    return out


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(  # nosec B603
        cmd, capture_output=True, text=True, timeout=30, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "cmd failed")[:200])
    return proc.stdout


def evaluate(
    *,
    repo: Path = ROOT,
    max_worktrees: int = DEFAULT_MAX_WORKTREES,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    gb_per_sandbox: float = DEFAULT_GB_PER_SANDBOX,
) -> dict:
    trees = list_worktrees(repo)
    # Exclude primary checkout from "sandbox" count for fan-out pressure
    primary = str(repo.resolve())
    sandboxes = [t for t in trees if Path(t["path"]).resolve() != Path(primary).resolve()]
    tip = template_sha(repo)
    same_as_template = 0
    diverged = 0
    if tip:
        for t in sandboxes:
            if t.get("head") == tip:
                same_as_template += 1
            else:
                diverged += 1
    redundancy_ratio = round(same_as_template / len(sandboxes), 3) if sandboxes else None
    mem = host_memory_gb()
    free = mem.get("free_gb_est")
    mem_cap = None
    if free is not None:
        # Keep min_free_gb headroom
        usable = max(0.0, free - min_free_gb)
        mem_cap = int(usable // gb_per_sandbox)
    recommended_max = max_worktrees
    if mem_cap is not None:
        recommended_max = max(0, min(max_worktrees, mem_cap))

    breaches: list[dict] = []
    if len(sandboxes) > recommended_max:
        breaches.append(
            {
                "metric": "sandbox_count",
                "value": len(sandboxes),
                "threshold": recommended_max,
                "why": (
                    "AgentZip: high fan-out hits memory before CPU — prune stale "
                    "worktrees or wait for LLM-idle compression/hygiene window"
                ),
            }
        )
    if free is not None and free < min_free_gb:
        breaches.append(
            {
                "metric": "free_gb_est",
                "value": free,
                "threshold": min_free_gb,
                "why": "Host under memory floor — stop spawning sandboxes",
            }
        )

    ctx = shared_context_fingerprint(repo)
    prefetch = [f for f in ctx["files"]]

    return {
        "ok": len(breaches) == 0,
        "framework": "agent_fanout_memory",
        "stolen_format": (
            "AgentZip / arXiv:2609.11294 — template-relative + cross-sandbox "
            "redundancy FORMAT (not a kernel compressor clone)"
        ),
        "source": {
            "paper": "https://arxiv.org/abs/2609.11294",
            "tweet": "https://x.com/omarsar0/status/2098531286319341932",
        },
        "template_sha": tip,
        "worktrees_total": len(trees),
        "sandboxes": len(sandboxes),
        "sandboxes_on_template": same_as_template,
        "sandboxes_diverged": diverged,
        "template_redundancy_ratio": redundancy_ratio,
        "memory": mem,
        "budget": {
            "max_worktrees_config": max_worktrees,
            "min_free_gb": min_free_gb,
            "gb_per_sandbox": gb_per_sandbox,
            "recommended_max_sandboxes": recommended_max,
        },
        "shared_context": ctx,
        "prefetch_on_restore": prefetch,
        "scheduling": {
            "compress_or_gc_when": "LLM wait / between tool bursts (AgentZip when)",
            "avoid_when": "foreground tool execution / parallel pytest wall",
        },
        "breaches": breaches,
        "practices": {
            "prefer": (
                "One shared template context fingerprint per fan-out; prune "
                "stale worktrees; prefetch Agents/SPEC/constants on restore"
            ),
            "never": (
                "Clone AgentZip kernel; spawn unbounded sandboxes; reload full "
                "AGENTS.md independently in every sibling"
            ),
        },
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-worktrees", type=int, default=DEFAULT_MAX_WORKTREES)
    p.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    p.add_argument("--gb-per-sandbox", type=float, default=DEFAULT_GB_PER_SANDBOX)
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true", default=True)
    args = p.parse_args(argv)
    out = evaluate(
        max_worktrees=args.max_worktrees,
        min_free_gb=args.min_free_gb,
        gb_per_sandbox=args.gb_per_sandbox,
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
