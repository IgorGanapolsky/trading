#!/bin/bash
# Harbor Evals Runner - Execute golden scenarios for trade execution evals
# Usage: ./run_evals.sh [scenario_name] -- or run all scenarios

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════════"
echo "  Harbor Evals Runner: Trade Execution Validation"
echo "═══════════════════════════════════════════════════════"
echo ""

# Load Python environment from parent repo
if [ -f "$SCRIPT_DIR/../../../../.venv/bin/activate" ]; then
	source "$SCRIPT_DIR/../../../../.venv/bin/activate" || true
else
	echo "Warning: Parent .venv not found, using system Python"
fi

# Run selected scenario or all scenarios
if [ -n "${1-}" ]; then
	SCENARIO_NAME="$1"
	echo "Running scenario: $SCENARIO_NAME"

	python "$SCRIPT_DIR/run_scenarios.py" --scenario "$SCENARIO_NAME" --verbose
else
	echo "Running all golden scenarios..."
	python "$SCRIPT_DIR/run_scenarios.py" --all --verbose

	# Generate Harbor report
	if [ -f "$SCRIPT_DIR/report.json" ]; then
		echo ""
		echo "═══════════════════════════════════════════════════════"
		echo "  Harbor Report: $SCRIPT_DIR/report.json"
		cat "$SCRIPT_DIR/report.json" | python -m json.tool 2>/dev/null || true
		echo "═══════════════════════════════════════════════════════"
	fi

fi

echo ""
echo "Evals completed. Check reports/ for detailed trajectories."
