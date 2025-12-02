from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mcp.client import MCPClient, default_client
from mcp.registry import load_registry


def _load_payload(payload_arg: str | None) -> dict[str, Any]:
    if not payload_arg:
        return {}

    candidate = Path(payload_arg)
    text = candidate.read_text(encoding="utf-8") if candidate.exists() else payload_arg

    return json.loads(text)


def _dump_output(result: dict[str, Any], output_path: str | None) -> None:
    serialized = json.dumps(result, indent=2)
    if output_path:
        Path(output_path).write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized + "\n")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute an MCP tool via the code-execution harness. "
            "Payloads can be provided inline JSON or as a path to a JSON file."
        )
    )
    parser.add_argument("server", help="MCP server identifier (e.g., trade-agent)")
    parser.add_argument("tool", help="Tool name defined on the server")
    parser.add_argument(
        "--payload",
        "-p",
        help="JSON payload or path to JSON file (defaults to empty object)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path to write the JSON response (defaults to stdout)",
    )
    parser.add_argument(
        "--client",
        help="Override CLI binary for MCP client (defaults to env `MCP_CLI_BIN`)",
    )
    parser.add_argument(
        "--profile",
        help="Override CLI profile (defaults to env `MCP_PROFILE`)",
    )

    args = parser.parse_args(argv)

    registry = load_registry()
    if args.server not in registry:
        parser.error(
            f"Unknown server '{args.server}'. Update mcp/registry.json if this is a new server."
        )

    payload = _load_payload(args.payload)

    client: MCPClient
    if args.client or args.profile:
        client = MCPClient(
            cli_bin=args.client or default_client().cli_bin,
            profile=args.profile or default_client().profile,
        )
    else:
        client = default_client()

    result = client.call_tool(args.server, args.tool, payload)
    _dump_output(result, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(run())
