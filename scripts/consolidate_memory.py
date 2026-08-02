#!/usr/bin/env python3
"""Memory consolidation script.

Reads raw JSONL memory stores, groups entries by date+category,
deduplicates, extracts meaningful content, and writes consolidated
scene-level summaries. Runs at session start (async) to keep
retrieval fast and noise-free.

Architecture (from MarkTechPost self-organizing memory pattern):
  Raw JSONL -> Group by scene (date+category) -> Consolidate -> Summary store
  Original files are preserved; consolidated_memory.json is the read-optimized view.
"""

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / ".claude" / "memory"
FEEDBACK_DIR = MEMORY_DIR / "feedback"
MEMALIGN_DIR = MEMORY_DIR / "memalign"
OUTPUT_FILE = MEMORY_DIR / "consolidated_memory.json"

# Memory cell types (inspired by article's taxonomy)
CELL_TYPES = {"fact", "decision", "risk", "preference", "plan", "task"}

# Noise patterns to filter out during consolidation
NOISE_PATTERNS = [
    "Avoid: unknown decision",
    "The agent's decision was incorrect: undefined",
]


def is_noise(entry: dict) -> bool:
    """Check if an entry is low-value noise."""
    principle = entry.get("principle", "")
    context = entry.get("context", "")
    user_feedback = entry.get("userFeedback", "")

    for pattern in NOISE_PATTERNS:
        if pattern in principle or pattern in user_feedback:
            # Still noise even if context exists but is just "thumbs up/down"
            clean_ctx = context.strip() if context else ""
            if not clean_ctx or clean_ctx in ("thumbs up", "thumbs down"):
                return True
    return False


def classify_cell(entry: dict) -> str:
    """Classify a memory entry into a cell type."""
    context = (entry.get("context", "") or entry.get("userFeedback", "") or "").lower()

    if any(w in context for w in ["risk", "phil town", "rule #1", "don't lose", "stop-loss"]):
        return "risk"
    if any(w in context for w in ["decided", "decision", "chose", "approach"]):
        return "decision"
    if any(w in context for w in ["prefer", "want", "should", "always", "never"]):
        return "preference"
    if any(w in context for w in ["plan", "implement", "build", "add"]):
        return "plan"
    if any(w in context for w in ["task", "fix", "bug", "error", "failing"]):
        return "task"
    return "fact"


def compute_salience(entry: dict) -> float:
    """Compute write-time salience score (0.0-1.0)."""
    score = 0.3  # baseline

    # Intensity boost
    intensity = entry.get("intensity", 0)
    if isinstance(intensity, (int, float)):
        score += min(intensity / 10.0, 0.3)

    # Rich context boost
    context = entry.get("context", "") or entry.get("richContext", {})
    if isinstance(context, dict):
        context = context.get("description", "")
    if len(str(context)) > 100:
        score += 0.2

    # Explicit feedback boost
    reward = entry.get("reward")
    if reward is not None:
        score += 0.1

    # Critical signal boost
    signal = entry.get("signal", "")
    if "strong" in str(signal) or "CRITICAL" in str(entry.get("context", "")):
        score += 0.1

    return min(score, 1.0)


def extract_date_key(timestamp_str: str) -> str:
    """Extract YYYY-MM-DD from a timestamp string."""
    if not timestamp_str:
        return "unknown"
    try:
        # Handle various timestamp formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return timestamp_str[:10] if len(timestamp_str) >= 10 else "unknown"
    except Exception:
        return "unknown"


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, skipping malformed lines."""
    entries = []
    if not path.exists():
        return entries
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  [warn] Skipped malformed line {line_num} in {path.name}", file=sys.stderr)
    return entries


def consolidate_scene(scene_key: str, entries: list[dict]) -> dict:
    """Consolidate a group of entries into a scene summary."""
    total = len(entries)
    positive = sum(
        1
        for e in entries
        if e.get("signal", e.get("feedback", e.get("sentiment", ""))).startswith("positive")
        or e.get("reward", 0) > 0
    )
    negative = sum(
        1
        for e in entries
        if e.get("signal", e.get("feedback", e.get("sentiment", ""))).startswith("negative")
        or e.get("reward", 0) < 0
    )

    # Extract meaningful context snippets (skip noise)
    contexts = []
    for e in entries:
        ctx = e.get("context", "") or e.get("richContext", {})
        if isinstance(ctx, dict):
            ctx = ctx.get("description", "")
        ctx = str(ctx).strip()
        if ctx and len(ctx) > 20 and not any(p in ctx for p in NOISE_PATTERNS):
            # Skip raw JSON session blobs that leaked into context
            if ctx.startswith("{") and "session_id" in ctx:
                continue
            # Truncate long contexts to first 200 chars for summary
            contexts.append(ctx[:200])

    # Extract principles that aren't noise
    principles = []
    for e in entries:
        p = e.get("principle", "")
        if p and p not in NOISE_PATTERNS and "unknown decision" not in p:
            principles.append(p)

    # Classify entries
    type_counts = defaultdict(int)
    for e in entries:
        cell_type = classify_cell(e)
        type_counts[cell_type] += 1

    # Compute aggregate salience
    saliences = [compute_salience(e) for e in entries]
    avg_salience = sum(saliences) / len(saliences) if saliences else 0.0
    max_salience = max(saliences) if saliences else 0.0

    # Deduplicate contexts
    unique_contexts = list(dict.fromkeys(contexts))[:5]  # top 5 unique
    unique_principles = list(dict.fromkeys(principles))[:3]  # top 3 unique

    return {
        "scene": scene_key,
        "entry_count": total,
        "positive": positive,
        "negative": negative,
        "satisfaction_rate": round(positive / total, 2) if total > 0 else 0,
        "avg_salience": round(avg_salience, 3),
        "max_salience": round(max_salience, 3),
        "dominant_type": max(type_counts, key=type_counts.get) if type_counts else "fact",
        "type_distribution": dict(type_counts),
        "key_contexts": unique_contexts,
        "principles": unique_principles,
        "noise_filtered": total - len([e for e in entries if not is_noise(e)]),
    }


def main():
    print("Memory Consolidation Starting...")

    # Load all raw stores
    feedback_entries = load_jsonl(FEEDBACK_DIR / "feedback-log.jsonl")
    episodes = load_jsonl(MEMALIGN_DIR / "episodes.jsonl")
    principles = load_jsonl(MEMALIGN_DIR / "principles.jsonl")

    print(
        f"  Raw entries: feedback={len(feedback_entries)}, episodes={len(episodes)}, principles={len(principles)}"
    )

    # Pre-filter: count noise
    feedback_noise = sum(1 for e in feedback_entries if is_noise(e))
    episodes_noise = sum(1 for e in episodes if is_noise(e))
    principles_noise = sum(1 for e in principles if is_noise(e))
    total_noise = feedback_noise + episodes_noise + principles_noise
    total_raw = len(feedback_entries) + len(episodes) + len(principles)

    print(
        f"  Noise entries: {total_noise}/{total_raw} ({round(total_noise / total_raw * 100) if total_raw else 0}%)"
    )

    # Merge all entries, tagging source
    all_entries = []
    for e in feedback_entries:
        e["_source"] = "feedback"
        all_entries.append(e)
    for e in episodes:
        e["_source"] = "episodes"
        all_entries.append(e)
    # principles.jsonl is a derivative of episodes — don't double-count
    # but extract unique principles for the summary
    extracted_principles = []
    for p in principles:
        principle_text = p.get("principle", "")
        if principle_text and "unknown decision" not in principle_text:
            extracted_principles.append(
                {
                    "principle": principle_text,
                    "sentiment": p.get("sentiment", "neutral"),
                    "intensity": p.get("intensity", 0),
                    "timestamp": p.get("timestamp", ""),
                }
            )

    # Group by date + category
    scenes = defaultdict(list)
    for entry in all_entries:
        ts = entry.get("timestamp", "")
        date_key = extract_date_key(ts)
        category = entry.get("task_category", "general")
        scene_key = f"{date_key}:{category}"
        scenes[scene_key].append(entry)

    # Consolidate each scene
    consolidated_scenes = []
    for scene_key in sorted(scenes.keys()):
        entries = scenes[scene_key]
        scene_summary = consolidate_scene(scene_key, entries)
        consolidated_scenes.append(scene_summary)

    # Build output
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "version": 1,
        "consolidated_at": now,
        "stats": {
            "total_raw_entries": total_raw,
            "total_noise_filtered": total_noise,
            "noise_percentage": round(total_noise / total_raw * 100, 1) if total_raw else 0,
            "scenes_created": len(consolidated_scenes),
            "unique_principles": len(extracted_principles),
            "sources": {
                "feedback_log": len(feedback_entries),
                "episodes": len(episodes),
                "principles_extracted": len(extracted_principles),
            },
        },
        "principles": extracted_principles,
        "scenes": consolidated_scenes,
    }

    # Write consolidated output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Scenes: {len(consolidated_scenes)}")
    print(f"  Principles: {len(extracted_principles)}")
    print(f"  Output: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print("Memory Consolidation Complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
