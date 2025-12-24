"""
MCP client utilities and shared resource factories.

This module serves two purposes:
1. Provide a lightweight wrapper around MCP-compatible CLIs (for legacy usage).
2. Expose cached factories for high-cost resources (OpenRouter analyzers,
   Alpaca traders) so MCP code can load them once per execution run as
   recommended by Anthropic's code-execution workflow.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Any

from src.core.alpaca_trader import AlpacaTrader, AlpacaTraderError

# MultiLLMAnalyzer was removed - file no longer exists
# OpenRouter sentiment functions will return None
try:
    from src.core.multi_llm_analysis import MultiLLMAnalyzer
    MULTI_LLM_AVAILABLE = True
except ImportError:
    MultiLLMAnalyzer = None  # type: ignore
    MULTI_LLM_AVAILABLE = False

DEFAULT_CLI_BIN = os.environ.get("MCP_CLI_BIN", "claude")
DEFAULT_PROFILE = os.environ.get("MCP_PROFILE")

_DEFAULT_CLIENT_LOCK = Lock()
_DEFAULT_CLIENT: MCPClient | None = None


class MCPError(RuntimeError):
    """Raised when an MCP tool invocation fails."""


@dataclass
class MCPClient:
    """
    Simple shell-based MCP client.
    """

    cli_bin: str = DEFAULT_CLI_BIN
    profile: str | None = DEFAULT_PROFILE
    env: dict[str, str] | None = None

    def call_tool(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        *,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Invoke an MCP tool via the CLI and return parsed JSON.
        """

        cmd = [self.cli_bin, "mcp", "run", server, tool]
        if self.profile:
            cmd.extend(["--profile", self.profile])

        try:
            process = subprocess.run(
                cmd,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env=self._build_env(),
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MCPError(
                f"MCP CLI binary '{self.cli_bin}' not found. "
                "Set MCP_CLI_BIN to the correct executable."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise MCPError(
                f"MCP tool '{server}:{tool}' timed out after {timeout} seconds."
            ) from exc

        if process.returncode != 0:
            raise MCPError(
                "\n".join(
                    [
                        f"MCP tool '{server}:{tool}' failed (exit {process.returncode}).",
                        "STDOUT:",
                        process.stdout or "<empty>",
                        "STDERR:",
                        process.stderr or "<empty>",
                    ]
                )
            )

        stdout = process.stdout.strip()
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise MCPError(
                f"MCP tool '{server}:{tool}' returned non-JSON output: {stdout}"
            ) from exc

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self.env:
            env.update(self.env)
        return env


def default_client() -> MCPClient:
    """
    Return a singleton MCPClient configured from environment variables.
    """

    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        with _DEFAULT_CLIENT_LOCK:
            if _DEFAULT_CLIENT is None:
                _DEFAULT_CLIENT = MCPClient()
    return _DEFAULT_CLIENT


@lru_cache(maxsize=4)
def get_multi_llm_analyzer(use_async: bool = True) -> Any:
    """
    Return a cached MultiLLMAnalyzer instance.

    Returns None if MultiLLMAnalyzer is not available (file was removed).
    """
    if not MULTI_LLM_AVAILABLE or MultiLLMAnalyzer is None:
        return None
    return MultiLLMAnalyzer(use_async=use_async)


@lru_cache(maxsize=2)
def get_alpaca_trader(paper: bool = True) -> AlpacaTrader:
    """
    Return a cached AlpacaTrader instance.
    """

    try:
        return AlpacaTrader(paper=paper)
    except AlpacaTraderError:
        get_alpaca_trader.cache_clear()  # type: ignore[attr-defined]
        raise
