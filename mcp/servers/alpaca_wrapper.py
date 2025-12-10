from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

# Official Alpaca MCP server id
SERVER_ID = "alpaca"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def submit_order(
    *,
    symbol: str,
    side: str,
    qty: float,
    order_type: str = "market",
    time_in_force: str = "day",
    extended_hours: bool = False,
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    # Map to official Alpaca MCP tool: submit_order(symbol, side, qty, type, time_in_force, extended_hours)
    payload = {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "type": order_type,
        "time_in_force": time_in_force,
        "extended_hours": extended_hours,
        **kwargs,
    }
    return _client(client).call_tool(SERVER_ID, "submit_order", payload)


def get_positions(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_all_positions", {})


def get_clock(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_clock", {})


def get_account(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_account_info", {})
