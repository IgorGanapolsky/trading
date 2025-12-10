#!/bin/bash
set -e

BRANCH=$1
if [ -z "$BRANCH" ]; then
    echo "Usage: $0 <branch_name>"
    exit 1
fi

echo "========================================================"
echo "Processing $BRANCH"

# Check if worktree already exists for this branch
EXISTING_WT=$(git worktree list | grep "\[$BRANCH\]" | head -n 1 | awk '{print $1}')

if [ -n "$EXISTING_WT" ]; then
    WORKTREE="$EXISTING_WT"
    echo "Found existing worktree at $WORKTREE"
    cd "$WORKTREE"
    # Ensure it's clean and up to date
    git reset --hard
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    # Use tr instead of sed for safety
    SAFE_NAME=$(echo "$BRANCH" | tr '/' '-')
    WORKTREE="trading_worktrees/$SAFE_NAME"
    echo "Creating new worktree at $WORKTREE"
    git worktree add "$WORKTREE" "$BRANCH"
    cd "$WORKTREE"
fi

echo "========================================================"

# 1. Fix slots=True
echo "Fixing slots=True..."
find . -name "*.py" -print0 | xargs -0 sed -i '' 's/@dataclass(slots=True)/@dataclass/g'

# 2. Fix known unused variables
echo "Fixing unused variables..."
if [ -f "scripts/check_daily_health.py" ]; then
    sed -i '' '/system_state = load_system_state(data_dir)/d' scripts/check_daily_health.py || true
fi
if [ -f "src/backtesting/stress_testing.py" ]; then
     sed -i '' '/avg_drawdown = sum/d' src/backtesting/stress_testing.py || true
fi

# 3. Ruff Fixes
echo "Running Ruff..."
../../.venv/bin/ruff check --fix --unsafe-fixes . || true
../../.venv/bin/ruff format . || true

# 4. Fix Future Imports
echo "Fixing Future Imports..."
FILES_TO_FIX="src/backtesting/backtest_results.py src/rag/collectors/options_flow_collector.py src/backtesting/walk_forward_matrix.py src/rag/collectors/tradingview_collector.py src/backtesting/backtest_engine.py src/agents/execution_agent.py src/rag/vector_db/chroma_client.py src/strategies/treasury_ladder_strategy.py src/rag/collectors/earnings_whisper_collector.py src/rag/collectors/finviz_collector.py"

for f in $FILES_TO_FIX; do
    if [ -f "$f" ]; then
        if ! grep -q "from __future__ import annotations" "$f"; then
            echo "  Adding future import to $f"
            if [[ "$f" == *"backtest_results.py"* ]]; then
                 if grep -q "import json" "$f"; then
                    perl -i -pe 's/^import json/from __future__ import annotations\nimport json/' "$f"
                 else
                    perl -i -pe 'print "from __future__ import annotations\n" if $. == 1' "$f"
                 fi
            elif grep -q "import logging" "$f"; then
                 perl -i -pe 's/^import logging/from __future__ import annotations\nimport logging/' "$f"
            else
                 perl -i -pe 'print "from __future__ import annotations\n" if $. == 1' "$f"
            fi
        fi
    fi
done

# 5. Commit and Push
echo "Committing..."
if [ -n "$(git status --porcelain)" ]; then
    git add .
    git commit -m "fix: resolve linting errors and python 3.9 compatibility"
    echo "Pushing..."
    git push origin HEAD
else
    echo "No changes to commit."
fi

echo "Done with $BRANCH"
echo ""
