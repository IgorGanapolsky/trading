"""Package-manager honesty: keep uv.lock, refuse a pnpm/npm/yarn switch.

InfoQ pnpm 12 FORMAT steal (https://www.infoq.com/news/2026/09/pnpm-12-rust/):
the lockfile and installer contract stay; a rewrite is not a migration.
Their 15ms / 64–90% figures are not ours. Do not vendor pnpm.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CANONICAL = "uv"
UV_LOCK = "uv.lock"
PYPROJECT = "pyproject.toml"
FOREIGN_LOCKFILES = (
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "poetry.lock",
    "Pipfile.lock",
)
FORBIDDEN_CLAIMS = (
    "15ms repeated install",
    "64.4%",
    "90.5%",
    "pnpm self-update next-12",
)
ALLOWED_MARKERS = (
    "uv sync --frozen",
    "uv lock --check",
    "uv lock --frozen",
)
DENIED_MARKERS = (
    "pnpm install",
    "pnpm i ",
    "pnpm i\t",
    "npm ci",
    "npm install",
    "yarn install",
    "bun install",
    "poetry install",
    "pipenv install",
)
UNPINNED_PIP_MARKERS = (
    "pip install -r",
    "pip3 install -r",
    "python -m pip install -r",
)


def lookalike_hits(source: str) -> list[str]:
    lowered = source.lower()
    return [snip for snip in FORBIDDEN_CLAIMS if snip in lowered]


def scan_tree(root: Path) -> dict[str, Any]:
    """Fail closed on missing uv.lock or a second package-manager lockfile."""

    base = Path(root)
    uv_lock = (base / UV_LOCK).is_file()
    pyproject = (base / PYPROJECT).is_file()
    foreign = [name for name in FOREIGN_LOCKFILES if (base / name).is_file()]
    if not uv_lock or not pyproject:
        status = "UNAVAILABLE"
        ok = False
        reason = "canonical uv.lock + pyproject.toml required"
    elif foreign:
        status = "DUAL_LOCKFILE"
        ok = False
        reason = "second package-manager lockfile is a silent switch"
    else:
        status = "ok"
        ok = True
        reason = "uv.lock is the installer contract; pnpm 12 speedup is not ours"
    return {
        "ok": ok,
        "status": status,
        "reason": reason,
        "canonical": CANONICAL if uv_lock else None,
        "uv_lock": uv_lock,
        "pyproject": pyproject,
        "foreign_lockfiles": foreign,
        "do_not_migrate_to_pnpm": True,
        "pnpm_speedup_is_not_ours": True,
        "lifecycle_scripts_default_deny": True,
        "keep_lockfile_format": True,
    }


def classify_command(
    command: str,
    *,
    has_uv_lock: bool = True,
    propose_switch: str | None = None,
) -> dict[str, Any]:
    """Classify an install command. Switching managers is denied."""

    text = " ".join(str(command or "").split())
    lowered = text.lower()
    switch = (propose_switch or "").strip().lower()
    if switch and switch not in {"", "uv", "none"}:
        return {
            "role": "denied",
            "allowed": False,
            "command": text,
            "reason": f"refuse package-manager switch to {switch!r}; keep {CANONICAL}",
            "matched": [f"propose-switch={switch}"],
            "canonical": CANONICAL,
            "pnpm_speedup_is_not_ours": True,
        }

    denied = [marker.strip() for marker in DENIED_MARKERS if marker.strip() in lowered]
    if denied:
        return {
            "role": "denied",
            "allowed": False,
            "command": text,
            "reason": "foreign installer; this repo's contract is uv.lock",
            "matched": denied,
            "canonical": CANONICAL,
            "pnpm_speedup_is_not_ours": True,
        }

    if has_uv_lock and any(marker in lowered for marker in UNPINNED_PIP_MARKERS):
        return {
            "role": "denied",
            "allowed": False,
            "command": text,
            "reason": "unpinned pip -r while uv.lock exists (npm-scripts analog: untrusted install path)",
            "matched": [m for m in UNPINNED_PIP_MARKERS if m in lowered],
            "canonical": CANONICAL,
            "pnpm_speedup_is_not_ours": True,
            "lifecycle_scripts_default_deny": True,
        }

    if any(marker in lowered for marker in ALLOWED_MARKERS):
        return {
            "role": "frozen_lock",
            "allowed": True,
            "command": text,
            "reason": "frozen uv lock analog of pnpm 12 keeping the lockfile format",
            "canonical": CANONICAL,
            "pnpm_speedup_is_not_ours": True,
        }

    return {
        "role": "unknown",
        "allowed": False,
        "command": text,
        "reason": "not a frozen-uv install; do not invent a pnpm alias",
        "canonical": CANONICAL,
        "pnpm_speedup_is_not_ours": True,
    }
