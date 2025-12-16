from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

SERVER_ID = "trade-agent"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def place_equity_order(
    *,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    time_in_force: str = "day",
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Place an equity order through the Trade Agent MCP server.

    Args:
        symbol: Ticker symbol (e.g. SPY).
        side: "buy" or "sell".
        quantity: Number of shares.
        order_type: Order type (market, limit, stop, etc.).
        time_in_force: Time in force (day, gtc, gtd).
        client: Optional MCPClient override.
        kwargs: Additional tool-specific overrides (e.g. limit_price).
    """
    payload = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "time_in_force": time_in_force,
        **kwargs,
    }
    return _client(client).call_tool(SERVER_ID, "place_equity_order", payload)


def cancel_order(
    *,
    order_id: str,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {"order_id": order_id}
    return _client(client).call_tool(SERVER_ID, "cancel_order", payload)


def get_positions(
    *,
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {**kwargs} if kwargs else {}
    return _client(client).call_tool(SERVER_ID, "get_positions", payload)


def get_account_overview(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_account_overview", {})
