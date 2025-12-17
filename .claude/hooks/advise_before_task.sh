#!/bin/bash
# .claude/hooks/advise_before_task.sh
# Auto-surfaces relevant lessons learned before starting tasks
# Based on Sionic AI's skill registry pattern

set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract prompt using jq
if command -v jq &> /dev/null; then
    PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')
else
    PROMPT=$(echo "$INPUT" | grep -o '"prompt":"[^"]*"' | cut -d'"' -f4 || echo "")
fi

# Exit if no prompt or too short
if [ -z "$PROMPT" ] || [ ${#PROMPT} -lt 15 ]; then
    exit 0
fi

# Convert to lowercase
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Skip questions and simple queries
if [[ "$PROMPT_LOWER" == *"what is"* ]] || \
   [[ "$PROMPT_LOWER" == *"how do"* ]] || \
   [[ "$PROMPT_LOWER" == *"explain"* ]] || \
   [[ "$PROMPT" == *"?"* && ${#PROMPT} -lt 50 ]]; then
    exit 0
fi

# Define keyword -> lesson mappings (high-value patterns)
declare -A KEYWORD_LESSONS=(
    ["backtest"]="ll_021_backtest ll_041_comprehensive"
    ["import"]="ll_011_missing_function"
    ["config"]="ll_033_config_enum ll_049_config_workflow"
    ["ci"]="ll_009_ci_syntax ci_failure_blocked"
    ["filter"]="ll_019_system_dead_2_days_overly_strict"
    ["trade"]="ll_020_pyramid ll_040_catching_falling ll_033_negative_momentum"
    ["verify"]="ll_033_comprehensive_verification ll_045_verification"
    ["dead"]="ll_010_dead_code ll_014_dead_code"
    ["test"]="ll_041_comprehensive_regression"
    ["api"]="ll_017_missing_langsmith"
    ["market"]="ll_018_weekend_market"
    ["option"]="ll_020_options_primary ll_022_options_not"
    ["commit"]="ll_020_trade_files_not_committed"
    ["rag"]="ll_035_failed_to_use_rag ll_017_rag_vectorization"
    ["hook"]="ll_autonomous_commands"
    ["budget"]="ll_025_bats_budget"
    ["risk"]="ll_016_regime_pivot_safety"
    ["hygiene"]="ll_042_code_hygiene ll_044_documentation"
)

LESSONS_DIR="${CLAUDE_PROJECT_DIR:-/home/user/trading}/rag_knowledge/lessons_learned"

# Find matching lessons
MATCHES=()
for keyword in "${!KEYWORD_LESSONS[@]}"; do
    if [[ "$PROMPT_LOWER" == *"$keyword"* ]]; then
        # Split lesson patterns and search
        IFS=' ' read -ra patterns <<< "${KEYWORD_LESSONS[$keyword]}"
        for pattern in "${patterns[@]}"; do
            found=$(ls "$LESSONS_DIR" 2>/dev/null | grep -i "$pattern" | head -1 || true)
            if [ -n "$found" ]; then
                MATCHES+=("$found")
            fi
        done
    fi
done

# Also do a direct grep search for any word in the prompt
for word in $PROMPT_LOWER; do
    # Skip common words
    if [ ${#word} -lt 4 ]; then continue; fi
    case "$word" in
        "the"|"and"|"for"|"this"|"that"|"with"|"from"|"have"|"will"|"make"|"just"|"please")
            continue
            ;;
    esac

    # Search lesson filenames
    found=$(ls "$LESSONS_DIR" 2>/dev/null | grep -i "$word" | head -2 || true)
    if [ -n "$found" ]; then
        while IFS= read -r f; do
            MATCHES+=("$f")
        done <<< "$found"
    fi
done

# Remove duplicates and limit to 3
UNIQUE_MATCHES=($(printf '%s\n' "${MATCHES[@]}" | sort -u | head -3))

# Exit if no matches
if [ ${#UNIQUE_MATCHES[@]} -eq 0 ]; then
    exit 0
fi

# Output advice header
echo ""
echo "📚 PRE-TASK ADVICE (from lessons learned):"
echo ""

# Extract key info from each lesson
for lesson in "${UNIQUE_MATCHES[@]}"; do
    filepath="$LESSONS_DIR/$lesson"
    if [ -f "$filepath" ]; then
        # Extract title (first # line)
        title=$(grep -m1 "^# " "$filepath" | sed 's/^# //' || echo "$lesson")
        # Extract severity if present
        severity=$(grep -m1 "Severity:" "$filepath" | sed 's/.*Severity:\s*//' || echo "")
        # Extract first prevention measure
        prevention=$(grep -A1 "## Prevention" "$filepath" | tail -1 | sed 's/^[-*] //' | head -c 80 || echo "")

        echo "• $title"
        if [ -n "$severity" ]; then
            echo "  ⚠️ Severity: $severity"
        fi
        if [ -n "$prevention" ]; then
            echo "  ✅ Prevention: $prevention..."
        fi
        echo ""
    fi
done

echo "💡 Run '/advise <topic>' for detailed analysis"
echo ""

exit 0
