"""
GraphRAG Lite: Simple Knowledge Graph for Financial Entities.

Uses NetworkX to model relationships between tickers and concepts based on co-occurrence
in news articles.

Features:
- Builds graph from document text
- Tracks edge weights (frequency of co-occurrence)
- Finds related entities (e.g., "Competitors of NVDA")
- Persists to disk
"""

import json
import logging
import os
import re

import networkx as nx

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    Lightweight Knowledge Graph using NetworkX.
    """

    def __init__(self, persist_path: str = "data/rag/knowledge_graph.json"):
        self.graph = nx.Graph()
        self.persist_path = persist_path
        self.known_tickers = set()  # Cache of tickers to look for

        # Ensure directory exists
        os.makedirs(os.path.dirname(persist_path), exist_ok=True)

        # Load existing graph
        self.load_graph()

    def add_document(self, text: str, source_ticker: str = None):
        """
        Process a document and update the graph.

        Args:
            text: Content of the article
            source_ticker: The primary ticker this article is about (optional)
        """
        # 1. Extract entities (Tickers)
        # Simple heuristic: Look for ALL CAPS words that match known tickers
        # In a real system, we'd use a proper NER model (Spacy/Bert)
        found_tickers = self._extract_tickers(text)

        if source_ticker:
            found_tickers.add(source_ticker)

        # 2. Update Graph
        # Create edges between all co-occurring tickers
        tickers_list = list(found_tickers)
        for i in range(len(tickers_list)):
            t1 = tickers_list[i]
            if not self.graph.has_node(t1):
                self.graph.add_node(t1, type="ticker")

            for j in range(i + 1, len(tickers_list)):
                t2 = tickers_list[j]
                if not self.graph.has_node(t2):
                    self.graph.add_node(t2, type="ticker")

                # Add or update edge
                if self.graph.has_edge(t1, t2):
                    self.graph[t1][t2]["weight"] += 1
                else:
                    self.graph.add_edge(t1, t2, weight=1)

        # Auto-save occasionally? For now, we'll rely on explicit save

    def get_related_tickers(self, ticker: str, top_k: int = 5) -> list[tuple[str, int]]:
        """
        Get tickers most strongly connected to the given ticker.

        Returns:
            List of (ticker, weight) tuples
        """
        if not self.graph.has_node(ticker):
            return []

        neighbors = self.graph[ticker]
        # Sort by weight descending
        sorted_neighbors = sorted(neighbors.items(), key=lambda x: x[1]["weight"], reverse=True)

        return [(n, data["weight"]) for n, data in sorted_neighbors[:top_k]]

    def _extract_tickers(self, text: str) -> set:
        """
        Heuristic extraction of tickers.
        """
        # Find all words that look like tickers (2-5 uppercase letters)
        # This is noisy, so we filter by a known universe if possible
        candidates = set(re.findall(r"\b[A-Z]{2,5}\b", text))

        # Filter against a known list if we have one, otherwise just return candidates
        # For this Lite version, we'll assume the caller populates known_tickers
        if self.known_tickers:
            return candidates.intersection(self.known_tickers)

        return candidates

    def set_known_tickers(self, tickers: list[str]):
        """Set the universe of valid tickers to reduce noise."""
        self.known_tickers = set(tickers)

    def save_graph(self):
        """Save graph to disk (node-link format)."""
        try:
            data = nx.node_link_data(self.graph)
            with open(self.persist_path, "w") as f:
                json.dump(data, f)
            logger.info(
                f"Saved Knowledge Graph to {self.persist_path} ({self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges)"
            )
        except Exception as e:
            logger.error(f"Failed to save graph: {e}")

    def load_graph(self):
        """Load graph from disk."""
        if not os.path.exists(self.persist_path):
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)
            self.graph = nx.node_link_graph(data)
            logger.info(f"Loaded Knowledge Graph: {self.graph.number_of_nodes()} nodes")
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")


# Global instance
_KG_INSTANCE = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _KG_INSTANCE
    if _KG_INSTANCE is None:
        _KG_INSTANCE = KnowledgeGraph()
        # Pre-seed with S&P 500 tickers if possible, or just common ones
        # For now, let's add the ones from GrowthStrategy
        common_tickers = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "TSLA",
            "META",
            "AMD",
            "INTC",
            "SPY",
            "QQQ",
        ]
        _KG_INSTANCE.set_known_tickers(common_tickers)
    return _KG_INSTANCE
