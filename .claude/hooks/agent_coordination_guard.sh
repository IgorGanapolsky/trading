#!/usr/bin/env bash
# Claude hook entrypoint for the repository-level coordination guard.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

exec bash "${PROJECT_ROOT}/scripts/agent_coordination_guard.sh" "${1-}"
