"""
Options Book Collector - PDF/EPUB Ingestion for Trading Books

Ingests options trading books for RAG retrieval:
- "Options as a Strategic Investment" by Lawrence McMillan (primary)
- Other options books (secondary)

Based on the proven Berkshire Letters pattern.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


@dataclass
class BookChunk:
    """A chunk of book content with metadata."""

    book_title: str
    author: str
    chapter: str
    section: str
    page_numbers: str
    content: str
    content_type: str  # 'strategy', 'example', 'definition', 'rule', 'warning'
    topics: list[str]


class OptionsBookCollector(BaseNewsCollector):
    """
    Collect and index options trading books for RAG.

    Primary target: "Options as a Strategic Investment" by Lawrence McMillan

    Features:
    - PDF parsing with chapter/section detection
    - Intelligent chunking preserving context
    - Content type classification (strategy, example, definition, etc.)
    - Page number tracking for citations
    - Semantic search across all books
    """

    # Book metadata for known options books
    KNOWN_BOOKS = {
        "mcmillan_options": {
            "title": "Options as a Strategic Investment",
            "author": "Lawrence G. McMillan",
            "edition": "5th Edition",
            "isbn": "978-0735201972",
            "pages": 1012,
            "topics": [
                "greeks",
                "volatility",
                "covered_calls",
                "iron_condor",
                "straddles",
                "spreads",
                "risk_management",
                "taxes",
            ],
        },
        "natenberg_volatility": {
            "title": "Option Volatility and Pricing",
            "author": "Sheldon Natenberg",
            "edition": "2nd Edition",
            "isbn": "978-0071818773",
            "pages": 512,
            "topics": [
                "volatility_trading",
                "pricing_models",
                "greeks",
                "volatility_skew",
                "risk_management",
            ],
        },
        "sinclair_volatility": {
            "title": "Volatility Trading",
            "author": "Euan Sinclair",
            "edition": "2nd Edition",
            "isbn": "978-1118347133",
            "pages": 384,
            "topics": [
                "volatility_forecasting",
                "trade_sizing",
                "hedging",
                "psychology",
                "variance_swaps",
            ],
        },
    }

    # Chapter patterns for McMillan's book (helps with parsing)
    MCMILLAN_CHAPTERS = {
        1: "Definitions",
        2: "Covered Call Writing",
        3: "Call Buying",
        4: "Other Call Buying Strategies",
        5: "Naked Call Writing",
        6: "Ratio Call Strategies",
        7: "Bull Spreads",
        8: "Bear Spreads",
        9: "Calendar Spreads",
        10: "Butterfly Spreads",
        11: "Ratio Spreads",
        12: "Combinations",
        13: "Put Buying",
        14: "Put Selling",
        15: "Spreads Combining Puts and Calls",
        16: "Straddle Buying",
        17: "Straddle Writing",
        18: "The Strangle",
        19: "Put and Call Combination Strategies",
        20: "Synthetic Stock Strategies",
        21: "Index Options",
        22: "Volatility",
        23: "The Volatility Smile",
        24: "Kurtosis in Stock Prices",
        25: "Taxes",
    }

    # Content type patterns for classification
    CONTENT_PATTERNS = {
        "strategy": [
            r"strategy[:\s]",
            r"setup[:\s]",
            r"trade[:\s]",
            r"position[:\s]",
            r"when to use",
            r"profit potential",
            r"maximum (loss|gain)",
        ],
        "example": [
            r"example[:\s]",
            r"for instance",
            r"consider",
            r"suppose",
            r"let's say",
            r"illustration",
            r"assume that",
        ],
        "definition": [
            r"is defined as",
            r"refers to",
            r"means that",
            r"definition",
            r"^[A-Z][a-z]+ is [a-z]",  # "Delta is the..."
        ],
        "rule": [
            r"rule[:\s]",
            r"always",
            r"never",
            r"must",
            r"should",
            r"critical",
            r"important",
            r"key point",
        ],
        "warning": [
            r"warning",
            r"caution",
            r"danger",
            r"risk",
            r"avoid",
            r"mistake",
            r"trap",
            r"pitfall",
        ],
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize options book collector.

        Args:
            cache_dir: Directory to cache books (default: data/rag/options_books)
        """
        super().__init__(source_name="options_books")

        if cache_dir is None:
            cache_dir = "data/rag/options_books"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.raw_dir = self.cache_dir / "raw"  # Original PDFs
        self.parsed_dir = self.cache_dir / "parsed"  # Extracted text
        self.chunks_dir = self.cache_dir / "chunks"  # Chunked content
        self.index_dir = self.cache_dir / "index"  # Search index

        for dir_path in [self.raw_dir, self.parsed_dir, self.chunks_dir, self.index_dir]:
            dir_path.mkdir(exist_ok=True)

        # Load or create index
        self.index_file = self.index_dir / "books_index.json"
        self.index = self._load_index()

        logger.info(f"Options Book Collector initialized (cache: {self.cache_dir})")

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load the books index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading index: {e}")
                return {}
        return {}

    def _save_index(self):
        """Save the books index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
            logger.info(f"Saved index with {len(self.index)} books")
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def ingest_pdf(
        self, pdf_path: str, book_id: str = "mcmillan_options", force_refresh: bool = False
    ) -> dict[str, Any]:
        """
        Ingest a PDF book into the RAG system.

        Args:
            pdf_path: Path to the PDF file
            book_id: Book identifier (e.g., 'mcmillan_options')
            force_refresh: Re-ingest even if already cached

        Returns:
            Dict with ingestion status and stats
        """
        if PyPDF2 is None:
            logger.error("PyPDF2 not installed - cannot parse PDF files")
            return {"status": "error", "message": "PyPDF2 not installed"}

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"status": "error", "message": f"PDF not found: {pdf_path}"}

        # Check if already ingested
        if not force_refresh and book_id in self.index:
            logger.info(f"Book {book_id} already ingested. Use force_refresh=True to re-ingest.")
            return {"status": "already_ingested", "book_id": book_id}

        logger.info(f"Ingesting book: {book_id} from {pdf_path}")

        # Get book metadata
        book_meta = self.KNOWN_BOOKS.get(
            book_id,
            {"title": pdf_path.stem, "author": "Unknown", "edition": "Unknown", "topics": []},
        )

        try:
            # Step 1: Extract text from PDF
            logger.info("Step 1: Extracting text from PDF...")
            full_text, page_texts = self._extract_pdf_text(pdf_path)

            if not full_text:
                return {"status": "error", "message": "No text extracted from PDF"}

            # Save raw text
            parsed_file = self.parsed_dir / f"{book_id}.txt"
            with open(parsed_file, "w", encoding="utf-8") as f:
                f.write(full_text)

            # Step 2: Chunk the text intelligently
            logger.info("Step 2: Chunking content...")
            chunks = self._chunk_book(full_text, page_texts, book_meta)

            # Save chunks
            chunks_file = self.chunks_dir / f"{book_id}_chunks.json"
            with open(chunks_file, "w") as f:
                json.dump([asdict(c) for c in chunks], f, indent=2)

            # Step 3: Update index
            self.index[book_id] = {
                "book_id": book_id,
                "title": book_meta["title"],
                "author": book_meta["author"],
                "pdf_path": str(pdf_path),
                "parsed_file": str(parsed_file),
                "chunks_file": str(chunks_file),
                "chunk_count": len(chunks),
                "char_count": len(full_text),
                "page_count": len(page_texts),
                "ingested_at": datetime.now().isoformat(),
                "topics": book_meta.get("topics", []),
            }
            self._save_index()

            logger.info(
                f"Successfully ingested {book_id}: {len(chunks)} chunks from {len(page_texts)} pages"
            )

            return {
                "status": "success",
                "book_id": book_id,
                "chunks": len(chunks),
                "pages": len(page_texts),
                "chars": len(full_text),
            }

        except Exception as e:
            logger.error(f"Error ingesting {book_id}: {e}")
            return {"status": "error", "message": str(e)}

    def _extract_pdf_text(self, pdf_path: Path) -> tuple:
        """
        Extract text from PDF, page by page.

        Returns:
            Tuple of (full_text, list of page texts)
        """
        page_texts = []

        try:
            with open(pdf_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)

                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text:
                        page_texts.append({"page": page_num + 1, "text": text})

            full_text = "\n\n".join([p["text"] for p in page_texts])
            return full_text, page_texts

        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return "", []

    def _chunk_book(
        self, full_text: str, page_texts: list[dict], book_meta: dict
    ) -> list[BookChunk]:
        """
        Chunk book into semantic units.

        Strategy:
        1. Detect chapter/section boundaries
        2. Split into ~2000 char chunks
        3. Preserve paragraph boundaries
        4. Classify content types
        5. Track page numbers
        """
        chunks = []

        # Build page lookup for page number tracking
        page_lookup = {}
        char_pos = 0
        for page_data in page_texts:
            page_text = page_data["text"]
            page_num = page_data["page"]
            page_lookup[char_pos] = page_num
            char_pos += len(page_text) + 2  # +2 for \n\n separator

        # Split into paragraphs
        paragraphs = re.split(r"\n\s*\n", full_text)

        current_chapter = "Introduction"
        current_section = ""
        current_chunk_text = ""
        chunk_page_start = 1

        max_chunk_size = 2000  # Characters per chunk

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect chapter headers
            chapter_match = re.match(r"^(?:CHAPTER|Chapter)\s*(\d+)[:\s]+(.+)$", para)
            if chapter_match:
                # Save current chunk if not empty
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            current_chunk_text,
                            book_meta,
                            current_chapter,
                            current_section,
                            chunk_page_start,
                        )
                    )
                    current_chunk_text = ""

                chapter_num = int(chapter_match.group(1))
                current_chapter = self.MCMILLAN_CHAPTERS.get(
                    chapter_num, chapter_match.group(2).strip()
                )
                current_section = ""
                chunk_page_start = self._get_page_for_position(
                    len(full_text) - len("\n\n".join(paragraphs[paragraphs.index(para) :])),
                    page_lookup,
                )
                continue

            # Detect section headers (ALL CAPS or Title Case with specific patterns)
            if re.match(r"^[A-Z][A-Z\s]+$", para) and len(para) < 100:
                current_section = para.title()
                continue

            # Add paragraph to current chunk
            if len(current_chunk_text) + len(para) > max_chunk_size:
                # Save current chunk
                if current_chunk_text:
                    chunks.append(
                        self._create_chunk(
                            current_chunk_text,
                            book_meta,
                            current_chapter,
                            current_section,
                            chunk_page_start,
                        )
                    )
                current_chunk_text = para
                chunk_page_start = self._get_page_for_position(
                    len(full_text) - len("\n\n".join(paragraphs[paragraphs.index(para) :])),
                    page_lookup,
                )
            else:
                if current_chunk_text:
                    current_chunk_text += "\n\n" + para
                else:
                    current_chunk_text = para

        # Don't forget the last chunk
        if current_chunk_text:
            chunks.append(
                self._create_chunk(
                    current_chunk_text,
                    book_meta,
                    current_chapter,
                    current_section,
                    chunk_page_start,
                )
            )

        return chunks

    def _create_chunk(
        self, text: str, book_meta: dict, chapter: str, section: str, page_start: int
    ) -> BookChunk:
        """Create a BookChunk with content classification."""

        # Classify content type
        content_type = self._classify_content(text)

        # Extract topics
        topics = self._extract_topics(text, book_meta.get("topics", []))

        return BookChunk(
            book_title=book_meta.get("title", "Unknown"),
            author=book_meta.get("author", "Unknown"),
            chapter=chapter,
            section=section,
            page_numbers=str(page_start),
            content=text,
            content_type=content_type,
            topics=topics,
        )

    def _classify_content(self, text: str) -> str:
        """Classify chunk by content type."""
        text_lower = text.lower()

        scores = {}
        for content_type, patterns in self.CONTENT_PATTERNS.items():
            score = sum(1 for pattern in patterns if re.search(pattern, text_lower))
            scores[content_type] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        return max(scores, key=scores.get)

    def _extract_topics(self, text: str, known_topics: list[str]) -> list[str]:
        """Extract relevant topics from chunk."""
        text_lower = text.lower()
        found_topics = []

        # Topic keywords mapping
        topic_keywords = {
            "greeks": ["delta", "gamma", "theta", "vega", "rho"],
            "volatility": ["volatility", "iv", "implied volatility", "vix", "iv rank"],
            "covered_calls": ["covered call", "covered writing", "overwriting"],
            "iron_condor": ["iron condor", "condor", "wing spread"],
            "straddles": ["straddle", "long straddle", "short straddle"],
            "spreads": ["spread", "vertical spread", "calendar spread", "diagonal"],
            "risk_management": ["risk", "stop loss", "position sizing", "max loss"],
            "taxes": ["tax", "wash sale", "qualified covered call", "straddle rules"],
            "expected_move": ["expected move", "standard deviation", "one sigma"],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                found_topics.append(topic)

        return found_topics

    def _get_page_for_position(self, char_position: int, page_lookup: dict) -> int:
        """Find the page number for a character position."""
        last_page = 1
        for pos, page in sorted(page_lookup.items()):
            if pos > char_position:
                break
            last_page = page
        return last_page

    def search(
        self,
        query: str,
        book_id: Optional[str] = None,
        top_k: int = 5,
        content_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Search ingested books for relevant content.

        Args:
            query: Search query
            book_id: Optional book ID to search (None = all books)
            top_k: Number of results to return
            content_types: Filter by content types (strategy, example, etc.)

        Returns:
            Search results with excerpts and metadata
        """
        logger.info(f"Searching options books for: '{query}'")

        if not self.index:
            return {
                "query": query,
                "results": [],
                "message": "No books ingested. Use ingest_pdf() first.",
            }

        # Determine which books to search
        books_to_search = [book_id] if book_id else list(self.index.keys())

        all_results = []

        for bid in books_to_search:
            if bid not in self.index:
                continue

            book_info = self.index[bid]
            chunks_file = Path(book_info["chunks_file"])

            if not chunks_file.exists():
                continue

            with open(chunks_file) as f:
                chunks = json.load(f)

            # Score each chunk
            for chunk in chunks:
                # Filter by content type if specified
                if content_types and chunk["content_type"] not in content_types:
                    continue

                score = self._score_chunk(query, chunk)
                if score > 0:
                    all_results.append(
                        {
                            "book_id": bid,
                            "book_title": chunk["book_title"],
                            "author": chunk["author"],
                            "chapter": chunk["chapter"],
                            "section": chunk["section"],
                            "page": chunk["page_numbers"],
                            "content_type": chunk["content_type"],
                            "topics": chunk["topics"],
                            "excerpt": chunk["content"][:500] + "..."
                            if len(chunk["content"]) > 500
                            else chunk["content"],
                            "full_content": chunk["content"],
                            "score": score,
                        }
                    )

        # Sort by score and return top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = all_results[:top_k]

        return {
            "query": query,
            "results": top_results,
            "total_matches": len(all_results),
            "books_searched": books_to_search,
        }

    def _score_chunk(self, query: str, chunk: dict) -> float:
        """Score a chunk's relevance to query."""
        query_lower = query.lower()
        content_lower = chunk["content"].lower()

        # Tokenize query
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "what",
            "how",
            "when",
            "where",
            "why",
        }
        query_words = [w for w in query_lower.split() if w not in stop_words]

        if not query_words:
            return 0.0

        # Count matches
        matches = sum(content_lower.count(word) for word in query_words)

        # Boost for exact phrase match
        if query_lower in content_lower:
            matches *= 2

        # Boost for topic match
        for topic in chunk.get("topics", []):
            if topic.replace("_", " ") in query_lower:
                matches *= 1.5

        # Normalize by content length
        word_count = len(content_lower.split())
        return (matches / len(query_words)) * (1000 / max(word_count, 100))

    def get_chunks_for_rag(self, book_id: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Get all chunks formatted for RAG ingestion.

        Returns list of dicts ready for vector store ingestion.
        """
        all_chunks = []

        books_to_process = [book_id] if book_id else list(self.index.keys())

        for bid in books_to_process:
            if bid not in self.index:
                continue

            book_info = self.index[bid]
            chunks_file = Path(book_info["chunks_file"])

            if not chunks_file.exists():
                continue

            with open(chunks_file) as f:
                chunks = json.load(f)

            for i, chunk in enumerate(chunks):
                all_chunks.append(
                    {
                        "id": f"{bid}_chunk_{i}",
                        "content": chunk["content"],
                        "metadata": {
                            "book_id": bid,
                            "book_title": chunk["book_title"],
                            "author": chunk["author"],
                            "chapter": chunk["chapter"],
                            "section": chunk["section"],
                            "page": chunk["page_numbers"],
                            "content_type": chunk["content_type"],
                            "topics": ",".join(chunk["topics"]),
                            "source": "options_book",
                        },
                    }
                )

        return all_chunks

    # Implement abstract methods from BaseNewsCollector

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Options books don't have ticker-specific news.
        Return empty list.
        """
        return []

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Return general options knowledge as "market news".

        This returns chunks that can be used as context for trading decisions.
        """
        # Get high-value chunks (strategies, rules, warnings)
        valuable_types = ["strategy", "rule", "warning"]
        chunks = self.get_chunks_for_rag()

        # Filter to valuable content
        valuable_chunks = [c for c in chunks if c["metadata"]["content_type"] in valuable_types]

        # Convert to article format
        articles = []
        for chunk in valuable_chunks[:50]:  # Limit to 50 most valuable
            article = self.normalize_article(
                title=f"{chunk['metadata']['chapter']} - {chunk['metadata']['section'] or 'Overview'}",
                content=chunk["content"],
                url=f"book://{chunk['metadata']['book_id']}/page/{chunk['metadata']['page']}",
                published_date=datetime.now().strftime("%Y-%m-%d"),
                ticker=None,
                sentiment=None,
            )
            articles.append(article)

        return articles


# Convenience function
def get_options_book_collector() -> OptionsBookCollector:
    """Get OptionsBookCollector instance."""
    return OptionsBookCollector()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = OptionsBookCollector()

    print("Options Book Collector initialized")
    print(f"Cache directory: {collector.cache_dir}")
    print(f"Known books: {list(collector.KNOWN_BOOKS.keys())}")

    # Example: Check if any books are already ingested
    if collector.index:
        print(f"\nIngested books: {list(collector.index.keys())}")
    else:
        print("\nNo books ingested yet. Use ingest_pdf() to add books.")
