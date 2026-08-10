#!/usr/bin/env python3
"""Store one Alpaca paper credential from the macOS clipboard in Keychain.

The credential is never printed or written to a repository file. The clipboard is
cleared in a finally block after it is read.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess  # nosec B404 - fixed macOS clipboard and Keychain binaries
import sys
from dataclasses import dataclass

ACCOUNT = "paper"
SERVICE_PREFIX = "trading.alpaca.paper.api"
SERVICES = {
    "api-key": f"{SERVICE_PREFIX}-key",
    "api-secret": f"{SERVICE_PREFIX}-secret",
}


@dataclass(frozen=True)
class StoreResult:
    service: str
    length: int
    fingerprint: str


def _run(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - callers provide fixed absolute binaries only
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def read_clipboard() -> str:
    result = _run(["/usr/bin/pbpaste"])
    if result.returncode != 0:
        raise RuntimeError("could not read the macOS clipboard")
    value = result.stdout.strip()
    if not value:
        raise ValueError("clipboard is empty; copy the Alpaca paper credential first")
    return value


def clear_clipboard() -> None:
    result = _run(["/usr/bin/pbcopy"], input_text="")
    if result.returncode != 0:
        raise RuntimeError("credential consumed, but clipboard clearing failed")


def keychain_read(service: str) -> str:
    result = _run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            ACCOUNT,
            "-s",
            service,
            "-w",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"Keychain verification failed for service {service}")
    return result.stdout.rstrip("\n")


def keychain_write(service: str, value: str) -> None:
    # `security` has no stdin-only password option. Passing the value as one argv
    # element avoids shell history, expansion, and transcript output. The child is
    # short-lived and stdout/stderr are captured and never echoed.
    result = _run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-a",
            ACCOUNT,
            "-s",
            service,
            "-w",
            value,
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"Keychain write failed for service {service}")


def store_from_clipboard(kind: str) -> StoreResult:
    service = SERVICES[kind]
    value = read_clipboard()
    try:
        keychain_write(service, value)
        verified = keychain_read(service)
        if hashlib.sha256(verified.encode()).digest() != hashlib.sha256(value.encode()).digest():
            raise RuntimeError(f"Keychain verification mismatch for service {service}")
        return StoreResult(
            service=service,
            length=len(value),
            fingerprint=hashlib.sha256(value.encode()).hexdigest()[:12],
        )
    finally:
        clear_clipboard()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(SERVICES))
    parser.add_argument(
        "--from-clipboard",
        action="store_true",
        required=True,
        help="read the credential from the macOS clipboard and clear it after storage",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = store_from_clipboard(args.kind)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"stored service={result.service} account={ACCOUNT} "
        f"length={result.length} fingerprint={result.fingerprint} clipboard=cleared"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
