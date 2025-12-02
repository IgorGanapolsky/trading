from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

SERVER_ID = "metatrader"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def place_order(
    *,
    symbol: str,
    side: str,
    volume: float,
    order_type: str = "market",
    deviation: int | None = None,
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "order_type": order_type,
        **kwargs,
    }
    if deviation is not None:
        payload["deviation"] = deviation
    return _client(client).call_tool(SERVER_ID, "place_order", payload)


def get_open_positions(
    *,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    return _client(client).call_tool(SERVER_ID, "get_open_positions", {})


def get_indicator(
    *,
    symbol: str,
    indicator: str,
    timeframe: str = "H1",
    period: int | None = None,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "indicator": indicator,
        "timeframe": timeframe,
    }
    if period is not None:
        payload["period"] = period
    return _client(client).call_tool(SERVER_ID, "get_indicator", payload)
