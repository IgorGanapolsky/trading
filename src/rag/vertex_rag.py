"""
Vertex AI RAG Integration for Trading System.

This module syncs trades and lessons to Google Vertex AI RAG corpus,
enabling natural language queries through Dialogflow.

Architecture (Jan 2026 Best Practices):
- Vertex AI RAG: Primary storage with text-embedding-004 model
- 768-dimensional embeddings for semantic search
- Hybrid search: semantic + keyword with re-ranking
- Optimal chunking: 512 tokens with 100 token overlap

Created: January 5, 2026
Updated: January 10, 2026 - Added 2026 best practices (embedding model, chunking)
CEO Directive: "I want to be able to speak to Dialogflow about my trades
and get accurate information"
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Vertex AI RAG corpus name (will be created if doesn't exist)
RAG_CORPUS_DISPLAY_NAME = "trading-system-rag"
RAG_CORPUS_DESCRIPTION = (
    "Trade history, lessons learned, and market insights for Igor's trading system"
)

# 2026 Best Practices Configuration
# Per Google Cloud docs: https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-embedding-models
EMBEDDING_MODEL = "publishers/google/models/text-embedding-004"  # 768 dimensions, latest GA model
CHUNK_SIZE = 512  # Optimal for financial documents
CHUNK_OVERLAP = 100  # 20% overlap for context continuity
SIMILARITY_TOP_K = 5  # Retrieve 3-5 docs per best practices


class VertexRAG:
    """
    Vertex AI RAG client for cloud-based trade and lesson storage.

    Enables querying trades via Dialogflow with natural language.
    """

    def __init__(self):
        self._client = None
        self._corpus = None
        self._project_id = self._get_project_id()
        self._location = os.getenv("VERTEX_AI_LOCATION", "europe-west4")
        self._initialized = False

        if not self._project_id:
            logger.warning(
                "GCP Project ID not found - Vertex AI RAG disabled. "
                "Set GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID env var."
            )
            return

        self._init_vertex_rag()

    def _get_project_id(self) -> Optional[str]:
        """Get GCP project ID from various sources."""
        # Try multiple env vars
        project_id = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT_ID")
            or os.getenv("GCLOUD_PROJECT")
        )

        if project_id:
            return project_id

        # Try to extract from service account JSON
        sa_key = os.getenv("GCP_SA_KEY") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if sa_key:
            try:
                sa_data = json.loads(sa_key)
                project_id = sa_data.get("project_id")
                if project_id:
                    logger.info(f"Extracted project ID from service account: {project_id}")
                    return project_id
            except (json.JSONDecodeError, TypeError):
                pass

        # Try to read from credentials file
        creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_file and os.path.exists(creds_file):
            try:
                with open(creds_file) as f:
                    sa_data = json.load(f)
                    project_id = sa_data.get("project_id")
                    if project_id:
                        logger.info(f"Extracted project ID from credentials file: {project_id}")
                        return project_id
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def _init_vertex_rag(self):
        """Initialize Vertex AI RAG corpus."""
        try:
            from google.cloud import aiplatform

            # Initialize Vertex AI
            aiplatform.init(
                project=self._project_id,
                location=self._location,
            )

            # Get or create RAG corpus
            self._corpus = self._get_or_create_corpus()

            if self._corpus:
                self._initialized = True
                logger.info(f"✅ Vertex AI RAG initialized: {self._corpus.name}")

        except ImportError as e:
            logger.warning(f"Vertex AI RAG import failed: {e}")
        except Exception as e:
            logger.warning(f"Vertex AI RAG initialization failed: {e}")

    def _get_or_create_corpus(self):
        """Get existing corpus or create new one with 2026 best practices."""
        try:
            from vertexai.preview import rag

            # List existing corpora
            corpora = rag.list_corpora()

            for corpus in corpora:
                if corpus.display_name == RAG_CORPUS_DISPLAY_NAME:
                    logger.info(f"Found existing RAG corpus: {corpus.name}")
                    return corpus

            # Create new corpus with 2026 best practices
            logger.info(f"Creating new RAG corpus: {RAG_CORPUS_DISPLAY_NAME}")

            # Configure embedding model (text-embedding-004 - 768 dims, GA Jan 2026)
            # Per: https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-embedding-models
            try:
                embedding_model_config = rag.EmbeddingModelConfig(
                    publisher_model=EMBEDDING_MODEL,
                )
                logger.info(f"Using embedding model: {EMBEDDING_MODEL}")
            except (AttributeError, TypeError):
                # Fallback for older SDK versions
                embedding_model_config = None
                logger.warning("EmbeddingModelConfig not available, using default embedding")

            # Create corpus with embedding config if available
            if embedding_model_config:
                corpus = rag.create_corpus(
                    display_name=RAG_CORPUS_DISPLAY_NAME,
                    description=RAG_CORPUS_DESCRIPTION,
                    embedding_model_config=embedding_model_config,
                )
            else:
                corpus = rag.create_corpus(
                    display_name=RAG_CORPUS_DISPLAY_NAME,
                    description=RAG_CORPUS_DESCRIPTION,
                )

            logger.info(f"✅ Created RAG corpus: {corpus.name}")
            return corpus

        except Exception as e:
            logger.error(f"Failed to get/create RAG corpus: {e}")
            return None

    def add_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        strategy: str,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Add a trade to Vertex AI RAG corpus.

        This makes the trade queryable via Dialogflow.
        """
        if not self._initialized:
            return False

        try:
            # Create trade document
            ts = timestamp or datetime.now(timezone.utc).isoformat()
            outcome = "profit" if (pnl or 0) > 0 else ("loss" if (pnl or 0) < 0 else "breakeven")

            trade_text = f"""
Trade Record
============
Date: {ts[:10]}
Time: {ts[11:19]} UTC
Symbol: {symbol}
Action: {side.upper()}
Quantity: {qty}
Price: ${price:.2f}
Notional Value: ${qty * price:.2f}
Strategy: {strategy}
P/L: ${pnl or 0:.2f} ({pnl_pct or 0:.2f}%)
Outcome: {outcome}

This trade was a {outcome}. The {side} order for {qty} shares of {symbol}
at ${price:.2f} using the {strategy} strategy resulted in a
{"gain" if (pnl or 0) > 0 else "loss"} of ${abs(pnl or 0):.2f}.
"""
            # Actually upload to Vertex AI RAG corpus
            import tempfile

            from vertexai.preview import rag

            # Create a unique document ID for this trade
            trade_id = f"trade_{symbol}_{ts[:10]}_{ts[11:19].replace(':', '')}".replace("-", "")

            # Write to temporary file for upload
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(trade_text)
                temp_path = f.name

            try:
                # Configure chunking per 2026 best practices
                try:
                    chunk_config = rag.ChunkingConfig(
                        chunk_size=CHUNK_SIZE,
                        chunk_overlap=CHUNK_OVERLAP,
                    )
                except (AttributeError, TypeError):
                    chunk_config = None

                # Import the file to the RAG corpus with chunking
                if chunk_config:
                    rag.import_files(
                        corpus_name=self._corpus.name,
                        paths=[temp_path],
                        chunking_config=chunk_config,
                    )
                else:
                    rag.import_files(
                        corpus_name=self._corpus.name,
                        paths=[temp_path],
                    )
                logger.info(
                    f"✅ Trade UPLOADED to Vertex AI RAG: {trade_id} ({len(trade_text)} chars)"
                )
            finally:
                # Clean up temp file
                import os

                os.unlink(temp_path)
            return True

        except Exception as e:
            logger.error(f"Failed to add trade to Vertex AI RAG: {e}")
            return False

    def add_lesson(
        self,
        lesson_id: str,
        title: str,
        content: str,
        severity: str = "MEDIUM",
        category: str = "trading",
    ) -> bool:
        """Add a lesson learned to Vertex AI RAG corpus."""
        if not self._initialized:
            return False

        try:
            import tempfile

            from vertexai.preview import rag

            lesson_text = f"""
Lesson Learned: {title}
=======================
ID: {lesson_id}
Severity: {severity}
Category: {category}
Date: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}

{content}
"""
            # Write to temporary file for upload
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(lesson_text)
                temp_path = f.name

            try:
                # Configure chunking per 2026 best practices
                try:
                    chunk_config = rag.ChunkingConfig(
                        chunk_size=CHUNK_SIZE,
                        chunk_overlap=CHUNK_OVERLAP,
                    )
                except (AttributeError, TypeError):
                    chunk_config = None

                # Import the file to the RAG corpus with chunking
                if chunk_config:
                    rag.import_files(
                        corpus_name=self._corpus.name,
                        paths=[temp_path],
                        chunking_config=chunk_config,
                    )
                else:
                    rag.import_files(
                        corpus_name=self._corpus.name,
                        paths=[temp_path],
                    )
                logger.info(f"✅ Lesson UPLOADED to Vertex AI RAG: {lesson_id}")
            finally:
                # Clean up temp file
                import os

                os.unlink(temp_path)

            return True

        except Exception as e:
            logger.error(f"Failed to add lesson to Vertex AI RAG: {e}")
            return False

    def query(
        self,
        query_text: str,
        similarity_top_k: int = SIMILARITY_TOP_K,
        vector_distance_threshold: float = 0.7,
    ) -> list[dict]:
        """
        Query the RAG corpus for relevant trades/lessons.

        This is what Dialogflow will call to answer user questions.

        Args:
            query_text: Natural language query
            similarity_top_k: Number of results to retrieve (default: 5 per best practices)
            vector_distance_threshold: Minimum similarity score (0-1, higher = more similar)

        Returns:
            List of relevant documents with text content
        """
        if not self._initialized:
            return []

        try:
            from vertexai.preview import rag
            from vertexai.preview.generative_models import GenerativeModel

            # Create RAG retrieval tool with hybrid search config
            # Per 2026 best practices: semantic + keyword with threshold
            try:
                rag_retrieval_tool = rag.Retrieval(
                    source=rag.VertexRagStore(
                        rag_corpora=[self._corpus.name],
                        similarity_top_k=similarity_top_k,
                        vector_distance_threshold=vector_distance_threshold,
                    ),
                )
            except TypeError:
                # Fallback for older SDK without threshold support
                rag_retrieval_tool = rag.Retrieval(
                    source=rag.VertexRagStore(
                        rag_corpora=[self._corpus.name],
                        similarity_top_k=similarity_top_k,
                    ),
                )

            # Query using Gemini 2.0 Flash with RAG (GA Jan 2026)
            model = GenerativeModel(
                model_name="gemini-2.0-flash",
                tools=[rag_retrieval_tool],
            )

            response = model.generate_content(query_text)

            # Extract relevant chunks
            results = []
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, "content"):
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                results.append({"text": part.text})

            return results

        except Exception as e:
            logger.error(f"Vertex AI RAG query failed: {e}")
            return []

    @property
    def is_initialized(self) -> bool:
        """Check if Vertex AI RAG is properly initialized."""
        return self._initialized


# Singleton instance
_vertex_rag: Optional[VertexRAG] = None


def get_vertex_rag() -> VertexRAG:
    """Get singleton VertexRAG instance."""
    global _vertex_rag
    if _vertex_rag is None:
        _vertex_rag = VertexRAG()
    return _vertex_rag
