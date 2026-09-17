"""Thin TypeSafe System One HTTP adapter (no SDK required).

Loads ``TYPESAFE_API_KEY`` from env, then macOS Keychain (hermes-fleet),
then ``~/.resume_secrets/TYPESAFE_API_KEY``. Never logs the secret.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
KEYCHAIN_SERVICE = "TYPESAFE_API_KEY"
KEYCHAIN_ACCOUNT = "hermes-fleet"
SECURE_FILE = Path.home() / ".resume_secrets" / "TYPESAFE_API_KEY"


def load_api_key(environ: Mapping[str, str] | None = None) -> Optional[str]:
    """Return TypeSafe API key or None. Never prints the value."""
    env = environ if environ is not None else os.environ
    raw = (env.get("TYPESAFE_API_KEY") or "").strip()
    if raw:
        return raw

    if os.name == "posix" and Path("/usr/bin/security").exists():
        try:
            import subprocess as _sp  # nosec B404 — Keychain CLI bridge only

            proc = _sp.run(  # nosec B603 — absolute binary + fixed argv
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-a",
                    KEYCHAIN_ACCOUNT,
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-w",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                value = (proc.stdout or "").strip()
                if value:
                    return value
        except Exception as exc:  # noqa: BLE001
            logger.debug("TypeSafe Keychain read failed: %s", exc)

    if SECURE_FILE.exists():
        try:
            value = SECURE_FILE.read_text(encoding="utf-8").strip()
            if value:
                return value
        except OSError as exc:
            logger.debug("TypeSafe secure-file read failed: %s", exc)
    return None


def system_one(
    *,
    state: Any,
    questions: Mapping[str, Any],
    api_key: str,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """POST a System One request. Returns parsed JSON body."""
    payload = {"state": state, "model": model, "questions": dict(questions)}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "igor-trading-typesafe-adapter/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 — fixed HTTPS API
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        raise RuntimeError(f"TypeSafe HTTP {exc.code}: {detail}") from exc
