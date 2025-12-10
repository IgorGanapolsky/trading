#!/bin/bash
# =============================================================================
# AI Trading Dashboard Launcher
# =============================================================================
# Run the world-class trading dashboard
#
# Usage: ./scripts/run_dashboard.sh [port]
#
# Default port: 8501
# =============================================================================

set -e

PORT=${1:-8501}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🎯 AI Trading Dashboard"
echo "========================"
echo ""
echo "Starting dashboard on port $PORT..."
echo "Open: http://localhost:$PORT"
echo ""

# Run streamlit
streamlit run dashboard/main.py \
    --server.port=$PORT \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --theme.base="dark" \
    --theme.primaryColor="#3fb950" \
    --theme.backgroundColor="#0d1117" \
    --theme.secondaryBackgroundColor="#161b22" \
    --theme.textColor="#f0f6fc"
