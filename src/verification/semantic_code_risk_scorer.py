"""
Semantic Code Change Risk Scorer.

Uses embeddings to understand code changes semantically and score
them for risk based on similarity to past failures. This goes beyond
simple pattern matching by understanding the meaning of changes.

Key Features:
1. Semantic similarity to past failure patterns
2. Code change intent classification
3. Impact analysis based on affected modules
4. Confidence-weighted risk scoring

Created: 2025-12-14
Author: Trading CTO
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Check for embedding availability
EMBEDDINGS_AVAILABLE = False
try:
    import httpx

    EMBEDDINGS_AVAILABLE = bool(
        os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    pass


class ChangeIntent(Enum):
    """Classification of code change intent."""

    FEATURE_ADD = "feature_add"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    OPTIMIZATION = "optimization"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    CLEANUP = "cleanup"
    UNKNOWN = "unknown"


class ImpactLevel(Enum):
    """Impact level of a code change."""

    MINIMAL = "minimal"  # Docs, comments, minor formatting
    LOW = "low"  # Tests, non-critical utilities
    MODERATE = "moderate"  # Helpers, non-trading logic
    HIGH = "high"  # Trading logic, risk management
    CRITICAL = "critical"  # Execution, safety systems


@dataclass
class CodeChunk:
    """A chunk of code for embedding."""

    file_path: str
    content: str
    change_type: str  # "added", "removed", "modified"
    line_start: int
    line_end: int
    embedding: Optional[list[float]] = None


@dataclass
class SemanticRiskScore:
    """Result of semantic risk scoring."""

    overall_score: float  # 0.0 to 1.0 (higher = riskier)
    change_intent: ChangeIntent
    impact_level: ImpactLevel
    similar_failures: list[dict]  # Past failures with similarity scores
    high_risk_chunks: list[CodeChunk]
    confidence: float
    explanation: str
    recommendations: list[str]


class SemanticCodeRiskScorer:
    """
    Scores code changes for risk using semantic analysis.

    Unlike pattern matching, this uses embeddings to understand:
    - What the code change is trying to do
    - How similar it is to past failures
    - Which modules are most impacted

    Embedding Strategy:
    1. OpenAI text-embedding-3-small via OpenRouter (primary)
    2. sentence-transformers all-MiniLM-L6-v2 (fallback)
    3. Keyword-based scoring (final fallback)
    """

    FAILURE_EMBEDDINGS_PATH = Path("data/ml/failure_embeddings.json")

    # Critical path patterns
    CRITICAL_PATHS = {
        "execution": [
            "src/execution/",
            "src/risk/trade_gateway",
            "scripts/autonomous_trader",
        ],
        "safety": [
            "src/safety/",
            "src/risk/",
            "src/verification/",
        ],
        "orchestration": [
            "src/orchestrator/",
            "src/agents/",
        ],
        "ml_pipeline": [
            "src/ml/",
            "src/rag/",
        ],
    }

    # Intent keywords for classification
    INTENT_KEYWORDS = {
        ChangeIntent.FEATURE_ADD: ["add", "new", "implement", "create", "introduce"],
        ChangeIntent.BUG_FIX: ["fix", "bug", "issue", "error", "patch", "correct"],
        ChangeIntent.REFACTOR: ["refactor", "restructure", "reorganize", "clean"],
        ChangeIntent.OPTIMIZATION: ["optimize", "improve", "performance", "speed", "faster"],
        ChangeIntent.DOCUMENTATION: ["doc", "comment", "readme", "explain"],
        ChangeIntent.TEST: ["test", "spec", "coverage", "mock"],
        ChangeIntent.CONFIGURATION: ["config", "setting", "env", "yaml", "json"],
        ChangeIntent.DEPENDENCY: ["dependency", "package", "requirements", "version"],
        ChangeIntent.SECURITY: ["security", "auth", "token", "secret", "permission"],
        ChangeIntent.CLEANUP: ["cleanup", "remove", "delete", "dead code"],
    }

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        rag_enabled: bool = True,
    ):
        """
        Initialize the semantic risk scorer.

        Args:
            model_name: sentence-transformers model to use
            rag_enabled: Whether to query RAG for similar failures
        """
        self.model_name = model_name
        self.encoder = None
        self.rag = None
        self.failure_embeddings: list[dict] = []
        self._embedding_method = "keyword"

        # Initialize embedding method
        self._init_embeddings()

        # Load failure embeddings
        self._load_failure_embeddings()

        # Initialize RAG if enabled
        if rag_enabled:
            self._init_rag()

    def _init_embeddings(self) -> None:
        """Initialize embedding method."""
        # Try API first
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                import httpx

                self._embedding_method = "api"
                logger.info("Using API embeddings for semantic scoring")
                return
            except ImportError:
                pass

        # Try local model
        try:
            from sentence_transformers import SentenceTransformer

            self.encoder = SentenceTransformer(self.model_name)
            self._embedding_method = "local"
            logger.info(f"Using local embeddings ({self.model_name})")
            return
        except Exception as e:
            logger.warning(f"Could not load local model: {e}")

        # Fallback to keyword
        self._embedding_method = "keyword"
        logger.warning("Using keyword-based scoring (no embeddings available)")

    def _init_rag(self) -> None:
        """Initialize RAG connection."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag = LessonsLearnedRAG()
            logger.info("RAG integration enabled for semantic scoring")
        except Exception as e:
            logger.warning(f"Could not initialize RAG: {e}")

    def _load_failure_embeddings(self) -> None:
        """Load pre-computed failure embeddings."""
        if self.FAILURE_EMBEDDINGS_PATH.exists():
            try:
                with open(self.FAILURE_EMBEDDINGS_PATH) as f:
                    self.failure_embeddings = json.load(f)
                logger.info(f"Loaded {len(self.failure_embeddings)} failure embeddings")
            except Exception as e:
                logger.warning(f"Could not load failure embeddings: {e}")

    def _save_failure_embeddings(self) -> None:
        """Save failure embeddings to disk."""
        self.FAILURE_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.FAILURE_EMBEDDINGS_PATH, "w") as f:
            json.dump(self.failure_embeddings, f)

    def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding for text."""
        if self._embedding_method == "api":
            return self._get_api_embedding(text)
        elif self._embedding_method == "local" and self.encoder:
            return self.encoder.encode(text).tolist()
        return None

    def _get_api_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding via API."""
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            import httpx

            if os.getenv("OPENROUTER_API_KEY"):
                url = "https://openrouter.ai/api/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/trading",
                }
                model = "openai/text-embedding-3-small"
            else:
                url = "https://api.openai.com/v1/embeddings"
                headers = {"Authorization": f"Bearer {api_key}"}
                model = "text-embedding-3-small"

            response = httpx.post(
                url,
                headers=headers,
                json={"input": text[:8000], "model": model},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

        except Exception as e:
            logger.warning(f"API embedding failed: {e}")
            return None

    def _cosine_similarity(
        self,
        a: list[float] | np.ndarray,
        b: list[float] | np.ndarray,
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

    def parse_diff(self, diff_content: str) -> list[CodeChunk]:
        """
        Parse a git diff into code chunks.

        Args:
            diff_content: Git diff content

        Returns:
            List of CodeChunk objects
        """
        chunks = []
        current_file = None
        current_content = []
        current_type = "modified"
        current_line = 0

        for line in diff_content.split("\n"):
            # New file header
            if line.startswith("diff --git"):
                # Save previous chunk
                if current_file and current_content:
                    chunks.append(
                        CodeChunk(
                            file_path=current_file,
                            content="\n".join(current_content),
                            change_type=current_type,
                            line_start=current_line,
                            line_end=current_line + len(current_content),
                        )
                    )
                current_content = []
                # Extract file path
                match = re.search(r"b/(.+)$", line)
                if match:
                    current_file = match.group(1)

            # Line number
            elif line.startswith("@@"):
                match = re.search(r"\+(\d+)", line)
                if match:
                    current_line = int(match.group(1))

            # Added line
            elif line.startswith("+") and not line.startswith("+++"):
                current_content.append(line[1:])
                current_type = "added"

            # Removed line
            elif line.startswith("-") and not line.startswith("---"):
                current_content.append(line[1:])
                current_type = "removed"

        # Save last chunk
        if current_file and current_content:
            chunks.append(
                CodeChunk(
                    file_path=current_file,
                    content="\n".join(current_content),
                    change_type=current_type,
                    line_start=current_line,
                    line_end=current_line + len(current_content),
                )
            )

        return chunks

    def classify_intent(
        self,
        commit_message: str,
        chunks: list[CodeChunk],
    ) -> ChangeIntent:
        """
        Classify the intent of a code change.

        Args:
            commit_message: The commit message
            chunks: The code chunks

        Returns:
            ChangeIntent enum value
        """
        # Combine text for analysis
        text = commit_message.lower()
        for chunk in chunks:
            text += " " + chunk.content.lower()

        # Check for intent keywords
        scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[intent] = score

        if scores:
            return max(scores, key=scores.get)

        return ChangeIntent.UNKNOWN

    def determine_impact_level(
        self,
        chunks: list[CodeChunk],
    ) -> ImpactLevel:
        """
        Determine the impact level of code changes.

        Args:
            chunks: The code chunks

        Returns:
            ImpactLevel enum value
        """
        max_impact = ImpactLevel.MINIMAL

        for chunk in chunks:
            file_path = chunk.file_path.lower()

            # Check against critical paths
            for category, patterns in self.CRITICAL_PATHS.items():
                for pattern in patterns:
                    if pattern in file_path:
                        if category == "execution":
                            return ImpactLevel.CRITICAL
                        elif category == "safety":
                            if max_impact.value not in ["critical"]:
                                max_impact = ImpactLevel.HIGH
                        elif category == "orchestration":
                            if max_impact.value in ["minimal", "low"]:
                                max_impact = ImpactLevel.HIGH
                        elif category == "ml_pipeline":
                            if max_impact.value in ["minimal", "low"]:
                                max_impact = ImpactLevel.MODERATE

            # Check by file extension
            if file_path.endswith((".md", ".txt", ".rst")):
                continue  # Minimal impact
            elif file_path.endswith("_test.py") or "/tests/" in file_path:
                if max_impact == ImpactLevel.MINIMAL:
                    max_impact = ImpactLevel.LOW

        return max_impact

    def find_similar_failures(
        self,
        chunks: list[CodeChunk],
        top_k: int = 5,
    ) -> list[dict]:
        """
        Find past failures similar to current changes.

        Args:
            chunks: The code chunks to analyze
            top_k: Number of similar failures to return

        Returns:
            List of similar failures with scores
        """
        if not chunks:
            return []

        # Combine chunk content for embedding
        combined_text = " ".join(c.content for c in chunks)[:5000]

        similar = []

        # Try semantic search if embeddings available
        if self._embedding_method != "keyword":
            chunk_embedding = self._get_embedding(combined_text)

            if chunk_embedding:
                for failure in self.failure_embeddings:
                    if failure.get("embedding"):
                        similarity = self._cosine_similarity(
                            chunk_embedding, failure["embedding"]
                        )
                        if similarity > 0.3:
                            similar.append(
                                {
                                    "id": failure["id"],
                                    "title": failure["title"],
                                    "similarity": round(similarity, 3),
                                    "prevention": failure.get("prevention", ""),
                                }
                            )

        # Also query RAG
        if self.rag:
            try:
                rag_results = self.rag.search(combined_text[:500], top_k=top_k)
                for lesson, score in rag_results:
                    if score > 0.3:
                        similar.append(
                            {
                                "id": lesson.id,
                                "title": lesson.title,
                                "similarity": round(score, 3),
                                "prevention": lesson.prevention,
                            }
                        )
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")

        # Deduplicate and sort by similarity
        seen_ids = set()
        unique_similar = []
        for s in sorted(similar, key=lambda x: x["similarity"], reverse=True):
            if s["id"] not in seen_ids:
                seen_ids.add(s["id"])
                unique_similar.append(s)

        return unique_similar[:top_k]

    def score_code_change(
        self,
        diff_content: str,
        commit_message: str = "",
    ) -> SemanticRiskScore:
        """
        Score a code change for risk.

        Args:
            diff_content: Git diff content
            commit_message: Optional commit message

        Returns:
            SemanticRiskScore with full analysis
        """
        # Parse diff into chunks
        chunks = self.parse_diff(diff_content)

        if not chunks:
            return SemanticRiskScore(
                overall_score=0.0,
                change_intent=ChangeIntent.UNKNOWN,
                impact_level=ImpactLevel.MINIMAL,
                similar_failures=[],
                high_risk_chunks=[],
                confidence=0.5,
                explanation="No parseable code changes found",
                recommendations=[],
            )

        # Classify intent
        intent = self.classify_intent(commit_message, chunks)

        # Determine impact level
        impact = self.determine_impact_level(chunks)

        # Find similar failures
        similar_failures = self.find_similar_failures(chunks)

        # Calculate embeddings for chunks
        high_risk_chunks = []
        for chunk in chunks:
            if any(
                pattern in chunk.file_path
                for patterns in self.CRITICAL_PATHS.values()
                for pattern in patterns
            ):
                # Get embedding for high-risk chunks
                if self._embedding_method != "keyword":
                    chunk.embedding = self._get_embedding(chunk.content[:1000])
                high_risk_chunks.append(chunk)

        # Calculate overall score
        score = self._calculate_score(
            intent=intent,
            impact=impact,
            similar_failures=similar_failures,
            num_chunks=len(chunks),
            num_high_risk=len(high_risk_chunks),
        )

        # Determine confidence based on method used
        if self._embedding_method == "api":
            confidence = 0.9
        elif self._embedding_method == "local":
            confidence = 0.75
        else:
            confidence = 0.5

        # Generate explanation
        explanation = self._generate_explanation(
            intent=intent,
            impact=impact,
            similar_failures=similar_failures,
            score=score,
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            impact=impact,
            similar_failures=similar_failures,
            high_risk_chunks=high_risk_chunks,
        )

        return SemanticRiskScore(
            overall_score=score,
            change_intent=intent,
            impact_level=impact,
            similar_failures=similar_failures,
            high_risk_chunks=high_risk_chunks,
            confidence=confidence,
            explanation=explanation,
            recommendations=recommendations,
        )

    def _calculate_score(
        self,
        intent: ChangeIntent,
        impact: ImpactLevel,
        similar_failures: list[dict],
        num_chunks: int,
        num_high_risk: int,
    ) -> float:
        """Calculate overall risk score."""
        score = 0.0

        # Impact level contribution (max 0.4)
        impact_scores = {
            ImpactLevel.MINIMAL: 0.0,
            ImpactLevel.LOW: 0.1,
            ImpactLevel.MODERATE: 0.2,
            ImpactLevel.HIGH: 0.3,
            ImpactLevel.CRITICAL: 0.4,
        }
        score += impact_scores.get(impact, 0.0)

        # Similar failures contribution (max 0.3)
        if similar_failures:
            avg_similarity = sum(f["similarity"] for f in similar_failures) / len(
                similar_failures
            )
            score += min(0.3, avg_similarity * 0.5)

        # High risk chunks contribution (max 0.2)
        score += min(0.2, num_high_risk * 0.05)

        # Intent-based adjustment (max 0.1)
        risky_intents = {
            ChangeIntent.BUG_FIX: 0.05,
            ChangeIntent.REFACTOR: 0.08,
            ChangeIntent.SECURITY: 0.1,
        }
        score += risky_intents.get(intent, 0.0)

        return min(1.0, score)

    def _generate_explanation(
        self,
        intent: ChangeIntent,
        impact: ImpactLevel,
        similar_failures: list[dict],
        score: float,
    ) -> str:
        """Generate explanation for the score."""
        risk_level = "low"
        if score >= 0.7:
            risk_level = "critical"
        elif score >= 0.5:
            risk_level = "high"
        elif score >= 0.3:
            risk_level = "moderate"

        explanation = (
            f"This {intent.value} change has {risk_level} risk (score: {score:.2f}). "
            f"Impact level: {impact.value}. "
        )

        if similar_failures:
            explanation += (
                f"Found {len(similar_failures)} similar past failures. "
                f"Most similar: {similar_failures[0]['title']} "
                f"(similarity: {similar_failures[0]['similarity']:.0%})."
            )
        else:
            explanation += "No similar past failures found."

        return explanation

    def _generate_recommendations(
        self,
        impact: ImpactLevel,
        similar_failures: list[dict],
        high_risk_chunks: list[CodeChunk],
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Impact-based recommendations
        if impact in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]:
            recommendations.extend(
                [
                    "Run full test suite before merge",
                    "Run pre_merge_gate.py",
                    "Verify critical imports work",
                    "Consider requesting human review",
                ]
            )

        # Similar failure-based recommendations
        for failure in similar_failures[:2]:
            if failure.get("prevention"):
                recommendations.append(f"[Past failure] {failure['prevention']}")

        # High-risk chunk recommendations
        if high_risk_chunks:
            affected_paths = set(c.file_path for c in high_risk_chunks)
            recommendations.append(
                f"Carefully review changes in: {', '.join(affected_paths)}"
            )

        return list(dict.fromkeys(recommendations))  # Deduplicate

    def add_failure_embedding(
        self,
        failure_id: str,
        title: str,
        description: str,
        prevention: str,
    ) -> bool:
        """
        Add a failure to the embedding database.

        Args:
            failure_id: Unique ID
            title: Failure title
            description: Failure description
            prevention: Prevention steps

        Returns:
            True if successful
        """
        if self._embedding_method == "keyword":
            return False

        text = f"{title} {description} {prevention}"
        embedding = self._get_embedding(text)

        if not embedding:
            return False

        self.failure_embeddings.append(
            {
                "id": failure_id,
                "title": title,
                "description": description,
                "prevention": prevention,
                "embedding": embedding,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        self._save_failure_embeddings()
        return True


def score_diff_risk(
    diff_content: str,
    commit_message: str = "",
) -> dict[str, Any]:
    """
    Convenience function to score a diff for risk.

    Returns:
        Dict with risk analysis
    """
    scorer = SemanticCodeRiskScorer()
    result = scorer.score_code_change(diff_content, commit_message)

    return {
        "score": result.overall_score,
        "intent": result.change_intent.value,
        "impact": result.impact_level.value,
        "confidence": result.confidence,
        "explanation": result.explanation,
        "similar_failures": result.similar_failures,
        "recommendations": result.recommendations,
        "high_risk_files": [c.file_path for c in result.high_risk_chunks],
    }


if __name__ == "__main__":
    """Demo the semantic risk scorer."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SEMANTIC CODE RISK SCORER DEMO")
    print("=" * 80)

    scorer = SemanticCodeRiskScorer()

    # Demo diff
    sample_diff = """
diff --git a/src/execution/alpaca_executor.py b/src/execution/alpaca_executor.py
@@ -100,6 +100,10 @@ class AlpacaExecutor:
+    def execute_trade(self, symbol, amount):
+        # Modified order validation
+        if amount > 1000:
+            raise ValueError("Order amount too large")
"""

    print("\nAnalyzing sample diff...")
    result = scorer.score_code_change(sample_diff, "fix: Add order amount validation")

    print(f"\nRisk Score: {result.overall_score:.2f}")
    print(f"Intent: {result.change_intent.value}")
    print(f"Impact: {result.impact_level.value}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"\nExplanation: {result.explanation}")

    print("\nRecommendations:")
    for r in result.recommendations:
        print(f"  - {r}")

    if result.similar_failures:
        print("\nSimilar Past Failures:")
        for f in result.similar_failures:
            print(f"  - {f['title']} (similarity: {f['similarity']:.0%})")
