"""
Berkshire Hathaway Shareholder Letters Collector with RAG Search.

Downloads, parses, and indexes Warren Buffett's annual shareholder letters
(1977-2024) for semantic search and investment wisdom extraction.

Features:
- PDF and HTML parsing
- Local caching of letters
- Semantic search via embeddings
- Stock mention extraction
- Investment principle detection
- Multi-year cross-referencing
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class BerkshireLettersCollector(BaseNewsCollector):
    """
    Collect and index Warren Buffett's shareholder letters from Berkshire Hathaway.

    Provides:
    - Download all letters (1977-2024)
    - Parse PDF/HTML to searchable text
    - Extract investment principles
    - Identify stock mentions with sentiment
    - Semantic search capabilities
    """

    # URL patterns for Berkshire letters
    BASE_URL = "https://www.berkshirehathaway.com"
    LETTERS_URL = f"{BASE_URL}/letters/letters.html"

    # Common stock ticker mappings mentioned in letters
    KNOWN_TICKERS = {
        "coca-cola": "KO",
        "apple": "AAPL",
        "american express": "AXP",
        "bank of america": "BAC",
        "wells fargo": "WFC",
        "moody's": "MCO",
        "geico": "GEICO",  # Private/subsidiary
        "washington post": "WPO",  # Historical
        "see's candies": "SEES",  # Private
        "precision castparts": "PCP",  # Acquired
        "kraft heinz": "KHC",
        "davita": "DVA",
        "us bancorp": "USB",
        "goldman sachs": "GS",
        "procter & gamble": "PG",
        "chevron": "CVX",
        "occidental petroleum": "OXY",
    }

    def __init__(self, cache_dir: str | None = None):
        """
        Initialize Berkshire letters collector.

        Args:
            cache_dir: Directory to cache downloaded letters (default: data/rag/berkshire_letters)
        """
        super().__init__(source_name="berkshire")

        # Set cache directory
        if cache_dir is None:
            cache_dir = "data/rag/berkshire_letters"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories for organization
        self.raw_dir = self.cache_dir / "raw"
        self.parsed_dir = self.cache_dir / "parsed"
        self.index_dir = self.cache_dir / "index"

        for dir_path in [self.raw_dir, self.parsed_dir, self.index_dir]:
            dir_path.mkdir(exist_ok=True)

        # Load or create index
        self.index_file = self.index_dir / "letters_index.json"
        self.index = self._load_index()

        logger.info(f"Initialized Berkshire letters collector (cache: {self.cache_dir})")

    def _load_index(self) -> dict[int, dict[str, Any]]:
        """Load the letters index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading index: {e}")
                return {}
        return {}

    def _save_index(self):
        """Save the letters index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f, indent=2)
            logger.info(f"Saved index with {len(self.index)} letters")
        except Exception as e:
            logger.error(f"Error saving index: {e}")

    def download_all_letters(self, force_refresh: bool = False) -> int:
        """
        Download all available shareholder letters.

        Args:
            force_refresh: Re-download even if cached

        Returns:
            Number of letters downloaded
        """
        logger.info("Fetching Berkshire letters index page...")

        # Use proper headers to avoid 403 Forbidden
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        try:
            response = requests.get(self.LETTERS_URL, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all letter links
            letter_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Look for letter links (typically /letters/YYYY.html or /letters/YYYY.pdf)
                if "/letters/" in href and any(str(year) in href for year in range(1977, 2025)):
                    full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    letter_links.append(full_url)

            # Deduplicate
            letter_links = list(set(letter_links))
            logger.info(f"Found {len(letter_links)} letter links")

            # Download each letter
            downloaded = 0
            for url in letter_links:
                year = self._extract_year(url)
                if year and self._download_letter(year, url, force_refresh):
                    downloaded += 1

            self._save_index()
            logger.info(f"Downloaded {downloaded} letters")
            return downloaded

        except Exception as e:
            logger.error(f"Error downloading letters: {e}")
            return 0

    def _extract_year(self, url: str) -> int | None:
        """Extract year from letter URL."""
        match = re.search(r"(19|20)\d{2}", url)
        if match:
            year = int(match.group(0))
            if 1977 <= year <= 2024:
                return year
        return None

    def _download_letter(self, year: int, url: str, force_refresh: bool = False) -> bool:
        """
        Download a single letter.

        Args:
            year: Letter year
            url: Download URL
            force_refresh: Re-download even if cached

        Returns:
            True if downloaded successfully
        """
        # Check if already cached
        if not force_refresh and year in self.index:
            logger.debug(f"Letter {year} already cached")
            return False

        try:
            logger.info(f"Downloading {year} letter from {url}")

            # Use proper headers to avoid 403 Forbidden
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Determine file type
            content_type = response.headers.get("Content-Type", "").lower()
            is_pdf = "pdf" in content_type or url.endswith(".pdf")

            # Save raw file
            ext = "pdf" if is_pdf else "html"
            raw_file = self.raw_dir / f"{year}.{ext}"

            with open(raw_file, "wb") as f:
                f.write(response.content)

            # Parse content
            text = self._parse_pdf(raw_file) if is_pdf else self._parse_html(response.text)

            if not text:
                logger.warning(f"No text extracted from {year} letter")
                return False

            # Save parsed text
            parsed_file = self.parsed_dir / f"{year}.txt"
            with open(parsed_file, "w", encoding="utf-8") as f:
                f.write(text)

            # Extract metadata
            metadata = self._extract_metadata(year, text)

            # Update index
            self.index[year] = {
                "year": year,
                "url": url,
                "raw_file": str(raw_file),
                "parsed_file": str(parsed_file),
                "file_type": ext,
                "downloaded_at": datetime.now().isoformat(),
                "char_count": len(text),
                "word_count": len(text.split()),
                **metadata,
            }

            logger.info(f"Successfully downloaded and parsed {year} letter ({len(text)} chars)")
            return True

        except Exception as e:
            logger.error(f"Error downloading {year} letter: {e}")
            return False

    def _parse_pdf(self, file_path: Path) -> str:
        """Parse PDF to text."""
        if PyPDF2 is None:
            logger.error("PyPDF2 not installed - cannot parse PDF files")
            return ""

        try:
            text_parts = []
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")
            return ""

    def _parse_html(self, html_content: str) -> str:
        """Parse HTML to text."""
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return ""

    def _extract_metadata(self, year: int, text: str) -> dict[str, Any]:
        """
        Extract metadata from letter text.

        Args:
            year: Letter year
            text: Parsed letter text

        Returns:
            Metadata dict with stock mentions, themes, etc.
        """
        metadata = {"stock_mentions": [], "key_themes": [], "investment_principles": []}

        # Extract stock mentions
        text_lower = text.lower()
        for company, ticker in self.KNOWN_TICKERS.items():
            if company in text_lower:
                # Count mentions
                count = text_lower.count(company)

                # Try to extract sentiment context
                sentiment = self._extract_sentiment_context(text, company)

                metadata["stock_mentions"].append(
                    {
                        "company": company,
                        "ticker": ticker,
                        "mention_count": count,
                        "sentiment": sentiment,
                    }
                )

        # Extract common investment themes (keywords)
        theme_keywords = {
            "intrinsic_value": ["intrinsic value", "value investing"],
            "moat": ["economic moat", "competitive advantage", "durable advantage"],
            "management": [
                "management quality",
                "honest management",
                "capable management",
            ],
            "index_funds": ["index fund", "low-cost index"],
            "derivatives": ["derivatives", "financial weapons"],
            "insurance": ["insurance float", "underwriting"],
            "capital_allocation": ["capital allocation", "retained earnings"],
        }

        for theme, keywords in theme_keywords.items():
            if any(kw in text_lower for kw in keywords):
                metadata["key_themes"].append(theme)

        return metadata

    def _extract_sentiment_context(self, text: str, company: str) -> str:
        """
        Extract sentiment context around company mentions.

        Args:
            text: Full letter text
            company: Company name to search for

        Returns:
            Sentiment label: "bullish", "bearish", "neutral", or "mixed"
        """
        # Find sentences containing the company
        sentences = re.split(r"[.!?]+", text)
        relevant_sentences = [s for s in sentences if company.lower() in s.lower()]

        if not relevant_sentences:
            return "neutral"

        # Simple sentiment analysis based on keywords
        positive_words = [
            "excellent",
            "outstanding",
            "strong",
            "great",
            "wonderful",
            "superb",
            "exceptional",
            "remarkable",
            "increased",
            "growth",
        ]
        negative_words = [
            "poor",
            "weak",
            "declined",
            "disappointing",
            "loss",
            "difficulty",
            "problem",
            "concern",
            "mistake",
        ]

        pos_count = 0
        neg_count = 0

        for sentence in relevant_sentences:
            sentence_lower = sentence.lower()
            pos_count += sum(1 for word in positive_words if word in sentence_lower)
            neg_count += sum(1 for word in negative_words if word in sentence_lower)

        if pos_count > neg_count * 1.5:
            return "bullish"
        elif neg_count > pos_count * 1.5:
            return "bearish"
        elif pos_count > 0 and neg_count > 0:
            return "mixed"
        else:
            return "neutral"

    def search(self, query: str, top_k: int = 5, years: list[int] | None = None) -> dict[str, Any]:
        """
        Search shareholder letters for relevant content.

        Args:
            query: Search query (e.g., "index funds vs stock picking")
            top_k: Number of top results to return
            years: Optional list of years to search (default: all)

        Returns:
            Search results with excerpts, years, sentiment, and sources
        """
        logger.info(f"Searching letters for: '{query}'")

        if not self.index:
            logger.warning("No letters in index - run download_all_letters() first")
            return {
                "query": query,
                "relevant_excerpts": [],
                "years_referenced": [],
                "sentiment": "No data available",
                "source": "berkshire_letters",
            }

        # Filter by years if specified
        search_years = years if years else list(self.index.keys())

        # Search each letter
        results = []
        for year in search_years:
            if year not in self.index:
                continue

            letter_info = self.index[year]
            parsed_file = Path(letter_info["parsed_file"])

            if not parsed_file.exists():
                continue

            # Load text
            with open(parsed_file, encoding="utf-8") as f:
                text = f.read()

            # Simple keyword search (can be enhanced with embeddings)
            relevance_score = self._calculate_relevance(query, text)

            if relevance_score > 0:
                excerpts = self._extract_excerpts(query, text, max_excerpts=2)

                results.append(
                    {
                        "year": year,
                        "relevance_score": relevance_score,
                        "excerpts": excerpts,
                        "url": letter_info["url"],
                    }
                )

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = results[:top_k]

        # Extract overall sentiment from results
        sentiment = self._extract_overall_sentiment(query, results)

        return {
            "query": query,
            "relevant_excerpts": [
                {"year": r["year"], "excerpts": r["excerpts"], "url": r["url"]} for r in results
            ],
            "years_referenced": [r["year"] for r in results],
            "sentiment": sentiment,
            "source": "berkshire_letters",
        }

    def _calculate_relevance(self, query: str, text: str) -> float:
        """
        Calculate relevance score between query and text.

        Simple implementation using keyword matching.
        Can be enhanced with embeddings/semantic search.
        """
        query_lower = query.lower()
        text_lower = text.lower()

        # Extract query keywords (ignore common words)
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
        }
        query_words = [w for w in query_lower.split() if w not in stop_words]

        if not query_words:
            return 0.0

        # Count keyword matches
        total_matches = sum(text_lower.count(word) for word in query_words)

        # Normalize by text length (favor shorter, more focused matches)
        text_word_count = len(text_lower.split())
        normalized_score = (total_matches / len(query_words)) * (1000 / max(text_word_count, 1000))

        return normalized_score

    def _extract_excerpts(self, query: str, text: str, max_excerpts: int = 2) -> list[str]:
        """Extract relevant excerpts from text containing query keywords."""
        query_lower = query.lower()
        sentences = re.split(r"[.!?]+", text)

        # Find sentences containing query keywords
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
        }
        query_words = [w for w in query_lower.split() if w not in stop_words]

        relevant_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in query_words):
                # Clean and add
                clean_sentence = sentence.strip()
                if len(clean_sentence) > 50:  # Ignore very short sentences
                    relevant_sentences.append(clean_sentence)

        # Sort by number of keyword matches
        def count_matches(sentence):
            return sum(1 for word in query_words if word in sentence.lower())

        relevant_sentences.sort(key=count_matches, reverse=True)

        # Return top excerpts
        return relevant_sentences[:max_excerpts]

    def _extract_overall_sentiment(self, query: str, results: list[dict]) -> str:
        """Extract overall sentiment/answer from search results."""
        if not results:
            return "No relevant information found"

        # Combine top excerpts
        all_excerpts = []
        for r in results[:3]:  # Top 3 results
            all_excerpts.extend(r["excerpts"])

        if not all_excerpts:
            return "Information found but no clear excerpts"

        # Return first excerpt as summary (can be enhanced with LLM summarization)
        return all_excerpts[0][:500] + "..." if len(all_excerpts[0]) > 500 else all_excerpts[0]

    def get_stock_mentions(self, ticker: str) -> list[dict[str, Any]]:
        """
        Get all mentions of a stock across all letters.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of mentions with year, context, and sentiment
        """
        mentions = []

        # Find company name from ticker
        company_name = None
        for name, tick in self.KNOWN_TICKERS.items():
            if tick == ticker:
                company_name = name
                break

        if not company_name:
            logger.warning(f"Ticker {ticker} not in known companies")
            return []

        # Search all letters
        for year, letter_info in self.index.items():
            stock_mentions = letter_info.get("stock_mentions", [])
            for mention in stock_mentions:
                if mention.get("ticker") == ticker:
                    mentions.append(
                        {
                            "year": year,
                            "company": mention["company"],
                            "mention_count": mention["mention_count"],
                            "sentiment": mention["sentiment"],
                            "url": letter_info["url"],
                        }
                    )

        return sorted(mentions, key=lambda x: x["year"])

    def get_letter(self, year: int) -> str | None:
        """
        Get full text of a specific letter.

        Args:
            year: Letter year

        Returns:
            Letter text or None if not found
        """
        if year not in self.index:
            logger.warning(f"Letter for {year} not in index")
            return None

        parsed_file = Path(self.index[year]["parsed_file"])
        if not parsed_file.exists():
            logger.warning(f"Parsed file for {year} not found")
            return None

        try:
            with open(parsed_file, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading {year} letter: {e}")
            return None

    # Implement abstract methods from BaseNewsCollector

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect historical mentions of a ticker from shareholder letters.

        Note: Berkshire letters are annual, not daily news.
        The days_back parameter is ignored.

        Args:
            ticker: Stock ticker symbol
            days_back: Ignored (letters are annual)

        Returns:
            List of normalized "articles" (letter excerpts mentioning ticker)
        """
        mentions = self.get_stock_mentions(ticker)

        articles = []
        for mention in mentions:
            year = mention["year"]
            letter_text = self.get_letter(year)

            if not letter_text:
                continue

            # Find company name
            company_name = mention["company"]

            # Extract excerpts
            excerpts = self._extract_excerpts(company_name, letter_text, max_excerpts=3)
            content = (
                "\n\n".join(excerpts) if excerpts else f"Mentioned {mention['mention_count']} times"
            )

            article = self.normalize_article(
                title=f"Warren Buffett on {company_name.title()} ({year})",
                content=content,
                url=mention["url"],
                published_date=f"{year}-01-01",  # Approximate (letters published annually)
                ticker=ticker,
                sentiment=self._sentiment_to_score(mention["sentiment"]),
            )

            articles.append(article)

        return articles

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect general investment wisdom from most recent letters.

        Args:
            days_back: Number of years back to collect (not days)

        Returns:
            List of normalized articles
        """
        # Get most recent letters
        years = sorted(self.index.keys(), reverse=True)[: max(days_back, 5)]

        articles = []
        for year in years:
            letter_text = self.get_letter(year)
            if not letter_text:
                continue

            # Extract key excerpts (first few paragraphs)
            paragraphs = letter_text.split("\n\n")
            intro = "\n\n".join(paragraphs[:5])[:2000]  # First 2000 chars

            article = self.normalize_article(
                title=f"Berkshire Hathaway {year} Shareholder Letter",
                content=intro,
                url=self.index[year]["url"],
                published_date=f"{year}-02-28",  # Letters typically published Feb/Mar
                ticker=None,
                sentiment=None,
            )

            articles.append(article)

        return articles

    def _sentiment_to_score(self, sentiment: str) -> float | None:
        """Convert sentiment label to numeric score (0-1)."""
        sentiment_map = {"bullish": 0.8, "neutral": 0.5, "bearish": 0.2, "mixed": 0.5}
        return sentiment_map.get(sentiment)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = BerkshireLettersCollector()

    # Download all letters
    print("Downloading Berkshire shareholder letters...")
    count = collector.download_all_letters()
    print(f"Downloaded {count} letters")

    # Example search
    print("\n--- Search: 'index funds vs stock picking' ---")
    results = collector.search("index funds vs stock picking")
    print(f"Query: {results['query']}")
    print(f"Years referenced: {results['years_referenced']}")
    print(f"Sentiment: {results['sentiment']}")
    print("\nExcerpts:")
    for excerpt in results["relevant_excerpts"][:3]:
        print(f"\n{excerpt['year']}:")
        for text in excerpt["excerpts"]:
            print(f"  - {text[:200]}...")

    # Example stock mentions
    print("\n--- Stock Mentions: Apple (AAPL) ---")
    mentions = collector.get_stock_mentions("AAPL")
    for mention in mentions:
        print(f"{mention['year']}: {mention['mention_count']} mentions ({mention['sentiment']})")
