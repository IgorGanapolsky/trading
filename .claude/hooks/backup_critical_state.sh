#!/bin/bash
# Automatic backup of critical state files before any modification
# Triggered: PreToolUse on Write/Edit to data/*.json files
#
# Maintains rolling 7-day backups with timestamps

set -e

BACKUP_DIR="data/backups"
MAX_BACKUPS=7

# Critical files to protect
CRITICAL_FILES=(
    "data/system_state.json"
    "data/performance_log.json"
    "data/feedback/stats.json"
)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Timestamp for this backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup each critical file if it exists
for FILE in "${CRITICAL_FILES[@]}"; do
    if [ -f "$FILE" ]; then
        BASENAME=$(basename "$FILE" .json)
        BACKUP_FILE="${BACKUP_DIR}/${BASENAME}_${TIMESTAMP}.json"
        cp "$FILE" "$BACKUP_FILE"
        echo "📦 Backed up: $FILE -> $BACKUP_FILE"
    fi
done

# Clean up old backups (keep only MAX_BACKUPS per file type)
for FILE in "${CRITICAL_FILES[@]}"; do
    BASENAME=$(basename "$FILE" .json)
    PATTERN="${BACKUP_DIR}/${BASENAME}_*.json"

    # Count backups for this file type
    COUNT=$(ls -1 $PATTERN 2>/dev/null | wc -l)

    if [ "$COUNT" -gt "$MAX_BACKUPS" ]; then
        # Remove oldest backups
        TO_DELETE=$((COUNT - MAX_BACKUPS))
        ls -1t $PATTERN | tail -n "$TO_DELETE" | xargs rm -f
        echo "🗑️ Cleaned up $TO_DELETE old backups for $BASENAME"
    fi
done

echo "✅ State backup complete"
