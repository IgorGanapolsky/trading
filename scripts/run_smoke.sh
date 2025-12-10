#!/usr/bin/env bash
set -euo pipefail
# Usage: scripts/run_smoke.sh <fixture-path> <seed> <out-json>

# Resolve absolute paths
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

FIXTURE=${1:-tests/fixtures/fixture.csv}
SEED=${2:-42}
OUT=${3:-/tmp/smoke_out.json}

# Ensure python path includes repo root
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

if [ ! -f "$FIXTURE" ]; then
    echo "Error: Fixture file not found: $FIXTURE"
    exit 1
fi

echo "Running smoke backtest with fixture=$FIXTURE seed=$SEED out=$OUT..."

# Ensure output directory exists
mkdir -p "$(dirname "$OUT")"

python3 - <<PY
import sys
import json
import os
try:
    from src.trading.backtest import run_backtest
    fixture = "$FIXTURE"
    if not os.path.exists(fixture):
        print(f"Fixture not found (python): {fixture}", file=sys.stderr)
        sys.exit(1)

    pnl = run_backtest(fixture_csv=fixture, seed=int("$SEED"))

    with open("$OUT", "w") as f:
        json.dump({"pnl": pnl}, f)
    print(f"SMOKE_PNL={pnl}")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
PY
