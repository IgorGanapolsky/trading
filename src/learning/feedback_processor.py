"""
Autonomous Feedback Processor

Closes the loop between user feedback (thumbs up/down) and system learning.
No manual intervention required.

Architecture:
1. Capture feedback → capture_feedback.sh calls this
2. Store with context → SQLite session_feedback table
3. Trigger auto-reflection → Generate rules when patterns emerge
4. Boost/demote RAG lessons → Feedback-weighted retrieval
5. Signal to RL → Session quality affects future decisions

Based on December 2025 research:
- Anthropic's RLHF uses human preference as reward signal
- We adapt this for session-level feedback (simpler, more practical)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class FeedbackProcessor:
    """
    Autonomous feedback learning loop.

    Usage (called by capture_feedback.sh):
        processor = FeedbackProcessor()
        processor.process_feedback("positive", "thumbs up", session_context={...})
    """

    def __init__(self, db_path: str = "data/feedback_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

        # Thresholds for autonomous actions
        self.AUTO_REFLECT_THRESHOLD = 3  # Reflect after 3 feedbacks
        self.PATTERN_THRESHOLD = 2  # Generate rule after 2 similar feedbacks
        self.LESSON_BOOST = 0.2  # Boost lesson score by 20% on positive
        self.LESSON_DEMOTE = 0.3  # Demote lesson score by 30% on negative

    def _create_tables(self):
        """Create feedback tracking tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session_feedback (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                feedback_type TEXT,  -- positive, negative
                score INTEGER,       -- +1, -1
                user_message TEXT,
                session_id TEXT,
                context_summary TEXT,
                lessons_cited TEXT,  -- JSON list of lesson IDs that were active
                actions_taken TEXT,  -- JSON list of recent actions
                processed INTEGER DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lesson_weights (
                lesson_id TEXT PRIMARY KEY,
                base_weight REAL DEFAULT 1.0,
                feedback_boost REAL DEFAULT 0.0,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS auto_rules (
                id INTEGER PRIMARY KEY,
                rule_text TEXT,
                source_pattern TEXT,
                confidence REAL,
                created_at TEXT,
                applied INTEGER DEFAULT 0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rl_session_signals (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                quality_score REAL,  -- -1 to +1
                feedback_count INTEGER,
                net_sentiment REAL
            )
        """)

        self.conn.commit()

    def process_feedback(
        self,
        feedback_type: str,
        user_message: str,
        session_id: Optional[str] = None,
        lessons_cited: Optional[list] = None,
        actions_taken: Optional[list] = None,
        context_summary: Optional[str] = None,
    ) -> dict:
        """
        Process incoming feedback and trigger autonomous learning.

        Returns dict with actions taken.
        """
        score = 1 if feedback_type == "positive" else -1
        session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M")

        # 1. Store feedback with context
        self.conn.execute(
            """
            INSERT INTO session_feedback
            (timestamp, feedback_type, score, user_message, session_id,
             context_summary, lessons_cited, actions_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now().isoformat(),
                feedback_type,
                score,
                user_message,
                session_id,
                context_summary or "",
                json.dumps(lessons_cited or []),
                json.dumps(actions_taken or []),
            ),
        )
        self.conn.commit()

        actions = {"stored": True, "actions": []}

        # 2. Update lesson weights based on feedback
        if lessons_cited:
            self._update_lesson_weights(lessons_cited, score)
            actions["actions"].append(f"Updated weights for {len(lessons_cited)} lessons")

        # 3. Update RL session signal
        self._update_rl_signal(session_id, score)
        actions["actions"].append(f"RL signal updated: {score:+d}")

        # 4. Check if auto-reflection needed
        unprocessed = self._count_unprocessed()
        if unprocessed >= self.AUTO_REFLECT_THRESHOLD:
            rules = self._auto_reflect()
            if rules:
                actions["actions"].append(f"Auto-generated {len(rules)} rules")
                actions["new_rules"] = rules

        # 5. For negative feedback, immediately analyze what went wrong
        if feedback_type == "negative":
            analysis = self._analyze_negative_feedback(user_message, actions_taken)
            actions["negative_analysis"] = analysis
            actions["actions"].append("Analyzed negative feedback")

        return actions

    def _update_lesson_weights(self, lesson_ids: list, score: int):
        """Boost or demote lesson weights based on feedback."""
        for lesson_id in lesson_ids:
            cursor = self.conn.execute(
                "SELECT base_weight, feedback_boost, positive_count, negative_count "
                "FROM lesson_weights WHERE lesson_id = ?",
                (lesson_id,),
            )
            row = cursor.fetchone()

            if row:
                base, boost, pos, neg = row
                if score > 0:
                    boost += self.LESSON_BOOST
                    pos += 1
                else:
                    boost -= self.LESSON_DEMOTE
                    neg += 1

                self.conn.execute(
                    """
                    UPDATE lesson_weights
                    SET feedback_boost = ?, positive_count = ?, negative_count = ?,
                        last_updated = ?
                    WHERE lesson_id = ?
                """,
                    (boost, pos, neg, datetime.now().isoformat(), lesson_id),
                )
            else:
                boost = self.LESSON_BOOST if score > 0 else -self.LESSON_DEMOTE
                pos = 1 if score > 0 else 0
                neg = 0 if score > 0 else 1

                self.conn.execute(
                    """
                    INSERT INTO lesson_weights
                    (lesson_id, base_weight, feedback_boost, positive_count,
                     negative_count, last_updated)
                    VALUES (?, 1.0, ?, ?, ?, ?)
                """,
                    (lesson_id, boost, pos, neg, datetime.now().isoformat()),
                )

        self.conn.commit()

    def _update_rl_signal(self, session_id: str, score: int):
        """Update RL quality signal for the session."""
        cursor = self.conn.execute(
            "SELECT quality_score, feedback_count FROM rl_session_signals WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()

        if row:
            quality, count = row
            # Running average
            new_quality = (quality * count + score) / (count + 1)
            self.conn.execute(
                """
                UPDATE rl_session_signals
                SET quality_score = ?, feedback_count = ?, net_sentiment = ?,
                    timestamp = ?
                WHERE session_id = ?
            """,
                (new_quality, count + 1, new_quality, datetime.now().isoformat(), session_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO rl_session_signals
                (session_id, timestamp, quality_score, feedback_count, net_sentiment)
                VALUES (?, ?, ?, 1, ?)
            """,
                (session_id, datetime.now().isoformat(), float(score), float(score)),
            )

        self.conn.commit()

        # Write signal file for RL agent to consume
        signal_file = Path("data/feedback/rl_session_signal.json")
        signal_file.parent.mkdir(parents=True, exist_ok=True)

        cursor = self.conn.execute(
            "SELECT quality_score, feedback_count FROM rl_session_signals WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()

        signal_file.write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "quality_score": row[0] if row else 0,
                    "feedback_count": row[1] if row else 0,
                    "timestamp": datetime.now().isoformat(),
                },
                indent=2,
            )
        )

    def _count_unprocessed(self) -> int:
        """Count unprocessed feedback entries."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM session_feedback WHERE processed = 0")
        return cursor.fetchone()[0]

    def _auto_reflect(self) -> list:
        """
        Automatically generate rules from feedback patterns.
        No human approval needed - rules are stored and applied.
        """
        cursor = self.conn.execute("""
            SELECT feedback_type, user_message, actions_taken, context_summary
            FROM session_feedback
            WHERE processed = 0
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        feedbacks = cursor.fetchall()
        rules = []

        # Pattern detection: look for repeated negative feedback contexts
        negative_contexts = [(row[1], row[2], row[3]) for row in feedbacks if row[0] == "negative"]

        if len(negative_contexts) >= self.PATTERN_THRESHOLD:
            # Find common patterns
            action_counts = {}
            for _, actions_json, _ in negative_contexts:
                try:
                    actions = json.loads(actions_json) if actions_json else []
                    for action in actions:
                        action_counts[action] = action_counts.get(action, 0) + 1
                except json.JSONDecodeError:
                    pass

            # Generate rules for repeated problematic actions
            for action, count in action_counts.items():
                if count >= self.PATTERN_THRESHOLD:
                    rule = f"AVOID: {action} (caused {count} negative feedbacks)"
                    confidence = count / len(negative_contexts)

                    self.conn.execute(
                        """
                        INSERT INTO auto_rules
                        (rule_text, source_pattern, confidence, created_at)
                        VALUES (?, ?, ?, ?)
                    """,
                        (rule, action, confidence, datetime.now().isoformat()),
                    )

                    rules.append({"rule": rule, "confidence": confidence})

        # Pattern detection: reinforce positive behaviors
        positive_contexts = [(row[1], row[2], row[3]) for row in feedbacks if row[0] == "positive"]

        if len(positive_contexts) >= self.PATTERN_THRESHOLD:
            action_counts = {}
            for _, actions_json, _ in positive_contexts:
                try:
                    actions = json.loads(actions_json) if actions_json else []
                    for action in actions:
                        action_counts[action] = action_counts.get(action, 0) + 1
                except json.JSONDecodeError:
                    pass

            for action, count in action_counts.items():
                if count >= self.PATTERN_THRESHOLD:
                    rule = f"CONTINUE: {action} (led to {count} positive feedbacks)"
                    confidence = count / len(positive_contexts)

                    self.conn.execute(
                        """
                        INSERT INTO auto_rules
                        (rule_text, source_pattern, confidence, created_at)
                        VALUES (?, ?, ?, ?)
                    """,
                        (rule, action, confidence, datetime.now().isoformat()),
                    )

                    rules.append({"rule": rule, "confidence": confidence})

        # Mark feedbacks as processed
        self.conn.execute("UPDATE session_feedback SET processed = 1 WHERE processed = 0")
        self.conn.commit()

        # Write rules to file for CLAUDE.md integration
        if rules:
            self._write_auto_rules_file(rules)

        return rules

    def _write_auto_rules_file(self, rules: list):
        """Write auto-generated rules to a file for CLAUDE.md integration."""
        rules_file = Path("data/feedback/auto_rules.md")
        rules_file.parent.mkdir(parents=True, exist_ok=True)

        content = "# Auto-Generated Rules\n\n"
        content += f"Generated: {datetime.now().isoformat()}\n\n"

        for r in rules:
            content += f"- {r['rule']} (confidence: {r['confidence']:.0%})\n"

        rules_file.write_text(content)

    def _analyze_negative_feedback(self, user_message: str, actions_taken: Optional[list]) -> dict:
        """Analyze what went wrong when negative feedback received."""
        return {
            "user_said": user_message,
            "recent_actions": actions_taken or [],
            "recommendation": "Review recent actions and adjust behavior",
            "auto_action": "Logged for pattern detection",
        }

    def get_lesson_weight(self, lesson_id: str) -> float:
        """Get the feedback-adjusted weight for a lesson."""
        cursor = self.conn.execute(
            "SELECT base_weight, feedback_boost FROM lesson_weights WHERE lesson_id = ?",
            (lesson_id,),
        )
        row = cursor.fetchone()

        if row:
            base, boost = row
            # Clamp to reasonable range
            return max(0.1, min(2.0, base + boost))
        return 1.0  # Default weight

    def get_session_quality(self, session_id: str) -> float:
        """Get the quality score for a session (for RL reward shaping)."""
        cursor = self.conn.execute(
            "SELECT quality_score FROM rl_session_signals WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def get_stats(self) -> dict:
        """Get feedback statistics."""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN feedback_type = 'positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback_type = 'negative' THEN 1 ELSE 0 END) as negative
            FROM session_feedback
        """)
        row = cursor.fetchone()

        total, positive, negative = row
        total = total or 0
        positive = positive or 0
        negative = negative or 0

        cursor = self.conn.execute("SELECT COUNT(*) FROM auto_rules")
        rules_count = cursor.fetchone()[0]

        return {
            "total_feedback": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": (positive / total * 100) if total > 0 else 0,
            "auto_rules_generated": rules_count,
        }


def process_feedback_cli():
    """CLI entry point for capture_feedback.sh to call."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m src.learning.feedback_processor <type> <message>")
        sys.exit(1)

    feedback_type = sys.argv[1]  # positive or negative
    user_message = sys.argv[2]

    # Optional: session context from environment
    import os

    session_id = os.environ.get("CLAUDE_SESSION_ID", datetime.now().strftime("%Y%m%d"))

    processor = FeedbackProcessor()
    result = processor.process_feedback(
        feedback_type=feedback_type,
        user_message=user_message,
        session_id=session_id,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    process_feedback_cli()
