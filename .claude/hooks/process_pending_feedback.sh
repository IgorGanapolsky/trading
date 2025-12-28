#!/bin/bash
# Autonomous Feedback Learning Hook
# Runs on session start to process any pending user feedback
# Converts negative feedback to lessons, reinforces positive patterns
#
# Created: 2025-12-27
# Part of: Autonomous Feedback Learning System

set -euo pipefail

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

FEEDBACK_DIR="$CLAUDE_PROJECT_DIR/data/feedback"
PROCESSED_FILE="$FEEDBACK_DIR/processed_feedback.json"

# Check if there's any feedback to process
if [[ ! -d "$FEEDBACK_DIR" ]]; then
    exit 0
fi

# Count unprocessed feedback
TOTAL_FEEDBACK=0
PROCESSED_COUNT=0

# Count total feedback entries
shopt -s nullglob
for f in "$FEEDBACK_DIR"/feedback_*.jsonl; do
    if [[ -f "$f" ]]; then
        count=$(wc -l < "$f" | tr -d ' ')
        TOTAL_FEEDBACK=$((TOTAL_FEEDBACK + count))
    fi
done
shopt -u nullglob

# Get processed count
if [[ -f "$PROCESSED_FILE" ]]; then
    PROCESSED_COUNT=$(jq -r '.total_processed // 0' "$PROCESSED_FILE" 2>/dev/null || echo "0")
fi

PENDING=$((TOTAL_FEEDBACK - PROCESSED_COUNT))

# Only run if there's pending feedback
if [[ $PENDING -le 0 ]]; then
    exit 0
fi

echo -e "${CYAN}🧠 AUTONOMOUS FEEDBACK LEARNING${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "📬 Found ${YELLOW}$PENDING${NC} pending feedback entries to process"

# Run the Python feedback learner
cd "$CLAUDE_PROJECT_DIR"

# Use python3 to run the feedback learner
RESULT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from src.learning.feedback_learner import run_autonomous_learning
import json
result = run_autonomous_learning()
print(json.dumps(result))
" 2>/dev/null) || {
    echo -e "${YELLOW}⚠️  Feedback learning deferred (module not ready)${NC}"
    exit 0
}

# Parse results
LESSONS_CREATED=$(echo "$RESULT" | jq -r '.lessons_created // 0')
PATTERNS_REINFORCED=$(echo "$RESULT" | jq -r '.patterns_reinforced // 0')
ERRORS=$(echo "$RESULT" | jq -r '.errors // 0')

# Display results
if [[ $LESSONS_CREATED -gt 0 ]]; then
    echo -e "${RED}📚 Created $LESSONS_CREATED lesson(s) from negative feedback${NC}"
    echo -e "   ${YELLOW}→ Review new lessons and add specific prevention rules${NC}"
fi

if [[ $PATTERNS_REINFORCED -gt 0 ]]; then
    echo -e "${GREEN}💪 Reinforced $PATTERNS_REINFORCED positive pattern(s)${NC}"
fi

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}❌ $ERRORS error(s) during processing${NC}"
fi

# Show current satisfaction stats
SAT_RATE=$(echo "$RESULT" | jq -r '.stats.satisfaction_rate // 0')
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "📊 Overall Satisfaction: ${GREEN}${SAT_RATE}%${NC}"

# If any lessons were created from negative feedback, remind Claude
if [[ $LESSONS_CREATED -gt 0 ]]; then
    echo ""
    echo -e "${YELLOW}⚠️  ACTION REQUIRED: Ask user about recent negative feedback${NC}"
    echo -e "   'I noticed some negative feedback. What did I do wrong? I want to learn.'${NC}"
fi

exit 0
