"""
Output Sanitization Layer (Anti-Injection)

Sanitizes all MCP responses before returning to client.
Prevents prompt injection attacks via response manipulation.
"""

from __future__ import annotations

import re
from typing import Any

# Patterns that indicate potential prompt injection attempts
INJECTION_PATTERNS = [
    r"<\|.*?\|>",  # Special tokens
    r"\[INST\].*?\[/INST\]",  # Instruction markers
    r"<<SYS>>.*?<</SYS>>",  # System markers
    r"Human:|Assistant:|System:",  # Role markers
    r"ignore previous|disregard|forget.*instructions",  # Override attempts
    r"you are now|act as|pretend to be",  # Role hijacking
    r"execute.*command|run.*script|eval\(",  # Code execution
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]

# Sensitive fields to redact from responses
SENSITIVE_FIELDS = frozenset({
    "api_key",
    "api_secret",
    "password",
    "token",
    "secret",
    "credentials",
    "authorization",
})


def _contains_injection(text: str) -> bool:
    """Check if text contains potential injection patterns."""
    return any(pattern.search(text) for pattern in COMPILED_PATTERNS)


def _sanitize_string(value: str) -> str:
    """Sanitize a string value."""
    if _contains_injection(value):
        return "[SANITIZED: potential injection detected]"
    # Truncate excessively long strings (resource exhaustion prevention)
    max_length = 10000
    if len(value) > max_length:
        return value[:max_length] + "... [TRUNCATED]"
    return value


def _redact_sensitive(key: str, value: Any) -> Any:
    """Redact sensitive field values."""
    if key.lower() in SENSITIVE_FIELDS:
        return "[REDACTED]"
    return value


def sanitize_response(response: dict[str, Any] | list | Any) -> dict[str, Any] | list | Any:
    """
    Sanitize MCP response data.

    - Detects and neutralizes prompt injection attempts
    - Redacts sensitive fields (API keys, secrets)
    - Truncates excessively long responses

    Args:
        response: Raw response from MCP server

    Returns:
        Sanitized response safe to return to client
    """
    if response is None:
        return None

    if isinstance(response, str):
        return _sanitize_string(response)

    if isinstance(response, (int, float, bool)):
        return response

    if isinstance(response, list):
        return [sanitize_response(item) for item in response]

    if isinstance(response, dict):
        sanitized = {}
        for key, value in response.items():
            # Redact sensitive fields
            value = _redact_sensitive(key, value)
            # Recursively sanitize
            sanitized[key] = sanitize_response(value)
        return sanitized

    # Unknown type - convert to string and sanitize
    return _sanitize_string(str(response))
