#!/bin/bash
# Initialization script for trading system environment
# This script sets up the environment and runs basic verification tests
# Agents should run this at the start of each session to verify the system is working

set -e

echo "🚀 Initializing Trading System Environment..."
echo ""

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $(pwd)"
echo ""

# Check Python environment
echo "🐍 Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: python3 not found"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "✅ Python: $PYTHON_VERSION"
echo ""

# Check virtual environment
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Warning: No venv directory found. Using system Python."
fi
echo ""

# Check required environment variables
echo "🔐 Checking environment variables..."
MISSING_VARS=0

if [ -z "$ALPACA_API_KEY" ]; then
    echo "⚠️  Warning: ALPACA_API_KEY not set"
    MISSING_VARS=$((MISSING_VARS + 1))
else
    echo "✅ ALPACA_API_KEY set"
fi

if [ -z "$ALPACA_SECRET_KEY" ]; then
    echo "⚠️  Warning: ALPACA_SECRET_KEY not set"
    MISSING_VARS=$((MISSING_VARS + 1))
else
    echo "✅ ALPACA_SECRET_KEY set"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  Warning: ANTHROPIC_API_KEY not set"
    MISSING_VARS=$((MISSING_VARS + 1))
else
    echo "✅ ANTHROPIC_API_KEY set"
fi

echo ""

# Check system state file
echo "📊 Checking system state..."
if [ -f "data/system_state.json" ]; then
    echo "✅ system_state.json exists"

    # Check if state is stale
    if command -v python3 &> /dev/null; then
        python3 -c "
import json
from datetime import datetime
from pathlib import Path

state_file = Path('data/system_state.json')
if state_file.exists():
    state = json.loads(state_file.read_text())
    last_updated = datetime.fromisoformat(state['meta']['last_updated'])
    hours_old = (datetime.now() - last_updated).total_seconds() / 3600
    if hours_old > 72:
        print(f'⚠️  Warning: State is {hours_old/24:.1f} days old')
    else:
        print(f'✅ State is {hours_old:.1f} hours old')
" || echo "⚠️  Could not check state freshness"
    fi
else
    echo "⚠️  Warning: system_state.json not found (will be created on first run)"
fi
echo ""

# Run basic health check if available
if [ -f "scripts/pre_market_health_check.py" ]; then
    echo "🏥 Running pre-market health check..."
    python3 scripts/pre_market_health_check.py || {
        echo "⚠️  Health check had warnings (this is OK for development)"
    }
    echo ""
fi

# Auto-download missing Berkshire letters (network permitting)
if [ -f "scripts/auto_download_berkshire.py" ]; then
    echo "📚 Checking Berkshire letter collection..."
    python3 scripts/auto_download_berkshire.py 2>/dev/null || {
        echo "⚠️  Could not check Berkshire letters (network may be restricted)"
    }
    echo ""
fi

# Check git status
echo "📝 Checking git status..."
if command -v git &> /dev/null; then
    git status --short || echo "⚠️  Not a git repository or git not available"
    echo ""

    echo "📜 Recent commits:"
    git log --oneline -5 || echo "⚠️  Could not read git log"
else
    echo "⚠️  Git not available"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $MISSING_VARS -eq 0 ]; then
    echo "✅ Environment initialized successfully"
    echo ""
    echo "Next steps:"
    echo "1. Read claude-progress.txt to understand recent work"
    echo "2. Read feature_list.json to see feature status"
    echo "3. Choose ONE feature to work on"
    echo "4. Test end-to-end before marking feature complete"
else
    echo "⚠️  Environment initialized with $MISSING_VARS missing environment variable(s)"
    echo "   System may not function correctly without all API keys"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
