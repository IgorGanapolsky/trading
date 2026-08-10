#!/usr/bin/env python3
"""Run a command with Alpaca paper credentials loaded from macOS Keychain."""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404 - fixed macOS Keychain binary and explicit child command
import sys
from dataclasses import dataclass

ACCOUNT = "paper"
KEY_SERVICE = "trading.alpaca.paper.api-key"
SECRET_SERVICE = "trading.alpaca.paper.api-secret"  # nosec B105 - Keychain service name


@dataclass(frozen=True)
class Credentials:
    api_key: str
    api_secret: str


def _keychain_read(service: str) -> str | None:
    result = subprocess.run(  # nosec B603 - argv starts with fixed /usr/bin/security
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            ACCOUNT,
            "-s",
            service,
            "-w",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.rstrip("\n")
    return value or None


def load_credentials() -> Credentials | None:
    api_key = _keychain_read(KEY_SERVICE)
    api_secret = _keychain_read(SECRET_SERVICE)
    if not api_key or not api_secret:
        return None
    return Credentials(api_key=api_key, api_secret=api_secret)


def credential_env(credentials: Credentials) -> dict[str, str]:
    env = os.environ.copy()
    env["ALPACA_PAPER_TRADING_API_KEY"] = credentials.api_key
    env["ALPACA_PAPER_TRADING_API_SECRET"] = credentials.api_secret
    return env


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify both entries exist")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    credentials = load_credentials()
    if credentials is None:
        print(
            "error: Alpaca paper credentials are incomplete in macOS Keychain",
            file=sys.stderr,
        )
        return 2

    if args.check:
        if args.command:
            print("error: --check does not accept a command", file=sys.stderr)
            return 2
        print(
            "alpaca_keychain=ready account=paper "
            f"api_key_length={len(credentials.api_key)} "
            f"api_secret_length={len(credentials.api_secret)}"
        )
        return 0

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("error: provide --check or a command after --", file=sys.stderr)
        return 2

    completed = subprocess.run(  # nosec B603 - user-selected local command, no shell
        command, env=credential_env(credentials), check=False
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
