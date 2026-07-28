"""Registry↔module contract evals for every MCP server.

Incident source (2026-07): mcp/registry.json declared servers whose modules
did not exist on disk; the mercury-only drift guard (test_mercury_mcp.py)
could not see it. This eval walks the whole registry: every module-backed
server must import and expose every declared tool, so registry edits and
server refactors cannot drift apart silently.
"""

from __future__ import annotations

import importlib

from mcp.registry import load_registry


def test_every_module_backed_server_imports_and_exposes_tools():
    registry = load_registry()
    assert registry.servers, "registry unexpectedly empty"
    problems: list[str] = []
    for server in registry.servers.values():
        if server.module is None:
            continue
        try:
            module = importlib.import_module(server.module)
        except Exception as exc:  # noqa: BLE001 - collected for one readable report
            problems.append(f"{server.id}: module {server.module} failed to import ({exc})")
            continue
        for tool_name, function_name in server.tools.items():
            if not callable(getattr(module, function_name, None)):
                problems.append(
                    f"{server.id}: tool '{tool_name}' -> missing function "
                    f"{server.module}.{function_name}"
                )
    assert not problems, "registry/module drift:\n" + "\n".join(problems)


def test_http_servers_declare_endpoints():
    registry = load_registry()
    for server in registry.servers.values():
        if server.transport == "http":
            assert server.endpoint, f"{server.id}: http transport without endpoint"
