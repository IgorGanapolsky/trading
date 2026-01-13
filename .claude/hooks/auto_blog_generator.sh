#!/bin/bash
# Auto-generate blog posts from daily activity
# Runs on SessionStart to capture learnings

cd /home/user/trading

# Only run if we have commits today
TODAY=$(date +%Y-%m-%d)
COMMITS_TODAY=$(git log --oneline --since="$TODAY 00:00:00" --until="$TODAY 23:59:59" 2>/dev/null | wc -l)

if [ "$COMMITS_TODAY" -gt 5 ]; then
    # Check for significant events not yet blogged
    RULE1_COMMITS=$(git log --oneline --since="$TODAY 00:00:00" --grep="Rule #1\|rule_1\|EMERGENCY" 2>/dev/null | wc -l)
    RULE1_POSTS=$(ls docs/_posts/${TODAY}*rule*.md 2>/dev/null | wc -l)

    if [ "$RULE1_COMMITS" -gt 0 ] && [ "$RULE1_POSTS" -eq 0 ]; then
        echo "📝 BLOG REMINDER: $RULE1_COMMITS significant commits today not yet blogged"
        echo "   Run: python3 scripts/auto_blog_post.py"
    fi
fi
