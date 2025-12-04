#!/bin/bash
# Initialize GitHub Wiki for trading repository
# This script creates the wiki repository and initial pages

set -e

echo "📝 Initializing GitHub Wiki..."

# Generate latest dashboard
cd "$(dirname "$0")/.."
python3 scripts/generate_progress_dashboard.py

# Create temp directory for wiki
WIKI_TEMP=$(mktemp -d)
cd "$WIKI_TEMP"

echo "🔧 Setting up wiki repository..."
git init
git config user.name "GitHub Actions Bot"
git config user.email "actions@github.com"

# Copy wiki files (use PROJECT_ROOT from earlier in script)
SCRIPT_DIR_ORIG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT_ORIG="$(cd "$SCRIPT_DIR_ORIG/.." && pwd)"
cp "$PROJECT_ROOT_ORIG/wiki/Home.md" .
cp "$PROJECT_ROOT_ORIG/wiki/Progress-Dashboard.md" .

# Commit
git add -A
git commit -m "Initial wiki: Progress Dashboard and Home page

- Added comprehensive progress dashboard
- Added wiki home page with quick links
- Dashboard auto-updates daily via GitHub Actions"

# Set remote
git remote add origin https://github.com/IgorGanapolsky/trading.wiki.git
git branch -M main

# Try to push - this will create the wiki repo if it doesn't exist
echo "📤 Pushing to wiki repository..."
if git push -u origin main 2>&1; then
    echo "✅ Wiki initialized successfully!"
    echo "🌐 View at: https://github.com/IgorGanapolsky/trading/wiki"
else
    echo "⚠️  Wiki repository may need to be created manually"
    echo "   1. Visit: https://github.com/IgorGanapolsky/trading/wiki"
    echo "   2. Click 'Create the first page'"
    echo "   3. Name it 'Home' and paste the content from wiki/Home.md"
    echo "   4. Save, then run this script again"
    echo ""
    echo "   Or manually push from: $WIKI_TEMP"
    exit 1
fi

echo "✅ Wiki setup complete!"
