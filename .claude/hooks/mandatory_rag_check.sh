#!/bin/bash
#
# Mandatory RAG Check - Force Claude to see critical lessons before responding
#
# This hook runs on UserPromptSubmit and injects critical lessons
# that Claude MUST acknowledge before proceeding.
#

set -euo pipefail

LESSONS_DIR="${CLAUDE_PROJECT_DIR}/rag_knowledge/lessons_learned"

# Critical lessons that should always be visible
CRITICAL_LESSONS=(
    "ll_051_calendar"      # Calendar awareness
    "ll_052_no_crypto"     # No crypto trading
)

echo "═══════════════════════════════════════════════════════════"
echo "📚 MANDATORY RAG CHECK - Critical Lessons"
echo "═══════════════════════════════════════════════════════════"

for pattern in "${CRITICAL_LESSONS[@]}"; do
    file=$(find "$LESSONS_DIR" -name "*${pattern}*" -type f 2>/dev/null | head -1)
    if [[ -n "$file" && -f "$file" ]]; then
        # Extract just the title and key points
        title=$(grep -m1 "^# " "$file" 2>/dev/null | sed 's/^# //' || echo "Lesson")
        echo "⚠️  $title"
    fi
done

# Check for lesson staleness
check_lesson_staleness() {
    local latest_lesson=$(ls -t "$LESSONS_DIR"/ll_*.md 2>/dev/null | head -1)
    if [[ -n "$latest_lesson" ]]; then
        local lesson_date=$(stat -c %Y "$latest_lesson" 2>/dev/null || stat -f %m "$latest_lesson" 2>/dev/null)
        local now=$(date +%s)
        local age_hours=$(( (now - lesson_date) / 3600 ))

        if [[ $age_hours -gt 48 ]]; then
            echo ""
            echo "🔴 LESSON CAPTURE OVERDUE: Last lesson was ${age_hours} hours ago!"
            echo "   Use /capture-learning or /diary to document today's insights"
        fi
    fi
}

check_lesson_staleness

# Day-specific reminders
DAY_OF_WEEK=$(TZ=America/New_York date +%A)
case $DAY_OF_WEEK in
    Friday)
        echo ""
        echo "🔴 FRIDAY RULE: Tomorrow is SATURDAY. Say 'Monday' not 'tomorrow'."
        ;;
    Saturday|Sunday)
        echo ""
        echo "🔴 WEEKEND: Markets CLOSED. Next trading is MONDAY."
        ;;
esac

echo "═══════════════════════════════════════════════════════════"
