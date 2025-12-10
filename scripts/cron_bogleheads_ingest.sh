#!/bin/bash
# Cron wrapper script for Bogleheads forum ingestion
# Runs daily to collect forum insights and ingest into RAG

set -euo pipefail

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Log file
LOG_FILE="$PROJECT_ROOT/logs/cron_bogleheads.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Log start
echo "[$TIMESTAMP] Starting Bogleheads forum ingestion..." >> "$LOG_FILE"

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the ingestion script
python3 scripts/bogleheads_ingest_once.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] ✅ Bogleheads ingestion completed successfully" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP] ❌ Bogleheads ingestion failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

exit $EXIT_CODE
