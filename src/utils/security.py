# ruff: noqa: UP045
"""
Security utilities for masking sensitive information in logs and output.

This module provides functions to safely mask API keys, secrets, and other
sensitive data to prevent accidental exposure in logs, print statements, or
error messages.
"""

import re


def mask_api_key(api_key: str | None, visible_chars: int = 4) -> str:
    """
    Mask an API key, showing only the first few characters.

    Args:
        api_key: The API key to mask (can be None)
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Masked API key string (e.g., "ABCD***" or "***" if None)

    Example:
        >>> mask_api_key("sk-1234567890abcdef")
        "sk-1***"
        >>> mask_api_key(None)
        "***"
    """
    if not api_key:
        return "***"

    if len(api_key) <= visible_chars:
        return "***"

    return f"{api_key[:visible_chars]}***"


def mask_secret(secret: str | None, visible_chars: int = 4) -> str:
    """
    Mask a secret key, showing only the first few characters.

    Args:
        secret: The secret to mask (can be None)
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Masked secret string (e.g., "ABCD***" or "***" if None)
    """
    return mask_api_key(secret, visible_chars)


def sanitize_log_message(message: str) -> str:
    """
    Sanitize a log message by masking any potential API keys or secrets.

    This function attempts to detect and mask common patterns of API keys
    and secrets in log messages.

    Args:
        message: The log message to sanitize

    Returns:
        Sanitized message with sensitive data masked
    """
    # Common API key patterns
    patterns = [
        (
            r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{10,})(["\']?)',
            r"\1***\3",
        ),
        (r'(secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{10,})(["\']?)', r"\1***\3"),
        (r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)', r"\1***\3"),
        (r'(token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})(["\']?)', r"\1***\3"),
    ]

    sanitized = message
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def is_sensitive_key(key_name: str) -> bool:
    """
    Check if a key name indicates sensitive information.

    Args:
        key_name: The name of the key/variable to check

    Returns:
        True if the key name suggests sensitive data
    """
    sensitive_patterns = [
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "secret_key",
        "secret-key",
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "credential",
        "cred",
    ]

    key_lower = key_name.lower()
    return any(pattern in key_lower for pattern in sensitive_patterns)
