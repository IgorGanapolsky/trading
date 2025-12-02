from __future__ import annotations

from typing import Any

from mcp.client import MCPClient, default_client

SERVER_ID = "mcp-trader"


def _client(client: MCPClient | None) -> MCPClient:
    return client or default_client()


def analyze_stock(
    *,
    symbol: str,
    lookback_days: int = 60,
    client: MCPClient | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = {
        "symbol": symbol,
        "lookback_days": lookback_days,
        **kwargs,
    }
    return _client(client).call_tool(SERVER_ID, "analyze_stock", payload)


def relative_strength(
    *,
    symbol: str,
    benchmark: str = "SPY",
    lookback_days: int = 60,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {
        "symbol": symbol,
        "benchmark": benchmark,
        "lookback_days": lookback_days,
    }
    return _client(client).call_tool(SERVER_ID, "relative_strength", payload)


def position_size(
    *,
    symbol: str,
    entry_price: float,
    stop_loss: float,
    risk_dollars: float,
    client: MCPClient | None = None,
) -> dict[str, Any]:
    payload = {
        "symbol": symbol,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_dollars": risk_dollars,
    }
    return _client(client).call_tool(SERVER_ID, "position_size", payload)
