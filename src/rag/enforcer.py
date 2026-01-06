#!/usr/bin/env python3
"""
Mandatory RAG Query Enforcement System.

Based on January 2026 research:
- MemR3: Memory Retrieval via Reflective Reasoning (arxiv.org/html/2512.20237v1)
- ReasonRAG: Process-level rewards for query/evidence/answer
- Anthropic Claude Agent SDK: Memory tool with evidence tracking

This module enforces RAG consultation BEFORE any action, with:
1. Mandatory query step
2. Evidence-gap tracking
3. Process-level feedback recording

Created: Jan 6, 2026
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
    CHROMADB_AVAILABLE = False

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
ENFORCEMENT_LOG = DATA_DIR / "rag_enforcement_log.json"
VECTOR_DB_PATH = DATA_DIR / "vector_db"


class RAGEnforcer:
    """
    Enforces mandatory RAG consultation before actions.

    Based on MemR3's router pattern:
    - RETRIEVE: Query RAG for relevant lessons
    - REFLECT: Analyze if lessons apply to current action
    - ANSWER: Only proceed if no blocking lessons found
    """

    def __init__(self):
        self._client = None
        self._collection = None
        self._enforcement_log = self._load_log()
        self._init_chromadb()

    def _init_chromadb(self):
        """Initialize ChromaDB connection."""
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available - RAG Enforcer running in mock mode")
            return

        try:
            self._client = chromadb.PersistentClient(
                path=str(VECTOR_DB_PATH),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_collection("phil_town_rag")
            logger.info(f"RAG Enforcer initialized: {self._collection.count()} lessons")
        except Exception as e:
            logger.error(f"RAG Enforcer init failed: {e}")

    def _load_log(self) -> dict[str, Any]:
        """Load enforcement log."""
        if ENFORCEMENT_LOG.exists():
            try:
                with open(ENFORCEMENT_LOG) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "created": datetime.now(timezone.utc).isoformat(),
            "queries": [],
            "stats": {
                "total_queries": 0,
                "lessons_found": 0,
                "lessons_followed": 0,
                "lessons_ignored": 0,
            },
        }

    def _save_log(self):
        """Save enforcement log."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(ENFORCEMENT_LOG, "w") as f:
            json.dump(self._enforcement_log, f, indent=2)

    def query_before_action(
        self,
        action_type: str,
        action_description: str,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        MANDATORY: Query RAG before any action.

        Returns:
            dict with:
                - lessons: List of relevant lessons
                - blocking: Whether any CRITICAL lesson blocks action
                - evidence_gap: What's missing from current knowledge
                - recommendation: Proceed/Block/Review
        """
        if not self._collection:
            return {
                "lessons": [],
                "blocking": False,
                "evidence_gap": "RAG not available",
                "recommendation": "PROCEED_WITH_CAUTION",
            }

        # Build query from action
        query_text = f"{action_type}: {action_description}"
        if context:
            query_text += f" Context: {context}"

        # Query RAG
        results = self._collection.query(
            query_texts=[query_text],
            n_results=5,
        )

        lessons = []
        blocking = False
        blocking_lessons = []

        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            lesson = {
                "source": meta.get("source", "unknown"),
                "content": doc[:500],
                "severity": meta.get("severity", "MEDIUM"),
                "category": meta.get("category", "general"),
            }
            lessons.append(lesson)

            # Check for blocking conditions
            if meta.get("severity") == "CRITICAL":
                # Check if lesson is relevant to this action
                action_keywords = action_type.lower().split("_")
                doc_lower = doc.lower()
                if any(kw in doc_lower for kw in action_keywords):
                    blocking = True
                    blocking_lessons.append(lesson)

        # Determine evidence gap
        evidence_gap = self._assess_evidence_gap(action_type, lessons)

        # Determine recommendation
        if blocking:
            recommendation = "BLOCK"
        elif len(lessons) == 0:
            recommendation = "PROCEED_NO_PRECEDENT"
        elif evidence_gap:
            recommendation = "REVIEW_EVIDENCE_GAP"
        else:
            recommendation = "PROCEED"

        # Log the query
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "action_description": action_description[:200],
            "lessons_found": len(lessons),
            "blocking": blocking,
            "recommendation": recommendation,
        }
        self._enforcement_log["queries"].append(log_entry)
        self._enforcement_log["stats"]["total_queries"] += 1
        self._enforcement_log["stats"]["lessons_found"] += len(lessons)

        # Keep only last 100 queries
        self._enforcement_log["queries"] = self._enforcement_log["queries"][-100:]
        self._save_log()

        return {
            "lessons": lessons,
            "blocking": blocking,
            "blocking_lessons": blocking_lessons,
            "evidence_gap": evidence_gap,
            "recommendation": recommendation,
        }

    def _assess_evidence_gap(
        self,
        action_type: str,
        lessons: list[dict],
    ) -> Optional[str]:
        """Assess what evidence is missing."""
        # Common action types and what we should know
        required_knowledge = {
            "CREATE_DATA": ["data validation", "verification before creation"],
            "MODIFY_FILE": ["file verification", "backup before modify"],
            "CLAIM_STATUS": ["verification protocol", "evidence requirements"],
            "EXECUTE_TRADE": ["risk management", "position sizing"],
            "SYNC_DATA": ["data integrity", "conflict resolution"],
        }

        action_base = action_type.upper().split("_")[0]
        for key, requirements in required_knowledge.items():
            if key.startswith(action_base):
                # Check if any lessons cover these requirements
                lesson_text = " ".join(l["content"].lower() for l in lessons)
                missing = [r for r in requirements if r not in lesson_text]
                if missing:
                    return f"Missing knowledge about: {', '.join(missing)}"

        return None

    def record_outcome(
        self,
        action_type: str,
        followed_advice: bool,
        outcome: str,  # "success", "failure", "partial"
        notes: Optional[str] = None,
    ):
        """
        Record whether RAG advice was followed and the outcome.

        This enables process-level feedback for learning.
        """
        if followed_advice:
            self._enforcement_log["stats"]["lessons_followed"] += 1
        else:
            self._enforcement_log["stats"]["lessons_ignored"] += 1

        # Record for learning
        outcome_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "followed_advice": followed_advice,
            "outcome": outcome,
            "notes": notes,
        }

        if "outcomes" not in self._enforcement_log:
            self._enforcement_log["outcomes"] = []
        self._enforcement_log["outcomes"].append(outcome_entry)
        self._enforcement_log["outcomes"] = self._enforcement_log["outcomes"][-100:]

        self._save_log()

        # Log warning if advice was ignored and outcome was failure
        if not followed_advice and outcome == "failure":
            logger.warning(
                f"⚠️ IGNORED RAG ADVICE led to FAILURE: {action_type} - {notes}"
            )

    def get_stats(self) -> dict[str, Any]:
        """Get enforcement statistics."""
        stats = self._enforcement_log["stats"].copy()

        # Calculate follow rate
        total_decisions = stats["lessons_followed"] + stats["lessons_ignored"]
        if total_decisions > 0:
            stats["follow_rate"] = stats["lessons_followed"] / total_decisions * 100
        else:
            stats["follow_rate"] = 0

        return stats

    def get_recent_queries(self, limit: int = 10) -> list[dict]:
        """Get recent RAG queries."""
        return self._enforcement_log.get("queries", [])[-limit:]


# Singleton instance
_enforcer: Optional[RAGEnforcer] = None


def get_enforcer() -> RAGEnforcer:
    """Get singleton RAG enforcer instance."""
    global _enforcer
    if _enforcer is None:
        _enforcer = RAGEnforcer()
    return _enforcer


def query_before_action(
    action_type: str,
    action_description: str,
    context: Optional[str] = None,
) -> dict[str, Any]:
    """Convenience function to query RAG before action."""
    return get_enforcer().query_before_action(action_type, action_description, context)


def record_outcome(
    action_type: str,
    followed_advice: bool,
    outcome: str,
    notes: Optional[str] = None,
):
    """Convenience function to record action outcome."""
    get_enforcer().record_outcome(action_type, followed_advice, outcome, notes)


# ============================================================
# MANDATORY USAGE EXAMPLES
# ============================================================
#
# BEFORE creating any data:
#   result = query_before_action("CREATE_DATA", "Creating trades file for Jan 6")
#   if result["blocking"]:
#       print("BLOCKED:", result["blocking_lessons"])
#       return
#
# BEFORE making any claim:
#   result = query_before_action("CLAIM_STATUS", "System is working")
#   if result["recommendation"] != "PROCEED":
#       print("REVIEW NEEDED:", result["evidence_gap"])
#
# AFTER action completes:
#   record_outcome("CREATE_DATA", followed_advice=True, outcome="success")
