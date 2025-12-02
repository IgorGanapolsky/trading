from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

SERVER_ID = "options-order-flow"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def live_summary(
    *,
    symbols: list[str] | None = None,
    min_notional: float | None = None,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if symbols:
        payload["symbols"] = symbols
    if min_notional is not None:
        payload["min_notional"] = min_notional
    return _client(client).call_tool(SERVER_ID, "live_summary", payload)


def unusual_activity(
    *,
    symbol: str,
    lookback_minutes: int = 30,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {
        "symbol": symbol,
        "lookback_minutes": lookback_minutes,
    }
    return _client(client).call_tool(SERVER_ID, "unusual_activity", payload)


def flow_snapshot(
    *,
    symbol: str,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {"symbol": symbol}
    return _client(client).call_tool(SERVER_ID, "flow_snapshot", payload)
