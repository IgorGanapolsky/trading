#!/usr/bin/env python3
"""
Update Alpaca API secrets in GitHub.

This script must be run in GitHub Actions where nacl is available.
"""

import os
import sys
from base64 import b64decode, b64encode

import requests

try:
    from nacl import encoding, public
except ImportError:
    print("ERROR: nacl library not available. Run in GitHub Actions.")
    sys.exit(1)


def encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a secret using the repository's public key."""
    public_key_bytes = b64decode(public_key)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


def update_secret(repo: str, secret_name: str, secret_value: str, token: str) -> bool:
    """Update a GitHub Actions secret."""
    # Get the public key
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    key_response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )

    if key_response.status_code != 200:
        print(f"Failed to get public key: {key_response.text}")
        return False

    key_data = key_response.json()
    encrypted_value = encrypt_secret(key_data["key"], secret_value)

    # Update the secret
    update_response = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
    )

    if update_response.status_code in (201, 204):
        print(f"Updated secret: {secret_name}")
        return True
    else:
        print(f"Failed to update {secret_name}: {update_response.text}")
        return False


def main():
    """Update Alpaca API secrets."""
    repo = "IgorGanapolsky/trading"
    token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")

    if not token:
        print("ERROR: GH_PAT or GITHUB_TOKEN environment variable required")
        sys.exit(1)

    # Get credentials from environment
    api_key = os.environ.get("NEW_ALPACA_API_KEY")
    api_secret = os.environ.get("NEW_ALPACA_API_SECRET")

    if not api_key or not api_secret:
        print("ERROR: NEW_ALPACA_API_KEY and NEW_ALPACA_API_SECRET required")
        sys.exit(1)

    # Update both secrets
    success = True
    success &= update_secret(repo, "ALPACA_PAPER_TRADING_5K_API_KEY", api_key, token)
    success &= update_secret(
        repo, "ALPACA_PAPER_TRADING_5K_API_SECRET", api_secret, token
    )

    if success:
        print("\nAll secrets updated successfully!")
    else:
        print("\nSome secrets failed to update")
        sys.exit(1)


if __name__ == "__main__":
    main()
