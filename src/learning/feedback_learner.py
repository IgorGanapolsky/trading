"""
Autonomous Feedback Learning System

Processes user feedback (thumbs up/down) and converts to actionable learnings:
- Negative feedback → Creates lesson learned (prevents future mistakes)
- Positive feedback → Reinforces pattern (remember what worked)

This module runs autonomously on session start via hook.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """A single feedback event from user."""

    timestamp: str
    type: str  # "positive" or "negative"
    score: int  # 1 or -1
    context: str
    processed: bool = False


@dataclass
class LearningOutcome:
    """Result of processing feedback."""

    feedback_id: str
    action_taken: str  # "lesson_created", "pattern_reinforced", "already_processed"
    details: str


class FeedbackLearner:
    """
    Autonomous feedback learning engine.

    Reads feedback JSONL files, processes unhandled entries,
    and creates lessons or reinforces patterns.
    """

    def __init__(
        self,
        feedback_dir: Optional[str] = None,
        lessons_dir: Optional[str] = None,
        patterns_dir: Optional[str] = None,
    ):
        self.feedback_dir = Path(feedback_dir or "data/feedback")
        self.lessons_dir = Path(lessons_dir or "rag_knowledge/lessons_learned")
        self.patterns_dir = Path(patterns_dir or "data/feedback/patterns")
        self.processed_file = self.feedback_dir / "processed_feedback.json"

        # Ensure directories exist
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

        # Load processing state
        self.processed_ids = self._load_processed_state()

    def _load_processed_state(self) -> set:
        """Load IDs of already-processed feedback entries."""
        if self.processed_file.exists():
            try:
                data = json.loads(self.processed_file.read_text())
                return set(data.get("processed_ids", []))
            except Exception as e:
                logger.warning(f"Failed to load processed state: {e}")
        return set()

    def _save_processed_state(self) -> None:
        """Save IDs of processed feedback entries."""
        data = {
            "processed_ids": list(self.processed_ids),
            "last_updated": datetime.now().isoformat(),
            "total_processed": len(self.processed_ids),
        }
        self.processed_file.write_text(json.dumps(data, indent=2))

    def _generate_feedback_id(self, entry: FeedbackEntry) -> str:
        """Generate unique ID for feedback entry."""
        # Use timestamp + first 20 chars of context hash
        context_hash = str(hash(entry.context))[:8]
        ts_clean = entry.timestamp.replace(" ", "_").replace(":", "-")
        return f"fb_{ts_clean}_{context_hash}"

    def load_all_feedback(self) -> list[FeedbackEntry]:
        """Load all feedback entries from JSONL files."""
        entries = []

        for jsonl_file in sorted(self.feedback_dir.glob("feedback_*.jsonl")):
            try:
                for line in jsonl_file.read_text().strip().split("\n"):
                    if line.strip():
                        data = json.loads(line)
                        entry = FeedbackEntry(
                            timestamp=data.get("timestamp", ""),
                            type=data.get("type", "neutral"),
                            score=data.get("score", 0),
                            context=data.get("context", ""),
                        )
                        entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to load feedback from {jsonl_file}: {e}")

        return entries

    def get_pending_feedback(self) -> list[tuple[str, FeedbackEntry]]:
        """Get feedback entries that haven't been processed yet."""
        all_entries = self.load_all_feedback()
        pending = []

        for entry in all_entries:
            fb_id = self._generate_feedback_id(entry)
            if fb_id not in self.processed_ids:
                pending.append((fb_id, entry))

        return pending

    def _get_next_lesson_number(self) -> int:
        """Get next available lesson number."""
        max_num = 100  # Start after existing lessons

        for lesson_file in self.lessons_dir.glob("ll_*.md"):
            match = re.search(r"ll_(\d+)", lesson_file.stem)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

        return max_num + 1

    def create_lesson_from_negative_feedback(
        self, fb_id: str, entry: FeedbackEntry
    ) -> LearningOutcome:
        """
        Create a lesson learned from negative feedback.

        This is triggered when user gives thumbs down or indicates dissatisfaction.
        """
        lesson_num = self._get_next_lesson_number()
        lesson_id = f"ll_{lesson_num:03d}_feedback_learning"

        # Create lesson content
        lesson_content = f"""# LL-{lesson_num:03d}: User Feedback - Improvement Needed

**ID**: LL-{lesson_num:03d}
**Date**: {entry.timestamp.split()[0] if " " in entry.timestamp else datetime.now().strftime("%Y-%m-%d")}
**Severity**: HIGH
**Category**: User Feedback
**Impact**: User dissatisfaction, trust erosion
**Source**: Autonomous Feedback Learning System

## The Issue

User expressed dissatisfaction with Claude's response or action.

**Feedback received at**: {entry.timestamp}
**User signal**: {entry.context}

## Root Cause

This lesson was auto-generated from negative user feedback. The specific cause needs investigation.

**Possible factors:**
- Response didn't meet expectations
- Action taken was incorrect or incomplete
- Communication was unclear
- Task was misunderstood

## Prevention

1. **Before similar tasks**: Review this lesson and past context
2. **During task**: Ask clarifying questions if unsure
3. **After task**: Verify outcomes match expectations
4. **Always**: Be honest about uncertainty

## Action Required

- [x] Lesson automatically created from feedback
- [ ] Claude should ask user for specific improvement details
- [ ] Update this lesson with root cause once identified
- [ ] Add specific prevention rules once understood

## Learning Notes

*This lesson was auto-generated by the Feedback Learning System.*
*Update with specific learnings after discussing with user.*

## Tags

`feedback`, `improvement`, `user-satisfaction`, `auto-generated`
"""

        # Write lesson file
        lesson_file = self.lessons_dir / f"{lesson_id}.md"
        lesson_file.write_text(lesson_content)

        logger.info(f"Created lesson {lesson_id} from negative feedback")

        return LearningOutcome(
            feedback_id=fb_id,
            action_taken="lesson_created",
            details=f"Created {lesson_id} - needs user input for specific improvements",
        )

    def reinforce_positive_pattern(self, fb_id: str, entry: FeedbackEntry) -> LearningOutcome:
        """
        Reinforce a positive pattern from good feedback.

        Stores what worked so it can be replicated.
        """
        patterns_file = self.patterns_dir / "positive_patterns.jsonl"

        pattern_entry = {
            "timestamp": entry.timestamp,
            "context": entry.context,
            "feedback_id": fb_id,
            "recorded_at": datetime.now().isoformat(),
            "lesson": "User was satisfied - replicate this approach",
        }

        # Append to patterns file
        with open(patterns_file, "a") as f:
            f.write(json.dumps(pattern_entry) + "\n")

        logger.info(f"Reinforced positive pattern from feedback {fb_id}")

        return LearningOutcome(
            feedback_id=fb_id,
            action_taken="pattern_reinforced",
            details=f"Recorded positive pattern: {entry.context[:100]}...",
        )

    def process_single_feedback(self, fb_id: str, entry: FeedbackEntry) -> LearningOutcome:
        """Process a single feedback entry."""
        if fb_id in self.processed_ids:
            return LearningOutcome(
                feedback_id=fb_id,
                action_taken="already_processed",
                details="Feedback was already processed in previous session",
            )

        if entry.type == "negative":
            outcome = self.create_lesson_from_negative_feedback(fb_id, entry)
        elif entry.type == "positive":
            outcome = self.reinforce_positive_pattern(fb_id, entry)
        else:
            outcome = LearningOutcome(
                feedback_id=fb_id,
                action_taken="skipped",
                details="Neutral feedback - no action needed",
            )

        # Mark as processed
        self.processed_ids.add(fb_id)
        self._save_processed_state()

        return outcome

    def process_all_pending(self) -> list[LearningOutcome]:
        """
        Process all pending feedback entries.

        This is the main entry point for autonomous processing.
        """
        pending = self.get_pending_feedback()
        outcomes = []

        for fb_id, entry in pending:
            try:
                outcome = self.process_single_feedback(fb_id, entry)
                outcomes.append(outcome)
            except Exception as e:
                logger.error(f"Failed to process feedback {fb_id}: {e}")
                outcomes.append(
                    LearningOutcome(
                        feedback_id=fb_id,
                        action_taken="error",
                        details=str(e),
                    )
                )

        return outcomes

    def get_positive_patterns(self, limit: int = 10) -> list[dict]:
        """Retrieve recent positive patterns for reference."""
        patterns_file = self.patterns_dir / "positive_patterns.jsonl"
        patterns = []

        if patterns_file.exists():
            for line in patterns_file.read_text().strip().split("\n"):
                if line.strip():
                    try:
                        patterns.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Return most recent patterns
        return patterns[-limit:]

    def get_stats(self) -> dict:
        """Get feedback learning statistics."""
        all_feedback = self.load_all_feedback()
        positive = sum(1 for f in all_feedback if f.type == "positive")
        negative = sum(1 for f in all_feedback if f.type == "negative")

        return {
            "total_feedback": len(all_feedback),
            "positive": positive,
            "negative": negative,
            "processed": len(self.processed_ids),
            "pending": len(self.get_pending_feedback()),
            "satisfaction_rate": (positive / len(all_feedback) * 100) if all_feedback else 0,
        }


def run_autonomous_learning() -> dict:
    """
    Main entry point for autonomous feedback learning.

    Called by session-start hook to process pending feedback.
    Returns summary of actions taken.
    """
    learner = FeedbackLearner()
    outcomes = learner.process_all_pending()

    summary = {
        "processed_count": len(outcomes),
        "lessons_created": sum(1 for o in outcomes if o.action_taken == "lesson_created"),
        "patterns_reinforced": sum(1 for o in outcomes if o.action_taken == "pattern_reinforced"),
        "errors": sum(1 for o in outcomes if o.action_taken == "error"),
        "outcomes": [
            {"id": o.feedback_id, "action": o.action_taken, "details": o.details} for o in outcomes
        ],
        "stats": learner.get_stats(),
    }

    return summary


if __name__ == "__main__":
    # Can be run directly for testing
    logging.basicConfig(level=logging.INFO)

    result = run_autonomous_learning()
    print(json.dumps(result, indent=2))

    if result["processed_count"] > 0:
        print(f"\n✅ Processed {result['processed_count']} feedback entries")
        if result["lessons_created"] > 0:
            print(f"📚 Created {result['lessons_created']} new lessons")
        if result["patterns_reinforced"] > 0:
            print(f"💪 Reinforced {result['patterns_reinforced']} positive patterns")
    else:
        print("\n📭 No pending feedback to process")
