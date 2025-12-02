from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

SERVER_ID = "tradovate"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def place_order(
    *,
    contract: str,
    side: str,
    quantity: int,
    order_type: str = "market",
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "contract": contract,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        **kwargs,
    }
    return _client(client).call_tool(SERVER_ID, "place_order", payload)


def get_positions(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_positions", {})


def get_contract_details(
    *,
    contract: str,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {"contract": contract}
    return _client(client).call_tool(SERVER_ID, "get_contract_details", payload)
