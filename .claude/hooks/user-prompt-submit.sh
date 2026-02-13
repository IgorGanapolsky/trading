#!/bin/bash
# User Prompt Submit Hook - Detects thumbs up/down feedback
# This hook runs BEFORE Claude processes user message
#
# FEEDBACK RECORDING SYSTEM:
# LanceDB via semantic-memory-v2.py (RLHF + hybrid BM25/vector search)
#
# KEY IMPROVEMENT (Jan 2026): Auto-captures Claude's last response from transcript
# instead of relying on manual context entry. Inspired by igor project approach.

set -e

SCRIPT_DIR="$(dirname "$0")"
MEMORY_DIR="$SCRIPT_DIR/../memory"
FEEDBACK_DIR="$SCRIPT_DIR/../scripts/feedback"
FEEDBACK_LOG_JSONL="$MEMORY_DIR/feedback/feedback-log.jsonl"
VENV_PYTHON="$FEEDBACK_DIR/venv/bin/python3"
SEMANTIC_MEMORY="$FEEDBACK_DIR/semantic-memory-v2.py"
TRAIN_SCRIPT="$FEEDBACK_DIR/train_from_feedback.py"
CORTEX_SYNC="$FEEDBACK_DIR/cortex_sync.py"

mkdir -p "$MEMORY_DIR/feedback"

# Read user message from stdin (Claude passes it via stdin)
USER_MESSAGE=$(cat)

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Prefer venv python for semantic memory (has LanceDB + embedding deps).
SEMANTIC_PYTHON=""
if [ -x "$VENV_PYTHON" ]; then
    SEMANTIC_PYTHON="$VENV_PYTHON"
fi

FALLBACK_PYTHON=""
if command -v python3 &>/dev/null; then
    FALLBACK_PYTHON="python3"
fi

sanitize_one_line() {
    # Hooks pass user text with newlines; keep JSONL entries one-line.
    tr '\n\t' '  ' | sed 's/  */ /g'
}

append_feedback_jsonl_fallback() {
    # Fallback when semantic-memory-v2 isn't available. Writes a minimal entry
    # compatible with train_from_feedback.py + semantic-memory-v2.py indexing.
    local feedback_type="$1"
    local reward="$2"
    local source="$3"
    local signal="$4"
    local tags_csv="$5"
    local context="$6"

    if [ -z "$FALLBACK_PYTHON" ]; then
        return 0
    fi

    mkdir -p "$MEMORY_DIR/feedback"

    # Pass content via env to avoid quoting hell.
    FEEDBACK_TS="$TIMESTAMP" \
    FEEDBACK_TYPE="$feedback_type" \
    FEEDBACK_REWARD="$reward" \
    FEEDBACK_SOURCE="$source" \
    FEEDBACK_SIGNAL="$signal" \
    FEEDBACK_TAGS="$tags_csv" \
    FEEDBACK_CONTEXT="$context" \
    FEEDBACK_USER_MESSAGE="$USER_MESSAGE" \
    FEEDBACK_ASSISTANT_RESPONSE="$LAST_CLAUDE_RESPONSE" \
    "$FALLBACK_PYTHON" - <<'PY' >>"$FEEDBACK_LOG_JSONL" 2>/dev/null || true
import os, json, hashlib
from datetime import datetime

ts = os.environ.get("FEEDBACK_TS") or datetime.utcnow().isoformat() + "Z"
context = (os.environ.get("FEEDBACK_CONTEXT") or "").strip()
feedback_type = os.environ.get("FEEDBACK_TYPE") or "negative"
tags_csv = os.environ.get("FEEDBACK_TAGS") or ""
tags = [t.strip() for t in tags_csv.split(",") if t.strip()]

try:
    reward = float(os.environ.get("FEEDBACK_REWARD", "-1"))
except Exception:
    reward = -1.0

entry = {
    "id": "fb_" + hashlib.md5((ts + ":" + context[:50]).encode("utf-8")).hexdigest()[:8],
    "timestamp": ts,
    "feedback": feedback_type,
    "context": context[:2000],
    "tags": tags,
    "reward": reward,
    "source": os.environ.get("FEEDBACK_SOURCE") or "hook",
    "signal": os.environ.get("FEEDBACK_SIGNAL"),
    "user_message": (os.environ.get("FEEDBACK_USER_MESSAGE") or "").strip()[:2000],
    "assistant_response": (os.environ.get("FEEDBACK_ASSISTANT_RESPONSE") or "").strip()[:2000],
}

print(json.dumps(entry, ensure_ascii=True))
PY
}

record_feedback() {
    local feedback_type="$1"
    local reward="$2"
    local source="$3"
    local signal="$4"
    local tags_csv="$5"
    local context="$6"
    local no_reindex="$7"  # "true" to skip LanceDB reindex

    context="$(printf '%s' "$context" | sanitize_one_line | head -c 2000)"

    if [ -n "$SEMANTIC_PYTHON" ] && [ -f "$SEMANTIC_MEMORY" ]; then
        # semantic-memory-v2.py writes to feedback-log.jsonl and can reindex LanceDB.
        # Silence stdout/stderr to avoid polluting prompt context.
        echo "$context" | "$SEMANTIC_PYTHON" "$SEMANTIC_MEMORY" \
            --add-feedback \
            --feedback-type "$feedback_type" \
            --reward "$reward" \
            --source "$source" \
            --signal "$signal" \
            --tags "$tags_csv" \
            $([ "$no_reindex" = "true" ] && echo "--no-reindex") \
            >/dev/null 2>&1 || append_feedback_jsonl_fallback "$feedback_type" "$reward" "$source" "$signal" "$tags_csv" "$context"
    else
        append_feedback_jsonl_fallback "$feedback_type" "$reward" "$source" "$signal" "$tags_csv" "$context"
    fi
}

update_thompson_model() {
    local py=""
    if [ -x "$VENV_PYTHON" ]; then
        py="$VENV_PYTHON"
    elif [ -n "$FALLBACK_PYTHON" ]; then
        py="$FALLBACK_PYTHON"
    else
        return 0
    fi

    if [ -f "$TRAIN_SCRIPT" ]; then
        "$py" "$TRAIN_SCRIPT" --incremental >/dev/null 2>&1 || true
    fi
}

queue_cortex_sync() {
    local signal="$1"
    local intensity="$2"
    local context="$3"
    local source="$4"

    if [ ! -f "$CORTEX_SYNC" ]; then
        return 0
    fi

    if [ -x "$VENV_PYTHON" ]; then
        "$VENV_PYTHON" "$CORTEX_SYNC" \
            --queue --signal "$signal" --intensity "$intensity" \
            --context "$context" \
            --source "$source" >/dev/null 2>&1 || true
    elif [ -n "$FALLBACK_PYTHON" ]; then
        "$FALLBACK_PYTHON" "$CORTEX_SYNC" \
            --queue --signal "$signal" --intensity "$intensity" \
            --context "$context" \
            --source "$source" >/dev/null 2>&1 || true
    fi
}

# ============================================
# Auto-capture Claude's last response from transcript
# This is the KEY improvement - no manual context needed
# ============================================
get_last_claude_response() {
    local transcript_dir="$HOME/.claude/projects"
    # Find the most recently modified transcript
    local latest_transcript
    latest_transcript=$(find "$transcript_dir" -name "*.jsonl" -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)
    if [ -n "$latest_transcript" ] && [ -f "$latest_transcript" ]; then
        # Get last assistant message content, truncate to 500 chars
        tail -50 "$latest_transcript" 2>/dev/null \
            | grep '"type":"assistant"' \
            | tail -1 \
            | python3 -c '
import json, sys
try:
    line = sys.stdin.read().strip()
    if line:
        obj = json.loads(line)
        msg = obj.get("message", {})
        content = msg.get("content", [])
        text_parts = [c.get("text","") for c in content if c.get("type") == "text"]
        result = " ".join(text_parts)[:500]
        print(result)
except:
    pass
' 2>/dev/null || true
    fi
}

LAST_CLAUDE_RESPONSE=$(get_last_claude_response)

# ============================================
# Feedback Detection and Recording
# ============================================

detect_feedback() {
    local msg_lower
    msg_lower=$(echo "$USER_MESSAGE" | tr '[:upper:]' '[:lower:]')

    if echo "$msg_lower" | grep -qE "thumbs down|👎|bad response|wrong answer|incorrect"; then
        echo "negative"
    elif echo "$msg_lower" | grep -qE "thumbs up|👍|great|good job|well done|perfect|excellent"; then
        echo "positive"
    else
        echo "none"
    fi
}

FEEDBACK_TYPE=$(detect_feedback)

if [ "$FEEDBACK_TYPE" = "negative" ]; then
    echo ""
    echo "=================================================="
    echo "THUMBS DOWN DETECTED - MANDATORY RECORDING"
    echo "=================================================="
    echo ""
    echo "Claude MUST:"
    echo "   1. ASK what went wrong"
    echo "   2. RECORD the failure pattern"
    echo "   3. APOLOGIZE and explain prevention"
    echo ""
    echo "DO NOT PROCEED WITHOUT RECORDING!"
    echo "=================================================="

    FEEDBACK_CONTEXT="$USER_MESSAGE"
    if [ -n "$LAST_CLAUDE_RESPONSE" ]; then
        FEEDBACK_CONTEXT="User thumbs down on assistant response: $LAST_CLAUDE_RESPONSE"
    fi
    record_feedback "negative" "-1" "user" "thumbs_down" "explicit,thumbs-down" "$FEEDBACK_CONTEXT" "false"
    update_thompson_model
    queue_cortex_sync "negative" "3" "User thumbs down: ${FEEDBACK_CONTEXT:0:150}" "user"

elif [ "$FEEDBACK_TYPE" = "positive" ]; then
    echo ""
    echo "=================================================="
    echo "THUMBS UP DETECTED - RECORD SUCCESS PATTERN"
    echo "=================================================="
    echo ""
    echo "Claude MUST record what worked well."
    echo "=================================================="

    FEEDBACK_CONTEXT="$USER_MESSAGE"
    if [ -n "$LAST_CLAUDE_RESPONSE" ]; then
        FEEDBACK_CONTEXT="User thumbs up on assistant response: $LAST_CLAUDE_RESPONSE"
    fi
    record_feedback "positive" "1" "user" "thumbs_up" "explicit,thumbs-up" "$FEEDBACK_CONTEXT" "false"
    update_thompson_model
    queue_cortex_sync "positive" "3" "User thumbs up: ${FEEDBACK_CONTEXT:0:150}" "user"
fi

# Detect pending correction (user corrects after thumbs down)
if echo "$USER_MESSAGE" | grep -qi "actually\|correction\|what i meant\|no, the issue\|the real problem"; then
    if [ -f "$FEEDBACK_LOG_JSONL" ] && tail -5 "$FEEDBACK_LOG_JSONL" 2>/dev/null | grep -q '"negative"'; then
        echo ""
        echo "=================================================="
        echo "CORRECTION DETECTED - Update previous feedback"
        echo "=================================================="
        echo "User appears to be correcting a previous thumbs-down."
        echo "Claude SHOULD update the feedback context with this clarification."
        echo "=================================================="
    fi
fi

# ============================================
# IMPLICIT FEEDBACK DETECTION (2026 Best Practice)
# Detects undo/revert signals as implicit negative feedback
# Based on: arXiv:2509.03990 - Implicit feedback is 3x more predictive
# ============================================

IMPLICIT_NEGATIVE_KEYWORDS="undo|revert|rollback|go back|restore|that broke|that failed|that's wrong|not what i asked|try again|start over"
IMPLICIT_POSITIVE_KEYWORDS="ship it|merge it|lgtm|looks good|approved|that works|worked"

detect_implicit_feedback() {
    local msg_lower
    msg_lower=$(echo "$USER_MESSAGE" | tr '[:upper:]' '[:lower:]')

    # Check for implicit negative signals
    if echo "$msg_lower" | grep -qiE "$IMPLICIT_NEGATIVE_KEYWORDS"; then
        echo "implicit_negative"
    # Check for implicit positive signals
    elif echo "$msg_lower" | grep -qiE "$IMPLICIT_POSITIVE_KEYWORDS"; then
        echo "implicit_positive"
    else
        echo "none"
    fi
}

IMPLICIT_FEEDBACK=$(detect_implicit_feedback)

if [ "$IMPLICIT_FEEDBACK" = "implicit_negative" ] && [ "$FEEDBACK_TYPE" = "none" ]; then
    FEEDBACK_CONTEXT="IMPLICIT NEGATIVE: User signaled undo/revert. User message: $USER_MESSAGE"
    if [ -n "$LAST_CLAUDE_RESPONSE" ]; then
        FEEDBACK_CONTEXT="IMPLICIT NEGATIVE (undo/revert) on assistant response: $LAST_CLAUDE_RESPONSE"
    fi
    record_feedback "negative" "-0.5" "auto" "undo_revert" "implicit,undo-revert" "$FEEDBACK_CONTEXT" "true"
    update_thompson_model
    queue_cortex_sync "negative" "2" "Implicit negative (undo/revert): ${USER_MESSAGE:0:100}" "auto"

elif [ "$IMPLICIT_FEEDBACK" = "implicit_positive" ] && [ "$FEEDBACK_TYPE" = "none" ]; then
    FEEDBACK_CONTEXT="IMPLICIT POSITIVE: User approved/continued. User message: $USER_MESSAGE"
    if [ -n "$LAST_CLAUDE_RESPONSE" ]; then
        FEEDBACK_CONTEXT="IMPLICIT POSITIVE (approval) on assistant response: $LAST_CLAUDE_RESPONSE"
    fi
    record_feedback "positive" "0.5" "auto" "approval" "implicit,approval" "$FEEDBACK_CONTEXT" "true"
    update_thompson_model
    queue_cortex_sync "positive" "2" "Implicit positive (approval): ${USER_MESSAGE:0:100}" "auto"
fi

# ============================================
# RALPH MODE - Multi-File Task Detection
# ============================================
USER_MESSAGE_LOWER=$(echo "$USER_MESSAGE" | tr '[:upper:]' '[:lower:]')

RALPH_KEYWORDS="implement|add feature|create|refactor|rewrite|redesign|build|fix.*and|update.*and|change.*multiple|across.*files|overnight|autonomous|/ralph|start ralph"
SINGLE_FILE_KEYWORDS="fix typo|fix this line|change this|update this file|in this file only|single file|one file"

if echo "$USER_MESSAGE_LOWER" | grep -qiE "$SINGLE_FILE_KEYWORDS"; then
    :
elif echo "$USER_MESSAGE_LOWER" | grep -qiE "$RALPH_KEYWORDS"; then
    echo ""
    echo "===================================================="
    echo "RALPH MODE - Multi-File Task Detected"
    echo "===================================================="
    echo ""
    echo "This looks like a multi-file change. Claude SHOULD use Ralph:"
    echo "   .claude/scripts/ralph-loop.sh start \"<description>\" [work-item-id]"
    echo ""
    echo "Ralph provides:"
    echo "   - Structured task breakdown"
    echo "   - Commit after each completed task"
    echo "   - Session recovery if interrupted"
    echo "   - Draft PR when complete"
    echo ""
    echo "Skip Ralph only for trivial single-file fixes."
    echo "===================================================="
fi

# ============================================
# PARALLEL SESSION Detection
# ============================================
PARALLEL_KEYWORDS="in parallel|parallel session|spawn session|new worktree|separate branch for|work on multiple|concurrent task|while i work on|at the same time|simultaneously|/parallel"

if echo "$USER_MESSAGE_LOWER" | grep -qiE "$PARALLEL_KEYWORDS"; then
    echo ""
    echo "===================================================="
    echo "PARALLEL SESSION DETECTED"
    echo "===================================================="
    echo ""
    echo "Claude MUST spawn parallel session:"
    echo "   .claude/scripts/parallel-claude.sh spawn \"<description>\" [work-item-id]"
    echo ""
    echo "This will:"
    echo "   - Create isolated git worktree"
    echo "   - Open new iTerm window with Claude"
    echo "   - Both sessions work independently"
    echo "===================================================="
fi

# Do not print the user message; other hooks provide context injection only.
