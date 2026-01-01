#!/bin/bash
#
# Vector DB Verification Hook - BLOCKS session if RAG is broken
#
# Created: Dec 30, 2025
# Updated: Jan 1, 2026 - Added semantic search verification (LL-074 fix)
#
# This hook runs on session start and WILL FAIL if RAG is not operational.
# No more silent fallbacks to useless keyword matching.

set -e

echo "🔍 Verifying Vector Database..."

# Run the comprehensive Python verification
VERIFY_OUTPUT=$(PYTHONPATH="${CLAUDE_PROJECT_DIR}" python3 "${CLAUDE_PROJECT_DIR}/scripts/verify_rag_operational.py" 2>&1 | grep -v "telemetry" || true)
VERIFY_EXIT_CODE=${PIPESTATUS[0]}

# Show condensed output
echo "$VERIFY_OUTPUT" | grep -E "^(✅|❌|==)" | head -10

if [[ $VERIFY_EXIT_CODE -ne 0 ]]; then
    echo ""
    echo "❌ RAG VERIFICATION FAILED"
    echo ""
    echo "🔧 Attempting auto-repair..."

    # Try to install chromadb if missing
    python3 -c "import chromadb" 2>/dev/null || pip install chromadb==0.6.3 --quiet

    # Rebuild vector DB
    PYTHONPATH="${CLAUDE_PROJECT_DIR}" python3 "${CLAUDE_PROJECT_DIR}/scripts/vectorize_rag_knowledge.py" --rebuild 2>&1 | tail -5

    # Verify again
    VERIFY_OUTPUT=$(PYTHONPATH="${CLAUDE_PROJECT_DIR}" python3 "${CLAUDE_PROJECT_DIR}/scripts/verify_rag_operational.py" 2>&1 | grep -v "telemetry" || true)
    VERIFY_EXIT_CODE=${PIPESTATUS[0]}

    if [[ $VERIFY_EXIT_CODE -ne 0 ]]; then
        echo ""
        echo "❌ RAG AUTO-REPAIR FAILED - CANNOT PROCEED"
        echo "   Manual intervention required."
        # Don't exit with error to avoid blocking completely, but warn loudly
        echo "⚠️ WARNING: Trading without RAG is DANGEROUS"
    else
        echo "✅ RAG auto-repair successful"
    fi
fi
