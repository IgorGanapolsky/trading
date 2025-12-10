"""
Training Library Collector - Curated Quant/Trading Knowledge Ingestion

Ingests high-value trading knowledge sources into the RAG system:
1. Academic papers (López de Prado, AQR, etc.)
2. Trading books (Carver, Antonacci, etc.)
3. Newsletters (Alpha Architect, Quantified Strategies, etc.)
4. YouTube transcripts (Chat With Traders, tastytrade, etc.)

Based on proven edge-to-money ratio sources for systematic trading.
"""

# Import base_collector directly to avoid triggering __init__.py's imports
import importlib.util as _importlib_util
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

_spec = _importlib_util.spec_from_file_location(
    "base_collector",
    Path(__file__).parent / "base_collector.py",
)
_base_module = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_base_module)
BaseNewsCollector = _base_module.BaseNewsCollector

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeChunk:
    """A chunk of trading knowledge with rich metadata."""

    source_type: str  # 'book', 'paper', 'newsletter', 'youtube', 'blog'
    source_name: str  # e.g., "Advances in Financial ML"
    author: str
    chapter_or_section: str
    page_or_timestamp: str
    content: str
    content_type: str  # 'concept', 'formula', 'strategy', 'example', 'warning', 'code'
    topics: list[str]
    edge_category: str  # 'backtest', 'position_sizing', 'regime', 'momentum', 'options', 'risk'
    citation: str  # For ThesisGenerator to cite


# Canonical trading books with proven edge
CANONICAL_BOOKS = {
    "afml": {
        "title": "Advances in Financial Machine Learning",
        "author": "Marcos López de Prado",
        "year": 2018,
        "edge_categories": ["backtest", "feature_engineering", "ml", "cross_validation"],
        "key_concepts": [
            "triple_barrier_method",
            "purged_kfold",
            "meta_labeling",
            "feature_importance",
            "fractionally_differentiated_features",
            "structural_breaks",
        ],
    },
    "systematic_trading": {
        "title": "Systematic Trading",
        "author": "Robert Carver",
        "year": 2015,
        "edge_categories": ["position_sizing", "volatility_targeting", "regime", "risk"],
        "key_concepts": [
            "volatility_targeting",
            "position_sizing",
            "instrument_diversification",
            "forecast_weights",
            "regime_switching",
            "expected_shortfall",
        ],
    },
    "dual_momentum": {
        "title": "Dual Momentum Investing",
        "author": "Gary Antonacci",
        "year": 2014,
        "edge_categories": ["momentum", "trend", "asset_allocation"],
        "key_concepts": [
            "absolute_momentum",
            "relative_momentum",
            "global_equity_momentum",
            "momentum_crashes",
            "trend_following",
        ],
    },
    "quantitative_trading": {
        "title": "Quantitative Trading",
        "author": "Ernest Chan",
        "year": 2021,
        "edge_categories": ["stat_arb", "mean_reversion", "pairs", "execution"],
        "key_concepts": [
            "mean_reversion",
            "pairs_trading",
            "cointegration",
            "sharpe_ratio",
            "kelly_criterion",
            "transaction_costs",
        ],
    },
    "ivy_portfolio": {
        "title": "The Ivy Portfolio",
        "author": "Mebane Faber",
        "year": 2011,
        "edge_categories": ["risk_parity", "trend", "asset_allocation"],
        "key_concepts": [
            "risk_parity",
            "trend_following",
            "tactical_allocation",
            "sma_timing",
            "ivy_endowment",
        ],
    },
}

# Key research papers
RESEARCH_PAPERS = {
    "101_alphas": {
        "title": "101 Formulaic Alphas",
        "authors": "Kakushadze & Tulchinsky",
        "year": 2016,
        "edge_categories": ["alpha_generation", "feature_engineering"],
        "key_concepts": ["formulaic_alphas", "alpha_decay", "alpha_combination"],
    },
    "time_series_momentum": {
        "title": "Time-Series Momentum",
        "authors": "AQR (Moskowitz, Ooi, Pedersen)",
        "year": 2012,
        "edge_categories": ["momentum", "trend", "futures"],
        "key_concepts": ["trend_following", "momentum_everywhere", "carry"],
    },
    "value_momentum_everywhere": {
        "title": "Value and Momentum Everywhere",
        "authors": "AQR (Asness, Moskowitz, Pedersen)",
        "year": 2013,
        "edge_categories": ["momentum", "value", "factor_investing"],
        "key_concepts": ["global_momentum", "value_factor", "factor_correlation"],
    },
    "ml_asset_managers": {
        "title": "Machine Learning for Asset Managers",
        "author": "Marcos López de Prado",
        "year": 2020,
        "edge_categories": ["ml", "meta_labeling", "feature_selection"],
        "key_concepts": ["meta_labeling", "feature_importance", "clustering_features"],
    },
}

# High-signal newsletters
NEWSLETTERS = {
    "alpha_architect": {
        "name": "Alpha Architect",
        "url": "https://alphaarchitect.com/blog/",
        "frequency": "weekly",
        "edge_categories": ["empirical_research", "factor_investing", "momentum"],
        "focus": "Academic research summaries, factor investing",
    },
    "quantified_strategies": {
        "name": "Quantified Strategies",
        "url": "https://www.quantifiedstrategies.com/",
        "frequency": "weekly",
        "edge_categories": ["backtested_strategies", "mean_reversion", "trend"],
        "focus": "200+ backtested strategies with Python code",
    },
    "flirting_with_models": {
        "name": "Flirting with Models",
        "author": "Corey Hoffstein",
        "url": "https://blog.thinknewfound.com/",
        "frequency": "bi-weekly",
        "edge_categories": ["risk_parity", "trend", "volatility_targeting"],
        "focus": "Risk parity, trend following, volatility management",
    },
    "moontower": {
        "name": "Moontower",
        "author": "Kris Abdelmessih",
        "url": "https://moontowermeta.com/",
        "frequency": "weekly",
        "edge_categories": ["options", "volatility", "market_making"],
        "focus": "Options trading floor wisdom, volatility trading",
    },
}


class TrainingLibraryCollector(BaseNewsCollector):
    """
    Collect and index curated trading knowledge for RAG.

    This collector handles:
    1. Pre-chunked knowledge from canonical books
    2. Research paper summaries
    3. Newsletter content scraping
    4. YouTube transcript processing

    All content is tagged with citation metadata for ThesisGenerator.
    """

    def __init__(self, cache_dir: str | None = None):
        """Initialize training library collector."""
        super().__init__(source_name="training_library")

        if cache_dir is None:
            cache_dir = "rag_knowledge"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.books_dir = self.cache_dir / "books"
        self.papers_dir = self.cache_dir / "papers"
        self.newsletters_dir = self.cache_dir / "newsletters"
        self.youtube_dir = self.cache_dir / "youtube_transcripts"
        self.blogs_dir = self.cache_dir / "blogs"
        self.chunks_dir = self.cache_dir / "chunks"

        for dir_path in [
            self.books_dir,
            self.papers_dir,
            self.newsletters_dir,
            self.youtube_dir,
            self.blogs_dir,
            self.chunks_dir,
        ]:
            dir_path.mkdir(exist_ok=True)

        # Index of all ingested knowledge
        self.index_file = self.cache_dir / "knowledge_index.json"
        self.index = self._load_index()

        logger.info(f"Training Library Collector initialized (cache: {self.cache_dir})")

    def _load_index(self) -> dict[str, Any]:
        """Load knowledge index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading index: {e}")
                return {"books": {}, "papers": {}, "newsletters": {}, "youtube": {}}
        return {"books": {}, "papers": {}, "newsletters": {}, "youtube": {}}

    def _save_index(self):
        """Save knowledge index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
            logger.info("Saved knowledge index")
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def ingest_book_summary(self, book_id: str, chapters: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Ingest pre-summarized book content.

        Args:
            book_id: Book identifier (e.g., 'afml', 'systematic_trading')
            chapters: List of chapter dicts with 'title', 'summary', 'key_points', 'formulas'

        Returns:
            Ingestion status and stats
        """
        if book_id not in CANONICAL_BOOKS:
            return {"status": "error", "message": f"Unknown book: {book_id}"}

        book_meta = CANONICAL_BOOKS[book_id]
        chunks = []

        for chapter in chapters:
            # Create chunk for chapter summary
            summary_chunk = KnowledgeChunk(
                source_type="book",
                source_name=book_meta["title"],
                author=book_meta["author"],
                chapter_or_section=chapter.get("title", "Unknown Chapter"),
                page_or_timestamp=chapter.get("pages", ""),
                content=chapter.get("summary", ""),
                content_type="concept",
                topics=chapter.get("topics", []),
                edge_category=self._classify_edge_category(
                    chapter.get("summary", ""), book_meta["edge_categories"]
                ),
                citation=f'{book_meta["author"]} ({book_meta["year"]}), "{book_meta["title"]}", Ch. {chapter.get("chapter_num", "?")}',
            )
            chunks.append(summary_chunk)

            # Create chunks for key points
            for i, point in enumerate(chapter.get("key_points", [])):
                point_chunk = KnowledgeChunk(
                    source_type="book",
                    source_name=book_meta["title"],
                    author=book_meta["author"],
                    chapter_or_section=chapter.get("title", "Unknown"),
                    page_or_timestamp=chapter.get("pages", ""),
                    content=point,
                    content_type="rule"
                    if "always" in point.lower() or "never" in point.lower()
                    else "concept",
                    topics=chapter.get("topics", []),
                    edge_category=self._classify_edge_category(point, book_meta["edge_categories"]),
                    citation=f"{book_meta['author']} ({book_meta['year']}), Ch. {chapter.get('chapter_num', '?')}",
                )
                chunks.append(point_chunk)

            # Create chunks for formulas
            for formula in chapter.get("formulas", []):
                formula_chunk = KnowledgeChunk(
                    source_type="book",
                    source_name=book_meta["title"],
                    author=book_meta["author"],
                    chapter_or_section=chapter.get("title", "Unknown"),
                    page_or_timestamp=chapter.get("pages", ""),
                    content=f"{formula.get('name', 'Formula')}: {formula.get('expression', '')}\n\nExplanation: {formula.get('explanation', '')}",
                    content_type="formula",
                    topics=chapter.get("topics", []) + ["quantitative"],
                    edge_category=self._classify_edge_category(
                        formula.get("name", ""), book_meta["edge_categories"]
                    ),
                    citation=f"{book_meta['author']} ({book_meta['year']}), {formula.get('name', 'Formula')}",
                )
                chunks.append(formula_chunk)

        # Save chunks
        chunks_file = self.chunks_dir / f"{book_id}_chunks.json"
        with open(chunks_file, "w") as f:
            json.dump([asdict(c) for c in chunks], f, indent=2)

        # Update index
        self.index["books"][book_id] = {
            "title": book_meta["title"],
            "author": book_meta["author"],
            "chunks_file": str(chunks_file),
            "chunk_count": len(chunks),
            "ingested_at": datetime.now().isoformat(),
        }
        self._save_index()

        logger.info(f"Ingested {len(chunks)} chunks from {book_meta['title']}")
        return {"status": "success", "book_id": book_id, "chunks": len(chunks)}

    def _classify_edge_category(self, text: str, default_categories: list[str]) -> str:
        """Classify content by edge category."""
        text_lower = text.lower()

        category_keywords = {
            "backtest": ["backtest", "walk-forward", "out-of-sample", "overfit", "leakage"],
            "position_sizing": ["position size", "kelly", "risk per trade", "volatility target"],
            "regime": ["regime", "market state", "bull", "bear", "crisis", "drawdown"],
            "momentum": ["momentum", "trend", "moving average", "breakout", "relative strength"],
            "options": ["option", "volatility", "greek", "delta", "gamma", "theta", "vega"],
            "risk": ["risk", "var", "cvar", "drawdown", "correlation", "diversification"],
            "ml": ["machine learning", "feature", "model", "prediction", "classification"],
            "mean_reversion": ["mean reversion", "pairs", "cointegration", "spread"],
        }

        scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return default_categories[0] if default_categories else "general"

    def get_chunks_for_rag(
        self,
        source_type: str | None = None,
        edge_category: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all chunks formatted for RAG ingestion.

        Args:
            source_type: Filter by source type (book, paper, newsletter, youtube)
            edge_category: Filter by edge category (backtest, momentum, etc.)

        Returns:
            List of chunks ready for vector store
        """
        all_chunks = []

        # Process books
        for book_id, book_info in self.index.get("books", {}).items():
            chunks_file = Path(book_info["chunks_file"])
            if not chunks_file.exists():
                continue

            with open(chunks_file) as f:
                chunks = json.load(f)

            for i, chunk in enumerate(chunks):
                # Apply filters
                if source_type and chunk["source_type"] != source_type:
                    continue
                if edge_category and chunk["edge_category"] != edge_category:
                    continue

                all_chunks.append(
                    {
                        "id": f"{book_id}_chunk_{i}",
                        "content": chunk["content"],
                        "metadata": {
                            "source_type": chunk["source_type"],
                            "source_name": chunk["source_name"],
                            "author": chunk["author"],
                            "chapter": chunk["chapter_or_section"],
                            "content_type": chunk["content_type"],
                            "edge_category": chunk["edge_category"],
                            "citation": chunk["citation"],
                            "topics": ",".join(chunk["topics"]),
                            "source": "training_library",
                        },
                    }
                )

        # Process papers
        for paper_id, paper_info in self.index.get("papers", {}).items():
            chunks_file = Path(paper_info.get("chunks_file", ""))
            if not chunks_file.exists():
                continue

            with open(chunks_file) as f:
                chunks = json.load(f)

            for i, chunk in enumerate(chunks):
                if source_type and chunk["source_type"] != source_type:
                    continue
                if edge_category and chunk["edge_category"] != edge_category:
                    continue

                all_chunks.append(
                    {
                        "id": f"{paper_id}_chunk_{i}",
                        "content": chunk["content"],
                        "metadata": {
                            "source_type": chunk["source_type"],
                            "source_name": chunk["source_name"],
                            "author": chunk["author"],
                            "content_type": chunk["content_type"],
                            "edge_category": chunk["edge_category"],
                            "citation": chunk["citation"],
                            "topics": ",".join(chunk["topics"]),
                            "source": "training_library",
                        },
                    }
                )

        return all_chunks

    def search(
        self,
        query: str,
        source_type: str | None = None,
        edge_category: str | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """
        Search training library for relevant knowledge.

        Args:
            query: Search query
            source_type: Filter by source type
            edge_category: Filter by edge category
            top_k: Number of results

        Returns:
            Search results with citations
        """
        chunks = self.get_chunks_for_rag(source_type, edge_category)

        if not chunks:
            return {
                "query": query,
                "results": [],
                "message": "No knowledge ingested yet. Use ingest_* methods first.",
            }

        # Simple keyword scoring (will be replaced by vector search when integrated)
        query_words = set(query.lower().split())
        scored_results = []

        for chunk in chunks:
            content_words = set(chunk["content"].lower().split())
            score = len(query_words & content_words) / len(query_words) if query_words else 0

            if score > 0:
                scored_results.append(
                    {
                        "content": chunk["content"][:500] + "..."
                        if len(chunk["content"]) > 500
                        else chunk["content"],
                        "citation": chunk["metadata"]["citation"],
                        "source_name": chunk["metadata"]["source_name"],
                        "edge_category": chunk["metadata"]["edge_category"],
                        "score": score,
                    }
                )

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "results": scored_results[:top_k],
            "total_matches": len(scored_results),
        }

    # Implement abstract methods from BaseNewsCollector
    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """Training library doesn't have ticker-specific content."""
        return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """Return training library content as market context."""
        chunks = self.get_chunks_for_rag()

        articles = []
        for chunk in chunks[:50]:  # Limit to 50 chunks
            article = self.normalize_article(
                title=f"{chunk['metadata']['source_name']} - {chunk['metadata']['chapter']}",
                content=chunk["content"],
                url=f"library://{chunk['id']}",
                published_date=datetime.now().strftime("%Y-%m-%d"),
                ticker=None,
                sentiment=None,
            )
            articles.append(article)

        return articles


def get_training_library_collector() -> TrainingLibraryCollector:
    """Get TrainingLibraryCollector instance."""
    return TrainingLibraryCollector()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = TrainingLibraryCollector()

    print("Training Library Collector initialized")
    print(f"Cache directory: {collector.cache_dir}")
    print(f"\nCanonical books available: {list(CANONICAL_BOOKS.keys())}")
    print(f"Research papers available: {list(RESEARCH_PAPERS.keys())}")
    print(f"Newsletters available: {list(NEWSLETTERS.keys())}")

    if collector.index.get("books"):
        print(f"\nIngested books: {list(collector.index['books'].keys())}")
    else:
        print("\nNo books ingested yet.")
