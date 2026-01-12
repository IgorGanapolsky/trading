"""Vertex AI RAG Engine integration for trading lessons.

CEO Directive (Jan 6, 2026): Record every trade and lesson in Vertex AI RAG.

This module provides bidirectional sync:
- WRITE: Sync trades and lessons to Vertex AI RAG corpus
- READ: Query lessons for pre-trade advice

Architecture (2026 best practices):
- Uses Vertex AI RAG Engine (not deprecated Vector Search)
- Gemini 2.0 Flash for grounded generation
- Hybrid search (semantic + keyword)
- Local JSON fallback when API unavailable

References:
- https://cloud.google.com/vertex-ai/generative-ai/docs/rag-engine
- https://cloud.google.com/vertex-ai/generative-ai/docs/grounding
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Constants
DEFAULT_PROJECT = "igor-trading-2025-v2"
DEFAULT_LOCATION = "us-central1"
CORPUS_DISPLAY_NAME = "trading-lessons-corpus"
LOCAL_LESSONS_PATH = Path("rag_knowledge/lessons_learned")
LOCAL_TRADES_PATH = Path("data")


class VertexRAG:
    """Vertex AI RAG Engine client for trading lessons.
    
    Provides:
    - add_document(): Add trade or lesson to RAG corpus
    - query(): Query RAG for relevant lessons
    - sync_lessons(): Bulk sync local lessons to RAG
    - get_pretrade_advice(): Get advice before trading
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        corpus_name: str | None = None,
    ):
        """Initialize Vertex AI RAG client.
        
        Args:
            project_id: GCP project ID (default from env or constant)
            location: GCP region (default us-central1)
            corpus_name: RAG corpus resource name (auto-discovered if None)
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT)
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION)
        self.corpus_name = corpus_name
        self._client = None
        self._corpus = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of Vertex AI client."""
        if self._initialized:
            return True

        try:
            from google.cloud import aiplatform
            from vertexai import rag

            aiplatform.init(project=self.project_id, location=self.location)
            
            # Find or create corpus
            if self.corpus_name:
                self._corpus = rag.get_corpus(name=self.corpus_name)
            else:
                # List existing corpora
                corpora = rag.list_corpora()
                for corpus in corpora:
                    if corpus.display_name == CORPUS_DISPLAY_NAME:
                        self._corpus = corpus
                        self.corpus_name = corpus.name
                        break
                
                # Create if not found
                if not self._corpus:
                    logger.info(f"Creating new RAG corpus: {CORPUS_DISPLAY_NAME}")
                    self._corpus = rag.create_corpus(display_name=CORPUS_DISPLAY_NAME)
                    self.corpus_name = self._corpus.name

            self._initialized = True
            logger.info(f"Vertex AI RAG initialized: {self.corpus_name}")
            return True

        except ImportError:
            logger.warning("Vertex AI SDK not available - using local fallback")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI RAG: {e}")
            return False

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a document to the RAG corpus.
        
        Args:
            content: Document text content
            metadata: Optional metadata (date, type, symbol, etc.)
            document_id: Optional unique ID for the document
            
        Returns:
            Result dict with success status and document info
        """
        if not document_id:
            document_id = f"doc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Always save locally as backup
        local_result = self._save_local(content, metadata, document_id)

        # Try Vertex AI
        if self._ensure_initialized():
            try:
                from vertexai import rag

                # Create inline document
                rag_file = rag.upload_file(
                    corpus_name=self.corpus_name,
                    path=None,  # Inline content
                    display_name=document_id,
                    description=json.dumps(metadata) if metadata else None,
                )
                
                logger.info(f"Added document to Vertex AI RAG: {document_id}")
                return {
                    "success": True,
                    "document_id": document_id,
                    "rag_file": rag_file.name,
                    "local_backup": local_result.get("path"),
                }

            except Exception as e:
                logger.error(f"Vertex AI upload failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "local_backup": local_result.get("path"),
                }

        return {
            "success": True,
            "document_id": document_id,
            "mode": "local_only",
            "local_backup": local_result.get("path"),
        }

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        min_relevance: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Query the RAG corpus for relevant documents.
        
        Args:
            query_text: Natural language query
            top_k: Maximum number of results
            min_relevance: Minimum relevance score (0-1)
            
        Returns:
            List of relevant documents with content and metadata
        """
        results = []

        # Try Vertex AI first
        if self._ensure_initialized():
            try:
                from vertexai import rag
                from vertexai.generative_models import GenerativeModel

                # Use RAG retrieval
                rag_retrieval = rag.Retrieval(
                    source=rag.VertexRagStore(
                        rag_corpora=[self.corpus_name],
                        similarity_top_k=top_k,
                    ),
                )

                # Query with Gemini
                model = GenerativeModel(
                    "gemini-2.0-flash-exp",
                    tools=[rag_retrieval],
                )

                response = model.generate_content(query_text)
                
                # Parse grounding metadata
                if hasattr(response, "candidates") and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, "grounding_metadata"):
                            for chunk in candidate.grounding_metadata.grounding_chunks:
                                results.append({
                                    "content": chunk.retrieved_context.text,
                                    "relevance": chunk.relevance_score,
                                    "source": "vertex_ai",
                                })

                logger.info(f"Vertex AI RAG query returned {len(results)} results")

            except Exception as e:
                logger.warning(f"Vertex AI query failed: {e}, using local fallback")

        # Fallback to local search
        if not results:
            results = self._search_local(query_text, top_k)

        # Filter by relevance
        return [r for r in results if r.get("relevance", 1.0) >= min_relevance]

    def sync_lessons(self, force: bool = False) -> dict[str, Any]:
        """Sync all local lessons to Vertex AI RAG.
        
        Args:
            force: If True, re-sync all lessons even if already synced
            
        Returns:
            Summary of sync operation
        """
        synced = 0
        failed = 0
        skipped = 0

        if not LOCAL_LESSONS_PATH.exists():
            return {"error": "Lessons directory not found", "synced": 0}

        for lesson_file in LOCAL_LESSONS_PATH.glob("ll_*.md"):
            try:
                content = lesson_file.read_text()
                metadata = {
                    "type": "lesson_learned",
                    "filename": lesson_file.name,
                    "date": datetime.now(timezone.utc).isoformat(),
                }

                result = self.add_document(
                    content=content,
                    metadata=metadata,
                    document_id=lesson_file.stem,
                )

                if result.get("success"):
                    synced += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to sync {lesson_file}: {e}")
                failed += 1

        return {
            "synced": synced,
            "failed": failed,
            "skipped": skipped,
            "total": synced + failed + skipped,
        }

    def get_pretrade_advice(
        self,
        symbol: str,
        strategy: str = "phil_town_csp",
    ) -> dict[str, Any]:
        """Get pre-trade advice from RAG lessons.
        
        Args:
            symbol: Trading symbol (e.g., "SOFI", "F")
            strategy: Strategy name
            
        Returns:
            Advice dict with recommendations and warnings
        """
        query = f"""
        What lessons have we learned about trading {symbol}?
        What should I watch out for when using the {strategy} strategy?
        Are there any past mistakes or warnings I should know?
        """

        results = self.query(query, top_k=5)

        advice = {
            "symbol": symbol,
            "strategy": strategy,
            "lessons": [],
            "warnings": [],
            "recommendations": [],
        }

        for result in results:
            content = result.get("content", "")
            
            # Extract warnings
            if "warning" in content.lower() or "mistake" in content.lower():
                advice["warnings"].append(content[:500])
            
            # Extract recommendations
            if "should" in content.lower() or "recommend" in content.lower():
                advice["recommendations"].append(content[:500])
            
            advice["lessons"].append({
                "content": content[:200],
                "relevance": result.get("relevance", 0),
            })

        return advice

    def _save_local(
        self,
        content: str,
        metadata: dict[str, Any] | None,
        document_id: str,
    ) -> dict[str, Any]:
        """Save document locally as JSON backup."""
        try:
            backup_dir = LOCAL_TRADES_PATH / "rag_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)

            doc = {
                "id": document_id,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            path = backup_dir / f"{document_id}.json"
            with open(path, "w") as f:
                json.dump(doc, f, indent=2)

            return {"success": True, "path": str(path)}

        except Exception as e:
            logger.error(f"Local backup failed: {e}")
            return {"success": False, "error": str(e)}

    def _search_local(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search local lessons using keyword matching."""
        results = []
        query_words = set(query.lower().split())

        # Search lesson files
        if LOCAL_LESSONS_PATH.exists():
            for lesson_file in LOCAL_LESSONS_PATH.glob("ll_*.md"):
                try:
                    content = lesson_file.read_text()
                    content_words = set(content.lower().split())
                    
                    # Simple relevance scoring
                    overlap = len(query_words & content_words)
                    relevance = overlap / len(query_words) if query_words else 0

                    if relevance > 0.1:
                        results.append({
                            "content": content[:1000],
                            "relevance": min(relevance, 1.0),
                            "source": "local",
                            "file": lesson_file.name,
                        })

                except Exception as e:
                    logger.warning(f"Error reading {lesson_file}: {e}")

        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:top_k]


# Convenience functions for scripts
def get_rag_client() -> VertexRAG:
    """Get a configured VertexRAG client."""
    return VertexRAG()


def sync_trade_to_rag(trade: dict[str, Any]) -> dict[str, Any]:
    """Sync a single trade to RAG."""
    client = get_rag_client()
    
    content = f"""
    Trade Record:
    Symbol: {trade.get('symbol')}
    Type: {trade.get('type')}
    Side: {trade.get('side')}
    Quantity: {trade.get('qty')}
    Price: {trade.get('price')}
    P/L: {trade.get('pnl', 'N/A')}
    Date: {trade.get('timestamp')}
    Notes: {trade.get('notes', '')}
    """
    
    return client.add_document(
        content=content,
        metadata={
            "type": "trade",
            "symbol": trade.get("symbol"),
            "pnl": trade.get("pnl"),
        },
        document_id=f"trade_{trade.get('symbol')}_{trade.get('timestamp', '')[:10]}",
    )


def query_lessons(query: str) -> list[dict[str, Any]]:
    """Query lessons from RAG."""
    client = get_rag_client()
    return client.query(query)
