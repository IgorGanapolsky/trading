"""
Registry loader for MCP server metadata.

The registry is stored in JSON (`mcp/registry.json`) so that CI and other tools
can diff schema changes without importing Python modules.  Runtime helpers load
the registry, validate important fields, and expose simple data objects to the
rest of the harness.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REGISTRY_FILENAME = "registry.json"
REGISTRY_PATH = Path(__file__).with_name(REGISTRY_FILENAME)


@dataclass(frozen=True)
class MCPServer:
    """Represents a configured MCP server."""

    id: str
    display_name: str
    module: str | None
    tools: dict[str, str]
    transport: str | None = None
    endpoint: str | None = None

    def tool_names(self) -> Iterable[str]:
        return self.tools.keys()


@dataclass
class MCPRegistry:
    """In-memory representation of the MCP registry."""

    servers: dict[str, MCPServer]
    generated_at: str | None = None

    def get(self, server_id: str) -> MCPServer:
        try:
            return self.servers[server_id]
        except KeyError as exc:
            raise KeyError(f"Unknown MCP server '{server_id}'.") from exc

    def __contains__(self, server_id: str) -> bool:
        return server_id in self.servers


def load_registry(path: os.PathLike | None = None) -> MCPRegistry:
    """
    Load the registry from disk.

    Args:
        path: Optional override for the registry path. When omitted, the default
              `mcp/registry.json` is used.

    Returns:
        MCPRegistry instance populated with server metadata.
    """
    registry_path = Path(path or REGISTRY_PATH)
    if not registry_path.exists():
        raise FileNotFoundError(f"MCP registry not found at {registry_path}")

    with registry_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    raw_servers = raw.get("servers", [])
    servers: dict[str, MCPServer] = {}

    for entry in raw_servers:
        server_id = entry["id"]
        module = entry.get("module")
        transport = entry.get("transport")
        endpoint = entry.get("endpoint")

        if module is None and transport is None:
            raise ValueError(f"MCP server '{server_id}' is missing both 'module' and 'transport'.")
        if transport == "http" and not endpoint:
            raise ValueError(f"MCP server '{server_id}' declares HTTP transport but no endpoint.")

        servers[server_id] = MCPServer(
            id=server_id,
            display_name=entry.get("display_name", server_id),
            module=module,
            tools=entry.get("tools", {}),
            transport=transport,
            endpoint=endpoint,
        )

    return MCPRegistry(
        servers=servers,
        generated_at=raw.get("generated_at"),
    )
