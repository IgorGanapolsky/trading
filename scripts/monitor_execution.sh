#!/bin/bash
# Real-time monitoring of autonomous trading execution

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 TRADING SYSTEM EXECUTION MONITOR"
echo "===================================="
echo ""
echo "📅 Current Time: $(date)"
echo "🎯 Next Execution: 9:35 AM EST (Weekdays)"
echo ""

echo "📊 LaunchD Job Status:"
launchctl list | grep com.trading.autonomous || echo "⚠️  Job not loaded"
echo ""

echo "📁 Recent Log Files:"
ls -lht "$PROJECT_ROOT/logs/"*.log 2>/dev/null | head -5 || echo "No logs yet"
echo ""

echo "💬 Tailing logs (CTRL+C to exit)..."
echo "===================================="
tail -f "$PROJECT_ROOT/logs/workflow_stdout.log" \
        "$PROJECT_ROOT/logs/workflow_stderr.log" 2>/dev/null &

TAIL_PID=$!

# Wait for user interrupt
trap "kill $TAIL_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait $TAIL_PID
