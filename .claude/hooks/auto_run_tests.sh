#!/bin/bash
# Auto-run tests when test files are edited
# Triggered by PostToolUse hook on Write|Edit

FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Only run for test files
if [[ ! "$FILE_PATH" =~ test.*\.py$ ]] && [[ ! "$FILE_PATH" =~ _test\.py$ ]]; then
    exit 0
fi

# Check if file exists
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Run pytest on the specific test file with minimal output
# Use timeout to prevent hanging (30 seconds max)
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Run the specific test file
RESULT=$(timeout 30 python3 -m pytest "$FILE_PATH" -v --tb=short 2>&1)
EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    # Count passed tests
    PASSED=$(echo "$RESULT" | grep -oP '\d+(?= passed)' | head -1)
    echo "✅ Tests passed: ${PASSED:-all} in $(basename "$FILE_PATH")"
elif [[ $EXIT_CODE -eq 124 ]]; then
    echo "⚠️ Test timed out after 30s: $(basename "$FILE_PATH")"
else
    # Extract failure summary
    FAILED=$(echo "$RESULT" | grep -oP '\d+(?= failed)' | head -1)
    echo "❌ Tests failed: ${FAILED:-some} in $(basename "$FILE_PATH")"
    echo "$RESULT" | grep -A5 "FAILED\|AssertionError\|Error" | head -10
fi

# Always exit 0 to not block the edit (non-blocking feedback)
exit 0
