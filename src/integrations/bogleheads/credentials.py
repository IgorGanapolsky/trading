"""Retrieve Bogleheads credentials from macOS Keychain only (never hardcode)."""

from __future__ import annotations

import subprocess  # nosec B404
from dataclasses import dataclass


@dataclass(frozen=True)
class BogleheadsCredentials:
    email: str
    username: str
    password: str

    def masked(self) -> dict[str, str | int]:
        return {
            "email": self.email,
            "username": self.username,
            "password_len": len(self.password),
        }


def _keychain_get(account: str, service: str) -> str | None:
    try:
        out = subprocess.run(  # nosec B603
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                account,
                "-s",
                service,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    value = (out.stdout or "").rstrip("\n")
    return value or None


def load_credentials() -> BogleheadsCredentials:
    """Load username/password/email from Keychain.

    Preferred labels (written by chat ingest):
      - account iganapolsky@gmail.com / service bogleheads.org  → password
      - account iganapolsky@gmail.com / service bogleheads.org.username
      - hermes-fleet / BOGLEHEADS_USERNAME|PASSWORD|EMAIL
    """
    email = _keychain_get("hermes-fleet", "BOGLEHEADS_EMAIL") or "iganapolsky@gmail.com"
    username = (
        _keychain_get("hermes-fleet", "BOGLEHEADS_USERNAME")
        or _keychain_get(email, "bogleheads.org.username")
        or _keychain_get("eazyigz", "bogleheads.org.username")
        or "eazyigz"
    )
    password = (
        _keychain_get("hermes-fleet", "BOGLEHEADS_PASSWORD")
        or _keychain_get(email, "bogleheads.org")
        or _keychain_get("eazyigz", "bogleheads.org")
    )
    if not password:
        raise RuntimeError(
            "Bogleheads password missing from Keychain "
            "(expected hermes-fleet/BOGLEHEADS_PASSWORD or "
            f"{email}/bogleheads.org)"
        )
    if not username:
        raise RuntimeError("Bogleheads username missing from Keychain")
    return BogleheadsCredentials(email=email, username=username, password=password)
