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


# =============================================================================
# UNIFIED MCP ABSTRACTION (Technical Debt Fix - Jan 2026)
# =============================================================================
# Consolidates 5 different MCP patterns into one clean interface:
# - Pattern 1: Direct cached factory (AlpacaTrader)
# - Pattern 2: MCPClient.call_tool() (shell-based)
# - Pattern 3: Async/sync wrapper (MultiLLMAnalyzer)
# - Pattern 4: Subprocess CLI (Playwright)
# - Pattern 5: High-level orchestrator imports
# =============================================================================

import asyncio
import logging
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MCPTransport(Enum):
    """Supported MCP transport mechanisms."""

    DIRECT = "direct"  # Direct Python instance (cached)
    SHELL = "shell"  # Subprocess via CLI
    HTTP = "http"  # HTTP endpoint
    ASYNC = "async"  # Async with sync wrapper


@dataclass
class MCPToolResult:
    """Standardized result from any MCP tool call."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    transport: MCPTransport | None = None
    latency_ms: float = 0.0

    def raise_on_error(self) -> None:
        """Raise MCPError if the call failed."""
        if not self.success:
            raise MCPError(self.error or "Unknown MCP error")


def run_sync(coro: Any) -> Any:
    """
    Run an async coroutine synchronously.

    Handles event loop detection for nested calls.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already in async context - use nest_asyncio or thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class UnifiedMCPClient:
    """
    Unified MCP client providing consistent interface across all transports.

    Usage:
        client = UnifiedMCPClient()

        # Direct resource access (cached)
        trader = client.get_resource("alpaca", paper=True)

        # Tool call (auto-detects transport)
        result = client.call("alpaca", "get_positions", {})

        # Async tool call
        result = await client.call_async("openrouter", "sentiment", {...})
    """

    def __init__(self) -> None:
        self._shell_client = default_client()
        self._resource_cache: dict[str, Any] = {}

    def get_resource(
        self,
        resource_type: str,
        **kwargs: Any,
    ) -> Any:
        """
        Get a cached resource instance.

        Args:
            resource_type: Type of resource ("alpaca", "multi_llm", etc.)
            **kwargs: Resource-specific arguments

        Returns:
            Cached resource instance
        """
        cache_key = f"{resource_type}:{hash(frozenset(kwargs.items()))}"

        if cache_key in self._resource_cache:
            return self._resource_cache[cache_key]

        if resource_type == "alpaca":
            resource = get_alpaca_trader(paper=kwargs.get("paper", True))
        elif resource_type == "multi_llm":
            resource = get_multi_llm_analyzer(use_async=kwargs.get("use_async", True))
        else:
            raise MCPError(f"Unknown resource type: {resource_type}")

        self._resource_cache[cache_key] = resource
        return resource

    def call(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        *,
        timeout: int = 120,
        transport: MCPTransport | None = None,
    ) -> MCPToolResult:
        """
        Call an MCP tool with automatic transport detection.

        Args:
            server: MCP server ID
            tool: Tool name
            payload: Tool arguments
            timeout: Timeout in seconds
            transport: Force specific transport (auto-detect if None)

        Returns:
            MCPToolResult with standardized response
        """
        import time

        start = time.perf_counter()

        try:
            # Auto-detect transport
            if transport is None:
                transport = self._detect_transport(server)

            if transport == MCPTransport.DIRECT:
                data = self._call_direct(server, tool, payload)
            elif transport == MCPTransport.SHELL:
                data = self._shell_client.call_tool(server, tool, payload, timeout=timeout)
            elif transport == MCPTransport.HTTP:
                data = self._call_http(server, tool, payload, timeout)
            else:
                data = run_sync(self._call_async_impl(server, tool, payload))

            latency = (time.perf_counter() - start) * 1000
            return MCPToolResult(
                success=True, data=data, transport=transport, latency_ms=latency
            )

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            logger.error(f"MCP call failed [{server}:{tool}]: {e}")
            return MCPToolResult(
                success=False,
                error=str(e),
                transport=transport,
                latency_ms=latency,
            )

    async def call_async(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        *,
        timeout: int = 120,
    ) -> MCPToolResult:
        """Async version of call()."""
        import time

        start = time.perf_counter()

        try:
            data = await self._call_async_impl(server, tool, payload)
            latency = (time.perf_counter() - start) * 1000
            return MCPToolResult(
                success=True,
                data=data,
                transport=MCPTransport.ASYNC,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            logger.error(f"MCP async call failed [{server}:{tool}]: {e}")
            return MCPToolResult(
                success=False,
                error=str(e),
                transport=MCPTransport.ASYNC,
                latency_ms=latency,
            )

    def _detect_transport(self, server: str) -> MCPTransport:
        """Detect the appropriate transport for a server."""
        # Direct resources
        if server in ("alpaca", "openrouter", "multi_llm"):
            return MCPTransport.DIRECT
        # HTTP servers (Alpaca MCP on port 8801)
        if server == "alpaca-mcp":
            return MCPTransport.HTTP
        # Default to shell
        return MCPTransport.SHELL

    def _call_direct(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a direct resource method."""
        if server == "alpaca":
            trader = self.get_resource("alpaca", paper=payload.get("paper", True))
            method = getattr(trader, tool, None)
            if method is None:
                raise MCPError(f"Unknown Alpaca tool: {tool}")
            # Remove 'paper' from payload as it's handled by resource
            call_payload = {k: v for k, v in payload.items() if k != "paper"}
            return method(**call_payload) if call_payload else method()

        raise MCPError(f"No direct handler for server: {server}")

    def _call_http(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        """Call an HTTP-based MCP server."""
        import urllib.request
        import urllib.error

        # Server endpoint mapping
        endpoints = {
            "alpaca-mcp": "http://127.0.0.1:8801",
        }

        base_url = endpoints.get(server)
        if not base_url:
            raise MCPError(f"Unknown HTTP server: {server}")

        url = f"{base_url}/tools/{tool}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise MCPError(f"HTTP call to {server} failed: {e}") from e

    async def _call_async_impl(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Internal async implementation."""
        # For async servers like Playwright, implement specific handlers
        if server == "playwright":
            # Import lazily to avoid circular deps
            try:
                from src.integrations.playwright_mcp.client import get_playwright_client

                client = get_playwright_client()
                method = getattr(client, tool, None)
                if method:
                    result = await method(**payload)
                    return result if isinstance(result, dict) else {"result": result}
            except ImportError:
                raise MCPError("Playwright MCP not available")

        # Fallback to sync shell call in thread
        return await asyncio.to_thread(
            self._shell_client.call_tool, server, tool, payload
        )


# Singleton unified client
_unified_client: UnifiedMCPClient | None = None
_unified_client_lock = Lock()


def get_unified_client() -> UnifiedMCPClient:
    """Get or create the singleton UnifiedMCPClient."""
    global _unified_client
    if _unified_client is None:
        with _unified_client_lock:
            if _unified_client is None:
                _unified_client = UnifiedMCPClient()
    return _unified_client
