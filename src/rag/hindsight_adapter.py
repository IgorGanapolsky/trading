"""
Hindsight Agentic Memory Adapter

Provides graceful integration with Vectorize Hindsight memory system.
Falls back to local lessons_learned_rag.py if Hindsight is unavailable.

Key Features:
1. Three-tier fallback: Hindsight API -> Local RAG -> Keyword search
2. Non-blocking failures (warnings, not errors)
3. Health checks before trade operations
4. Automatic memory bank management per trading context

Memory Banks:
- trading-lessons: Past trade outcomes and lessons learned
- market-observations: Factual market data and patterns
- trade-opinions: Confidence-scored beliefs about tickers/strategies

Author: Trading System CTO
Created: 2025-12-16
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Module-level availability detection (following lessons_learned_rag.py pattern)
# ============================================================================

HINDSIGHT_AVAILABLE = False
HINDSIGHT_CLIENT_CLASS = None

# Try to import hindsight-client
try:
    from hindsight_client import Hindsight

    HINDSIGHT_CLIENT_CLASS = Hindsight
    logger.info("hindsight-client package available")
except ImportError:
    logger.debug("hindsight-client not installed - will use local RAG fallback")

# Check if Hindsight service URL is configured
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "http://localhost:8888")


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class HindsightHealthResult:
    """Result of Hindsight health check."""

    available: bool
    client_installed: bool
    service_reachable: bool
    api_healthy: bool
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def should_use_hindsight(self) -> bool:
        """Return True if Hindsight is fully operational."""
        return self.available and self.service_reachable and self.api_healthy


@dataclass
class MemoryResult:
    """Result from memory operations."""

    success: bool
    source: str  # "hindsight", "local_rag", "keyword"
    data: Any = None
    confidence: Optional[float] = None
    error: Optional[str] = None


# ============================================================================
# Memory Bank Configuration
# ============================================================================

MEMORY_BANKS = {
    "trading-lessons": {
        "description": "Past trade outcomes, mistakes, and lessons learned",
        "disposition": {"skepticism": 3, "literalism": 4, "empathy": 2},
    },
    "market-observations": {
        "description": "Factual market data, patterns, and events",
        "disposition": {"skepticism": 2, "literalism": 5, "empathy": 1},
    },
    "trade-opinions": {
        "description": "Beliefs about tickers and strategies with confidence scores",
        "disposition": {"skepticism": 4, "literalism": 2, "empathy": 3},
    },
}


# ============================================================================
# Hindsight Adapter Class
# ============================================================================


class HindsightAdapter:
    """
    Adapter for Hindsight agentic memory with graceful degradation.

    Follows the three-tier fallback pattern from lessons_learned_rag.py:
    1. Hindsight API (if service running)
    2. Local RAG (lessons_learned_rag.py)
    3. Keyword search (final fallback)
    """

    def __init__(
        self,
        base_url: str = HINDSIGHT_BASE_URL,
        auto_init: bool = True,
    ):
        """
        Initialize Hindsight adapter.

        Args:
            base_url: Hindsight API URL (default: http://localhost:8888)
            auto_init: Whether to initialize client immediately
        """
        self.base_url = base_url
        self._client: Optional[Any] = None
        self._hindsight_enabled = False
        self._local_rag: Optional[Any] = None
        self._local_rag_enabled = False
        self._health_result: Optional[HindsightHealthResult] = None

        if auto_init:
            self._init_hindsight()
            self._init_local_fallback()

    def _init_hindsight(self) -> None:
        """Initialize Hindsight client if available."""
        if HINDSIGHT_CLIENT_CLASS is None:
            logger.debug("Hindsight client not installed, skipping init")
            return

        try:
            self._client = HINDSIGHT_CLIENT_CLASS(base_url=self.base_url)
            # Test connection with a simple operation
            # Note: This is a lightweight check, not a full health check
            self._hindsight_enabled = True
            logger.info(f"Hindsight client initialized: {self.base_url}")
        except Exception as e:
            logger.warning(f"Failed to initialize Hindsight client: {e}")
            self._hindsight_enabled = False

    def _init_local_fallback(self) -> None:
        """Initialize local RAG as fallback."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self._local_rag = LessonsLearnedRAG()
            self._local_rag_enabled = True
            logger.info("Local RAG fallback initialized")
        except Exception as e:
            logger.warning(f"Local RAG fallback not available: {e}")
            self._local_rag_enabled = False

    # ========================================================================
    # Health Check
    # ========================================================================

    def check_health(self) -> HindsightHealthResult:
        """
        Perform comprehensive health check.

        Returns:
            HindsightHealthResult with detailed status
        """
        errors: list[str] = []

        # Step 1: Check if client is installed
        client_installed = HINDSIGHT_CLIENT_CLASS is not None
        if not client_installed:
            errors.append("hindsight-client package not installed")

        # Step 2: Check if service is reachable
        service_reachable = False
        api_healthy = False

        if client_installed and self._client is not None:
            try:
                import httpx

                response = httpx.get(f"{self.base_url}/health", timeout=5.0)
                service_reachable = response.status_code == 200
                if not service_reachable:
                    errors.append(
                        f"Hindsight health endpoint returned {response.status_code}"
                    )
                else:
                    api_healthy = True
            except httpx.ConnectError:
                errors.append(f"Cannot connect to Hindsight at {self.base_url}")
            except httpx.TimeoutException:
                errors.append("Hindsight health check timed out")
            except Exception as e:
                errors.append(f"Hindsight health check failed: {e}")

        # Build result
        available = client_installed and service_reachable and api_healthy
        self._health_result = HindsightHealthResult(
            available=available,
            client_installed=client_installed,
            service_reachable=service_reachable,
            api_healthy=api_healthy,
            errors=errors,
        )

        # Log result
        if available:
            logger.info("Hindsight health check: HEALTHY")
        else:
            logger.warning(f"Hindsight health check: DEGRADED - {errors}")

        return self._health_result

    # ========================================================================
    # Core Operations: Retain, Recall, Reflect
    # ========================================================================

    def retain(
        self,
        content: str,
        bank_id: str = "trading-lessons",
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryResult:
        """
        Store information in memory.

        Falls back to local RAG if Hindsight unavailable.

        Args:
            content: The information to remember
            bank_id: Which memory bank to use
            metadata: Optional metadata (symbol, timestamp, etc.)

        Returns:
            MemoryResult indicating success and source
        """
        # Try Hindsight first
        if self._hindsight_enabled and self._client is not None:
            try:
                self._client.retain(bank_id=bank_id, content=content)
                logger.debug(f"Retained in Hindsight [{bank_id}]: {content[:50]}...")
                return MemoryResult(success=True, source="hindsight")
            except Exception as e:
                logger.warning(f"Hindsight retain failed, falling back: {e}")

        # Fallback to local RAG
        if self._local_rag_enabled and self._local_rag is not None:
            try:
                # Convert to lesson format for local RAG
                from src.rag.lessons_learned_rag import Lesson

                lesson = Lesson(
                    id=f"hs_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    category=bank_id,
                    title=content[:50],
                    description=content,
                    root_cause="",
                    prevention="",
                    tags=list(metadata.keys()) if metadata else [],
                    severity="medium",
                )
                self._local_rag.add_lesson(lesson)
                logger.debug(f"Retained in local RAG [{bank_id}]: {content[:50]}...")
                return MemoryResult(success=True, source="local_rag")
            except Exception as e:
                logger.warning(f"Local RAG retain failed: {e}")

        # Final fallback: just log it
        logger.info(f"Memory retained (log only) [{bank_id}]: {content[:100]}")
        return MemoryResult(
            success=False,
            source="none",
            error="No memory backend available",
        )

    def recall(
        self,
        query: str,
        bank_id: str = "trading-lessons",
        n_results: int = 5,
    ) -> MemoryResult:
        """
        Search for relevant memories.

        Falls back to local RAG if Hindsight unavailable.

        Args:
            query: What to search for
            bank_id: Which memory bank to search
            n_results: Maximum number of results

        Returns:
            MemoryResult with search results
        """
        # Try Hindsight first
        if self._hindsight_enabled and self._client is not None:
            try:
                results = self._client.recall(bank_id=bank_id, query=query)
                logger.debug(f"Recalled from Hindsight [{bank_id}]: {query[:50]}...")
                return MemoryResult(success=True, source="hindsight", data=results)
            except Exception as e:
                logger.warning(f"Hindsight recall failed, falling back: {e}")

        # Fallback to local RAG
        if self._local_rag_enabled and self._local_rag is not None:
            try:
                results = self._local_rag.search(query=query, top_k=n_results)
                logger.debug(f"Recalled from local RAG: {query[:50]}...")
                return MemoryResult(success=True, source="local_rag", data=results)
            except Exception as e:
                logger.warning(f"Local RAG recall failed: {e}")

        return MemoryResult(
            success=False,
            source="none",
            error="No memory backend available",
        )

    def reflect(
        self,
        query: str,
        bank_id: str = "trading-lessons",
    ) -> MemoryResult:
        """
        Reason over memories to generate insights with confidence scores.

        This is Hindsight-specific. Falls back to basic recall for local RAG.

        Args:
            query: What to reflect on
            bank_id: Which memory bank to use

        Returns:
            MemoryResult with insights and confidence
        """
        # Reflect is Hindsight-specific
        if self._hindsight_enabled and self._client is not None:
            try:
                results = self._client.reflect(bank_id=bank_id, query=query)
                logger.debug(f"Reflected in Hindsight [{bank_id}]: {query[:50]}...")
                return MemoryResult(
                    success=True,
                    source="hindsight",
                    data=results,
                    confidence=results.get("confidence") if isinstance(results, dict) else None,
                )
            except Exception as e:
                logger.warning(f"Hindsight reflect failed, falling back: {e}")

        # Fallback: just do recall (no confidence scoring)
        result = self.recall(query=query, bank_id=bank_id)
        if result.success:
            result.source = f"{result.source}_degraded"
            logger.info("Reflect degraded to recall (no confidence scoring)")
        return result

    # ========================================================================
    # Trading-Specific Convenience Methods
    # ========================================================================

    def remember_trade_outcome(
        self,
        symbol: str,
        side: str,
        outcome: str,
        pnl: float,
        lesson: str,
    ) -> MemoryResult:
        """
        Store a trade outcome for future learning.

        Args:
            symbol: Ticker symbol (e.g., "SPY")
            side: "buy" or "sell"
            outcome: "win" or "loss"
            pnl: Profit/loss amount
            lesson: What was learned

        Returns:
            MemoryResult
        """
        content = (
            f"Trade on {symbol} ({side}): {outcome} with P/L ${pnl:.2f}. "
            f"Lesson: {lesson}"
        )
        return self.retain(
            content=content,
            bank_id="trading-lessons",
            metadata={"symbol": symbol, "side": side, "outcome": outcome, "pnl": pnl},
        )

    def check_similar_trades(
        self,
        symbol: str,
        strategy: str,
        n_results: int = 5,
    ) -> MemoryResult:
        """
        Check for similar past trades before executing.

        Args:
            symbol: Ticker symbol
            strategy: Strategy being considered
            n_results: Max results to return

        Returns:
            MemoryResult with similar trade history
        """
        query = f"What happened when I traded {symbol} using {strategy}?"
        return self.recall(query=query, bank_id="trading-lessons", n_results=n_results)

    def get_ticker_opinion(self, symbol: str) -> MemoryResult:
        """
        Get current opinion/belief about a ticker with confidence score.

        Args:
            symbol: Ticker symbol

        Returns:
            MemoryResult with opinion and confidence
        """
        query = f"What do I believe about {symbol}? What is my conviction?"
        return self.reflect(query=query, bank_id="trade-opinions")


# ============================================================================
# Module-level convenience functions
# ============================================================================

_adapter_instance: Optional[HindsightAdapter] = None


def get_hindsight_adapter() -> HindsightAdapter:
    """Get or create singleton adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = HindsightAdapter()
    return _adapter_instance


def check_hindsight_health() -> HindsightHealthResult:
    """Check Hindsight health (convenience function)."""
    return get_hindsight_adapter().check_health()


def is_hindsight_available() -> bool:
    """Quick check if Hindsight is available."""
    adapter = get_hindsight_adapter()
    if adapter._health_result is None:
        adapter.check_health()
    return adapter._health_result.should_use_hindsight if adapter._health_result else False
