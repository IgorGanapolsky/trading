#!/usr/bin/env bash
# MemAlign RLHF Feedback Sync Hook
# Automatically syncs thumbs up/down feedback to dual-memory system

set -e

echo ""
echo "🧠 Hybrid Memory Sync - MemAlign + Cortex"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if pending feedback exists (support legacy + current paths)
PENDING_FILE=".claude/memory/feedback/pending_cortex_sync.jsonl"
LEGACY_PENDING_FILE=".claude/memory/pending_cortex_sync.jsonl"

if [ -f "$PENDING_FILE" ] && [ -s "$PENDING_FILE" ]; then
	ACTIVE_PENDING="$PENDING_FILE"
elif [ -f "$LEGACY_PENDING_FILE" ] && [ -s "$LEGACY_PENDING_FILE" ]; then
	ACTIVE_PENDING="$LEGACY_PENDING_FILE"
else
	echo "✅ No pending feedback - memory is up to date"
	echo ""
	exit 0
fi

# Count entries
ENTRY_COUNT=$(wc -l <"$ACTIVE_PENDING" | tr -d ' ')

echo "📥 Found $ENTRY_COUNT pending feedback entries"
echo "🔄 Syncing to MemAlign dual-memory system..."
echo ""

# Run RLHF integration (transpile-only to avoid local @types/node dependency)
if TS_NODE_TRANSPILE_ONLY=1 \
	TS_NODE_COMPILER_OPTIONS='{"module":"NodeNext","moduleResolution":"NodeNext","allowImportingTsExtensions":true}' \
	npx ts-node --transpile-only plugins/automation-plugin/skills/dynamic-agent-spawner/scripts/rlhf-integration.ts sync; then
	echo ""
	echo "✅ Hybrid memory sync complete"
	echo "   - MemAlign: Semantic principles + episodic memories updated"
	echo "   - Cortex: Human-readable audit trail appended"
	echo "   - Conflicts auto-resolved"
	echo ""
else
	echo ""
	echo "⚠️  Memory sync failed - will retry next session"
	echo ""
	exit 0 # Don't block session start on sync failure
fi
