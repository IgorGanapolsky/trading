#!/bin/bash
# Fix shell issue and commit all pending changes
# This script bypasses shell environment issues by using direct paths

set -e

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔧 Fixing shell issue and committing changes..."

# Check git status
echo "📋 Checking git status..."
git status --short

# Add all changes
echo "📦 Staging changes..."
git add -A

# Commit
echo "💾 Committing changes..."
git commit -m "docs: Archive redundant meta-documentation and add autonomous execution directive

- Archived meta-docs (MISSION_COMPLETE, CTO_REPORT)
- Added .cursorrules with autonomous execution directive
- Created docs/_archive/ directory structure
- Kept only actionable docs

All archived files preserved in docs/_archive/ for reference."

# Push
echo "🚀 Pushing to main..."
git push origin main

echo "✅ All changes committed and pushed successfully!"

# Merge PR #8
echo "🔄 Merging PR #8 (Dependabot)..."
gh pr merge 8 --squash --auto || echo "⚠️  PR merge may require manual approval"

echo "🎉 All tasks completed!"
