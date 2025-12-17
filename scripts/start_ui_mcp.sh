#!/bin/bash
# Start the Trading Dashboard MCP Server
#
# This server exposes the component manifest to AI agents for consistent UI development.
#
# Usage:
#   ./scripts/start_ui_mcp.sh [port]
#
# After starting, configure Claude Code:
#   claude mcp add trading-ui --transport http http://localhost:8765/mcp --scope project

set -e

PORT=${1:-8765}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Trading Dashboard MCP Server on port $PORT..."
echo ""
echo "Configure Claude Code with:"
echo "  claude mcp add trading-ui --transport http http://localhost:$PORT/mcp --scope project"
echo ""

cd "$PROJECT_ROOT"
python dashboard/mcp_server.py --port "$PORT"
