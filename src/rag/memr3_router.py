"""
MemR3 (Memory Retrieval via Reflective Reasoning) Router Pattern

Based on the paper: arxiv.org/html/2512.20237v1

This module implements a router that selects between three actions:
- RETRIEVE: Query RAG for relevant lessons
- REFLECT: Analyze if retrieved lessons apply to current context
- ANSWER: Proceed with action if safe

The router uses evidence gap tracking to determine when sufficient information
has been gathered to safely proceed with an answer.

Created: Jan 6, 2026 (Implementation of MemR3 pattern from research)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Paths
DECISIONS_LOG_PATH = Path("data/memr3_decisions.json")


class RouterAction(Enum):
    """Actions the router can select."""

    RETRIEVE = "retrieve"  # Query RAG for relevant lessons
    REFLECT = "reflect"  # Analyze if retrieved lessons apply to current context
    ANSWER = "answer"  # Proceed with action if safe


@dataclass
class Evidence:
    """Evidence gathered during the reasoning process."""

    requirement: str  # What requirement/question this evidence addresses
    content: str  # The actual evidence content
    source: str  # Where this evidence came from (e.g., "RAG:LL-001")
    confidence: float = 1.0  # Confidence in this evidence (0-1)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "requirement": self.requirement,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class Gap:
    """Knowledge gap that needs to be filled."""

    question: str  # What information is missing
    importance: str  # CRITICAL, HIGH, MEDIUM, LOW
    suggested_query: str = ""  # Suggested query to fill this gap
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "question": self.question,
            "importance": self.importance,
            "suggested_query": self.suggested_query,
            "timestamp": self.timestamp,
        }


class EvidenceGapTracker:
    """
    Tracks evidence gathered and gaps remaining during reasoning.

    This class maintains explicit state variables tracking both established
    and missing information, enabling reasoning under partial observability.
    """

    def __init__(self):
        self.evidence: list[Evidence] = []
        self.gaps: list[Gap] = []
        self._iteration: int = 0

    def add_evidence(
        self,
        requirement: str,
        content: str,
        source: str,
        confidence: float = 1.0,
    ) -> None:
        """Add evidence to the tracker."""
        evidence = Evidence(
            requirement=requirement,
            content=content,
            source=source,
            confidence=confidence,
        )
        self.evidence.append(evidence)
        logger.debug(f"Added evidence for '{requirement}' from {source}")

    def add_gap(
        self, question: str, importance: str = "MEDIUM", suggested_query: str = ""
    ) -> None:
        """Add a knowledge gap to the tracker."""
        gap = Gap(
            question=question, importance=importance, suggested_query=suggested_query
        )
        self.gaps.append(gap)
        logger.debug(f"Added gap: {question} (importance: {importance})")

    def remove_gap(self, question: str) -> bool:
        """Remove a gap once it's been filled."""
        for i, gap in enumerate(self.gaps):
            if gap.question == question:
                self.gaps.pop(i)
                logger.debug(f"Gap filled: {question}")
                return True
        return False

    def has_critical_gaps(self) -> bool:
        """Check if any CRITICAL gaps remain."""
        return any(gap.importance == "CRITICAL" for gap in self.gaps)

    def has_gaps(self) -> bool:
        """Check if any gaps remain."""
        return len(self.gaps) > 0

    def get_confidence_score(self) -> float:
        """
        Calculate overall confidence based on evidence quality and gaps.

        Returns:
            Confidence score (0-1)
        """
        if not self.evidence:
            return 0.0

        # Average confidence of evidence
        avg_evidence_confidence = sum(e.confidence for e in self.evidence) / len(
            self.evidence
        )

        # Penalty for gaps
        gap_penalty = 0.0
        if self.gaps:
            critical_gaps = sum(1 for g in self.gaps if g.importance == "CRITICAL")
            high_gaps = sum(1 for g in self.gaps if g.importance == "HIGH")
            medium_gaps = sum(1 for g in self.gaps if g.importance == "MEDIUM")

            gap_penalty = (critical_gaps * 0.3) + (high_gaps * 0.15) + (medium_gaps * 0.05)
            gap_penalty = min(gap_penalty, 0.5)  # Cap at 50% penalty

        return max(0.0, avg_evidence_confidence - gap_penalty)

    def increment_iteration(self) -> int:
        """Increment and return iteration count."""
        self._iteration += 1
        return self._iteration

    def get_iteration(self) -> int:
        """Get current iteration count."""
        return self._iteration

    def to_dict(self) -> dict:
        """Convert tracker state to dictionary for serialization."""
        return {
            "iteration": self._iteration,
            "evidence": [e.to_dict() for e in self.evidence],
            "gaps": [g.to_dict() for g in self.gaps],
            "confidence": self.get_confidence_score(),
        }


@dataclass
class RouterDecision:
    """A decision made by the router."""

    action: RouterAction
    confidence: float
    reason: str
    iteration: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "context": self.context,
        }


class MemR3Router:
    """
    MemR3 Router implementing the Memory Retrieval via Reflective Reasoning pattern.

    The router autonomously selects actions using deterministic constraints:
    1. Maximum iteration budget forces an answer
    2. Reflect-streak capacity prevents excessive reflection
    3. Retrieval-opportunity check ensures progress

    Based on Algorithm 1 from the paper.
    """

    def __init__(
        self,
        max_iterations: int = 10,
        max_reflect_streak: int = 2,
        min_confidence: float = 0.7,
        rag_integration: Optional[Any] = None,
    ):
        """
        Initialize the MemR3 Router.

        Args:
            max_iterations: Maximum iterations before forcing ANSWER
            max_reflect_streak: Maximum consecutive REFLECT actions
            min_confidence: Minimum confidence to proceed with ANSWER
            rag_integration: Optional RAG integration (LessonsSearch instance)
        """
        self.max_iterations = max_iterations
        self.max_reflect_streak = max_reflect_streak
        self.min_confidence = min_confidence
        self.rag = rag_integration

        self.tracker = EvidenceGapTracker()
        self._reflect_streak = 0
        self._last_action: Optional[RouterAction] = None
        self._decisions: list[RouterDecision] = []

        # Initialize RAG if not provided
        if self.rag is None:
            try:
                from src.rag.lessons_search import get_lessons_search

                self.rag = get_lessons_search()
                logger.info("MemR3Router: RAG integration initialized")
            except Exception as e:
                logger.warning(f"MemR3Router: RAG init failed: {e}")

    def route(self, query: str, context: dict = None) -> RouterDecision:
        """
        Route the query to the appropriate action.

        Args:
            query: The user query or task
            context: Optional context dictionary

        Returns:
            RouterDecision with action, confidence, and reason
        """
        context = context or {}
        self.tracker.increment_iteration()
        iteration = self.tracker.get_iteration()

        # Algorithm 1: Deterministic constraints
        # Constraint 1: Maximum iteration budget forces ANSWER
        if iteration >= self.max_iterations:
            decision = self._make_decision(
                RouterAction.ANSWER,
                confidence=self.tracker.get_confidence_score(),
                reason=f"Maximum iterations ({self.max_iterations}) reached - forcing answer",
                context=context,
            )
            self._log_decision(decision)
            return decision

        # Constraint 2: Reflect-streak capacity prevents excessive reflection
        if self._reflect_streak >= self.max_reflect_streak:
            # Must RETRIEVE to break reflection streak
            decision = self._make_decision(
                RouterAction.RETRIEVE,
                confidence=0.8,
                reason=f"Reflection streak ({self._reflect_streak}) exceeded - retrieving new information",
                context=context,
            )
            self._log_decision(decision)
            return decision

        # Constraint 3: Semantic stopping criterion - when gaps become empty
        if not self.tracker.has_gaps():
            confidence = self.tracker.get_confidence_score()
            if confidence >= self.min_confidence:
                decision = self._make_decision(
                    RouterAction.ANSWER,
                    confidence=confidence,
                    reason=f"All gaps filled with confidence {confidence:.2f} >= {self.min_confidence}",
                    context=context,
                )
                self._log_decision(decision)
                return decision

        # Decide based on current state
        action = self._select_action(query, context)
        confidence = self._calculate_confidence(action)
        reason = self._generate_reason(action, query)

        decision = self._make_decision(action, confidence, reason, context)
        self._log_decision(decision)
        return decision

    def _select_action(self, query: str, context: dict) -> RouterAction:
        """
        Select the appropriate action based on current state.

        Logic:
        1. If no evidence yet, RETRIEVE
        2. If critical gaps exist, RETRIEVE
        3. If evidence exists but unclear if applicable, REFLECT
        4. If confidence high enough, ANSWER
        """
        # No evidence yet - must retrieve
        if not self.tracker.evidence:
            return RouterAction.RETRIEVE

        # Critical gaps - must retrieve
        if self.tracker.has_critical_gaps():
            return RouterAction.RETRIEVE

        # Check confidence
        confidence = self.tracker.get_confidence_score()

        # Low confidence - need more information or reflection
        if confidence < self.min_confidence:
            # If we have evidence but low confidence, reflect on it
            if self.tracker.evidence and self._reflect_streak < self.max_reflect_streak:
                return RouterAction.REFLECT
            # Otherwise retrieve more
            return RouterAction.RETRIEVE

        # High confidence and no critical gaps - answer
        return RouterAction.ANSWER

    def _calculate_confidence(self, action: RouterAction) -> float:
        """Calculate confidence for the selected action."""
        base_confidence = self.tracker.get_confidence_score()

        # Adjust based on action
        if action == RouterAction.ANSWER:
            return base_confidence
        elif action == RouterAction.REFLECT:
            # Reflection adds uncertainty
            return base_confidence * 0.9
        else:  # RETRIEVE
            # Retrieval is neutral
            return base_confidence

    def _generate_reason(self, action: RouterAction, query: str) -> str:
        """Generate human-readable reason for the action."""
        confidence = self.tracker.get_confidence_score()
        gap_count = len(self.tracker.gaps)
        evidence_count = len(self.tracker.evidence)

        if action == RouterAction.RETRIEVE:
            if evidence_count == 0:
                return "No evidence gathered yet - initiating retrieval"
            elif self.tracker.has_critical_gaps():
                return f"{gap_count} critical gaps remain - retrieving more information"
            else:
                return f"Confidence {confidence:.2f} below threshold {self.min_confidence} - need more evidence"

        elif action == RouterAction.REFLECT:
            return f"Have {evidence_count} evidence items - reflecting on applicability to current context"

        else:  # ANSWER
            return f"Confidence {confidence:.2f} with {evidence_count} evidence items - safe to proceed"

    def _make_decision(
        self, action: RouterAction, confidence: float, reason: str, context: dict
    ) -> RouterDecision:
        """Create a RouterDecision and update internal state."""
        # Update reflect streak
        if action == RouterAction.REFLECT:
            self._reflect_streak += 1
        else:
            self._reflect_streak = 0

        self._last_action = action

        decision = RouterDecision(
            action=action,
            confidence=confidence,
            reason=reason,
            iteration=self.tracker.get_iteration(),
            context=context,
        )

        self._decisions.append(decision)
        return decision

    def _log_decision(self, decision: RouterDecision) -> None:
        """Log decision to JSON file for transparency."""
        try:
            DECISIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Load existing decisions
            decisions = []
            if DECISIONS_LOG_PATH.exists():
                try:
                    with open(DECISIONS_LOG_PATH) as f:
                        decisions = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Could not parse existing decisions log")

            # Append new decision
            decisions.append(
                {
                    "decision": decision.to_dict(),
                    "tracker_state": self.tracker.to_dict(),
                }
            )

            # Write back
            with open(DECISIONS_LOG_PATH, "w") as f:
                json.dump(decisions, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to log decision: {e}")

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[Any, float]]:
        """
        Retrieve relevant lessons from RAG.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (LessonResult, score) tuples
        """
        if self.rag is None:
            logger.warning("RAG not available for retrieval")
            return []

        try:
            results = self.rag.search(query, top_k=top_k)

            # Add evidence to tracker
            for lesson, score in results:
                self.tracker.add_evidence(
                    requirement=query,
                    content=lesson.snippet,
                    source=f"RAG:{lesson.id}",
                    confidence=score,
                )

            logger.info(f"Retrieved {len(results)} lessons for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def reflect(self, query: str, retrieved_lessons: list = None) -> dict:
        """
        Reflect on retrieved lessons and current context.

        This method analyzes if the retrieved lessons are applicable,
        identifies gaps, and updates the evidence tracker.

        Args:
            query: The original query
            retrieved_lessons: Optional list of retrieved lessons to reflect on

        Returns:
            Dictionary with reflection results
        """
        reflection = {
            "query": query,
            "evidence_count": len(self.tracker.evidence),
            "gaps_identified": [],
            "confidence": self.tracker.get_confidence_score(),
        }

        # Analyze evidence for gaps
        if self.tracker.evidence:
            # Check for common gaps in trading context
            evidence_topics = set()
            for e in self.tracker.evidence:
                # Extract topic from evidence
                if "position siz" in e.content.lower():
                    evidence_topics.add("position_sizing")
                if "risk" in e.content.lower():
                    evidence_topics.add("risk_management")
                if "stop loss" in e.content.lower():
                    evidence_topics.add("stop_loss")

            # Identify missing critical topics
            required_topics = ["risk_management", "position_sizing"]
            for topic in required_topics:
                if topic not in evidence_topics:
                    gap_text = f"Missing information about {topic.replace('_', ' ')}"
                    self.tracker.add_gap(
                        question=gap_text,
                        importance="HIGH",
                        suggested_query=f"{topic.replace('_', ' ')} in trading",
                    )
                    reflection["gaps_identified"].append(gap_text)

        logger.info(
            f"Reflection complete: {len(reflection['gaps_identified'])} gaps identified"
        )
        return reflection

    def get_decision_history(self) -> list[RouterDecision]:
        """Get history of all routing decisions."""
        return self._decisions.copy()

    def reset(self) -> None:
        """Reset the router state for a new query."""
        self.tracker = EvidenceGapTracker()
        self._reflect_streak = 0
        self._last_action = None
        self._decisions = []
        logger.info("Router reset for new query")


def create_router(
    max_iterations: int = 10,
    max_reflect_streak: int = 2,
    min_confidence: float = 0.7,
) -> MemR3Router:
    """
    Factory function to create a MemR3Router with default RAG integration.

    Args:
        max_iterations: Maximum iterations before forcing ANSWER
        max_reflect_streak: Maximum consecutive REFLECT actions
        min_confidence: Minimum confidence to proceed with ANSWER

    Returns:
        Configured MemR3Router instance
    """
    return MemR3Router(
        max_iterations=max_iterations,
        max_reflect_streak=max_reflect_streak,
        min_confidence=min_confidence,
    )


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    router = create_router()

    # Simulate a query flow
    query = "How should I handle position sizing for a volatile stock?"

    print(f"\n=== MemR3 Router Example: '{query}' ===\n")

    for i in range(5):
        decision = router.route(query)
        print(f"Iteration {decision.iteration}:")
        print(f"  Action: {decision.action.value.upper()}")
        print(f"  Confidence: {decision.confidence:.2f}")
        print(f"  Reason: {decision.reason}")

        if decision.action == RouterAction.RETRIEVE:
            results = router.retrieve(query)
            print(f"  Retrieved: {len(results)} lessons")

        elif decision.action == RouterAction.REFLECT:
            reflection = router.reflect(query)
            print(f"  Gaps identified: {len(reflection['gaps_identified'])}")

        elif decision.action == RouterAction.ANSWER:
            print(f"  Ready to answer!")
            break

        print()

    print(f"\n=== Decision History ===")
    print(f"Total decisions: {len(router.get_decision_history())}")
    print(f"Final confidence: {router.tracker.get_confidence_score():.2f}")
