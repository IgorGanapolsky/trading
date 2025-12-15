#!/bin/bash
# .claude/hooks/capture_session_learnings.sh
# Lightweight "Magic Docs" - captures learnings to RAG without editing CLAUDE.md
#
# Created: December 15, 2025
# Purpose: Capture substantial session learnings to lessons_learned directory
#
# Usage: This hook analyzes the session context and suggests learnings to capture
# Trigger: Manual via slash command or PostToolUse (filtered)

set -e

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

LESSONS_DIR="${CLAUDE_PROJECT_DIR}/rag_knowledge/lessons_learned"
TODAY=$(date +%Y-%m-%d)
MONTH_DAY=$(date +%b%d | tr '[:upper:]' '[:lower:]')

# Get next lesson number
get_next_lesson_number() {
    local max_num=0
    for file in "$LESSONS_DIR"/ll_*.md; do
        if [[ -f "$file" ]]; then
            num=$(basename "$file" | grep -oP 'll_\K\d+' | head -1)
            # Force base 10 to avoid octal interpretation of leading zeros
            if [[ -n "$num" ]]; then
                num=$((10#$num))
                if [[ "$num" -gt "$max_num" ]]; then
                    max_num=$num
                fi
            fi
        fi
    done
    echo $((max_num + 1))
}

# Check if this is a learning-worthy session (based on tool input)
TOOL_INPUT="${TOOL_INPUT:-}"

# Keywords that suggest a learning occurred
LEARNING_KEYWORDS=(
    "bug"
    "fix"
    "error"
    "mistake"
    "learned"
    "discovery"
    "gotcha"
    "pitfall"
    "workaround"
    "best practice"
    "antipattern"
    "should have"
    "next time"
    "remember"
    "important"
    "critical"
)

# Check if conversation contains learning indicators
contains_learning() {
    local input="$1"
    for keyword in "${LEARNING_KEYWORDS[@]}"; do
        if echo "$input" | grep -qi "$keyword"; then
            return 0
        fi
    done
    return 1
}

# Generate lesson template
generate_lesson_template() {
    local lesson_num=$1
    local title=$2
    local category=$3

    cat << EOF
# Lesson Learned: ${title}

**ID**: LL_$(printf "%03d" $lesson_num)
**Date**: ${TODAY}
**Severity**: MEDIUM
**Category**: ${category}
**Tags**: auto-captured, session-learning

## Incident Summary

[Describe what happened]

## Root Cause

[Why did this happen?]

## Impact

[What was the consequence?]

## Prevention Measures

[How to prevent this in the future]

## Detection Method

Auto-captured via session learning hook.

## Related Lessons

[Link to related lessons if any]
EOF
}

# Main execution
main() {
    # Ensure lessons directory exists
    mkdir -p "$LESSONS_DIR"

    NEXT_NUM=$(get_next_lesson_number)

    # Output suggestion for Claude to capture learning
    echo -e "${CYAN}💡 LESSONS CAPTURE READY${NC}"
    echo -e "Next lesson number: ${GREEN}LL_$(printf "%03d" $NEXT_NUM)${NC}"
    echo -e "Directory: ${BLUE}${LESSONS_DIR}${NC}"
    echo ""
    echo -e "${YELLOW}To capture a learning, create:${NC}"
    echo -e "  ${LESSONS_DIR}/ll_$(printf "%03d" $NEXT_NUM)_[topic]_${MONTH_DAY}.md"
    echo ""
    echo -e "Template fields:"
    echo -e "  - ID, Date, Severity, Category, Tags"
    echo -e "  - Incident Summary, Root Cause, Impact"
    echo -e "  - Prevention Measures, Detection Method"
    echo ""

    # If there's tool input, check for learning keywords
    if [[ -n "$TOOL_INPUT" ]]; then
        if contains_learning "$TOOL_INPUT"; then
            echo -e "${GREEN}✨ Learning indicators detected in session${NC}"
            echo -e "Consider capturing this insight!"
        fi
    fi
}

main "$@"
