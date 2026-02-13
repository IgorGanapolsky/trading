#!/bin/bash
# Surface Feedback Patterns at Session Start
#
# Displays aggregated feedback statistics and per-category reliability
# so Claude knows its strengths and weaknesses before working.
#
# Output:
#   - Total feedback count (positive/negative/satisfaction rate)
#   - Top positive patterns (what works well)
#   - Top negative patterns (what to avoid)
#   - Per-category reliability if enough data exists
#
# LOCAL ONLY - Do not commit to repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FEEDBACK_LOG="$PROJECT_ROOT/.claude/memory/feedback/feedback-log.jsonl"
VENV_PYTHON="$PROJECT_ROOT/.claude/scripts/feedback/venv/bin/python3"

# Skip if no feedback exists
if [ ! -f "$FEEDBACK_LOG" ]; then
    exit 0
fi

# Use Python for reliable JSON parsing and aggregation
if [ -x "$VENV_PYTHON" ]; then
    PYTHON="$VENV_PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    exit 0
fi

"$PYTHON" - "$FEEDBACK_LOG" <<'PYEOF'
import sys
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

feedback_log = Path(sys.argv[1])
if not feedback_log.exists():
    sys.exit(0)

entries = []
cutoff = datetime.now() - timedelta(days=30)

with open(feedback_log) as f:
    for line in f:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")
            if ts:
                ts_clean = ts.replace("Z", "+00:00")
                try:
                    entry_time = datetime.fromisoformat(ts_clean.split("+")[0])
                except ValueError:
                    entry_time = datetime.now()
                if entry_time > cutoff:
                    entries.append(entry)
        except (json.JSONDecodeError, ValueError):
            continue

if not entries:
    sys.exit(0)

# Aggregate stats
total = len(entries)
positive = sum(1 for e in entries if e.get("feedback") == "positive" or e.get("reward", 0) > 0)
negative = sum(1 for e in entries if e.get("feedback") == "negative" or e.get("reward", 0) < 0)
auto = sum(1 for e in entries if e.get("source") == "auto")
manual = total - auto

satisfaction = positive / total * 100 if total > 0 else 0

print("=" * 50)
print("RLHF FEEDBACK PATTERNS (Last 30 Days)")
print("=" * 50)
print()
print(f"Total: {total} entries ({manual} manual, {auto} auto-detected)")
print(f"Positive: {positive} | Negative: {negative} | Satisfaction: {satisfaction:.0f}%")
print()

# Per-category reliability (by tool)
tool_stats = defaultdict(lambda: {"pos": 0, "neg": 0, "total": 0})
for e in entries:
    tool = e.get("tool_name", e.get("tags", ["unknown"])[0] if isinstance(e.get("tags"), list) and e.get("tags") else "unknown")
    tool_stats[tool]["total"] += 1
    if e.get("feedback") == "positive" or e.get("reward", 0) > 0:
        tool_stats[tool]["pos"] += 1
    elif e.get("feedback") == "negative" or e.get("reward", 0) < 0:
        tool_stats[tool]["neg"] += 1

# Only show categories with 3+ entries
significant = {k: v for k, v in tool_stats.items() if v["total"] >= 3 and k != "unknown"}
if significant:
    print("Per-Category Reliability:")
    for cat, stats in sorted(significant.items(), key=lambda x: x[1]["total"], reverse=True)[:8]:
        reliability = stats["pos"] / stats["total"] * 100 if stats["total"] > 0 else 0
        bar = "#" * int(reliability / 10) + "-" * (10 - int(reliability / 10))
        print(f"  {cat:15s} [{bar}] {reliability:.0f}% ({stats['total']} samples)")
    print()

# Top negative patterns (context-based)
neg_entries = [e for e in entries if e.get("feedback") == "negative" or e.get("reward", 0) < 0]
if neg_entries:
    print("Top Negative Patterns (AVOID):")
    # Group by context keywords
    neg_contexts = Counter()
    for e in neg_entries[:20]:
        ctx = e.get("context", e.get("message", ""))[:80]
        if ctx:
            neg_contexts[ctx] += 1
    for ctx, count in neg_contexts.most_common(3):
        print(f"  - ({count}x) {ctx}")
    print()

# Top positive patterns (REPEAT)
pos_entries = [e for e in entries if e.get("feedback") == "positive" or e.get("reward", 0) > 0]
if pos_entries:
    print("Top Positive Patterns (REPEAT):")
    pos_contexts = Counter()
    for e in pos_entries[:20]:
        ctx = e.get("context", e.get("message", ""))[:80]
        if ctx:
            pos_contexts[ctx] += 1
    for ctx, count in pos_contexts.most_common(3):
        print(f"  + ({count}x) {ctx}")
    print()

print("=" * 50)
PYEOF

# Thompson Sampling model summary (if available)
MODEL_JSON="$PROJECT_ROOT/.claude/memory/feedback/feedback_model.json"
if [ -f "$MODEL_JSON" ]; then
    "$PYTHON" - "$MODEL_JSON" <<'PYEOF2'
import sys, json
from pathlib import Path

model_file = Path(sys.argv[1])
if not model_file.exists():
    sys.exit(0)

try:
    model = json.loads(model_file.read_text())
except (json.JSONDecodeError, OSError):
    sys.exit(0)

cats = model.get("categories", {})
if not cats:
    sys.exit(0)

# Only show if model has been trained (total_entries > 0)
if model.get("total_entries", 0) == 0:
    sys.exit(0)

print()
print("Per-Category Reliability (Thompson Sampling):")
for cat, params in sorted(cats.items(), key=lambda x: -x[1].get("alpha", 1) / (x[1].get("alpha", 1) + x[1].get("beta", 1))):
    alpha = params.get("alpha", 1.0)
    beta_val = params.get("beta", 1.0)
    samples = params.get("samples", 0)
    if samples < 1:
        continue
    reliability = alpha / (alpha + beta_val)
    bar = "#" * int(reliability * 10) + "-" * (10 - int(reliability * 10))
    print(f"  {cat:15s} [{bar}] {reliability:.0f}% ({samples} samples)")

print()
PYEOF2
fi

exit 0
